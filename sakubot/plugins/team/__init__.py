import asyncio
import json
import time
import uuid
from pathlib import Path

from sakubot.plugin import Invocation, Plugin, object_schema, text
from sakubot.store import encode
from sakubot.personas import managed_persona
from .confirmations import Confirmations


class Extension(Confirmations, Plugin):
    name = "team"

    def members(self):
        return self.runtime.store.kv_get("team:members", [])

    def setup(self):
        self.runtime.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, data TEXT NOT NULL, status TEXT NOT NULL, updated REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS team_requests (
          id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, task_id TEXT NOT NULL, run_id TEXT NOT NULL,
          kind TEXT NOT NULL, question TEXT NOT NULL, context TEXT NOT NULL, options TEXT NOT NULL,
          status TEXT NOT NULL, answer TEXT NOT NULL DEFAULT '', approved INTEGER,
          created REAL NOT NULL, resolved REAL, error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS team_requests_status ON team_requests(status,created);
        """)
        store = self.runtime.store
        store.execute("UPDATE tasks SET status='interrupted' WHERE status IN ('running','waiting') AND json_extract(data,'$.plugin_id')=?", (self.id,))
        store.execute("UPDATE tasks SET status='cancelled',updated=? WHERE status='pending' AND json_extract(data,'$.plugin_id') IS NULL", (time.time(),))
        store.execute("UPDATE team_requests SET status='interrupted',resolved=?,error='进程中断，等待已结束' WHERE status='waiting'", (time.time(),))
        store.execute("UPDATE events SET status='cancelled' WHERE status='pending' AND uid IN (SELECT 'team-request:' || id FROM team_requests WHERE status!='waiting')")
        self.active = {}
        self.setup_confirmations()
        members = self.members()
        migrated = []
        for member in members:
            if member.get('persona_mode') != 'managed':
                try:
                    persona = self.personas.get(member.get('persona_id') or self.runtime.config.settings.main_persona_id)
                except ValueError:
                    persona = self.personas.get(self.runtime.config.settings.main_persona_id)
                member = {**member, 'persona_mode': 'managed', 'persona_id': '',
                    'persona': {'prompt': persona['prompt'], 'visible_plugins': persona.get('visible_plugins')}}
            migrated.append(member)
        if migrated != members:
            self.runtime.store.kv_set('team:members', migrated)
        self.sync_agents(migrated)
        self.page("manage", "专业团队", Path(__file__).parent / "web" / "dist",
            icon="people", order=30, aliases=("/team",))
        self.api("members", self.page_members)
        self.api("members", self.save_member, methods=("POST",))
        self.api("members/{identifier}", self.delete_member, methods=("DELETE",))
        self.api("tasks", self.page_tasks)
        self.api("tasks", self.page_task_action, methods=("POST",))
        self.tool("team_members", "查看专业团队的 Agent 名称、职责、ID 及可用状态。先选择适合任务的成员，再用 team_delegate 委派。返回人格来源、模型和当前状态；完整人格用 team_get_member 查看。可用 team_create_member 动态创建成员，无须重载插件。",
            object_schema(), self.list_members)
        self.tool("team_delegate", "把分析或调查委派给专业团队中的指定 Agent，立即返回任务 ID。独立任务可并行，完成后通过 wake 回报主 Agent。成员使用各自的人格、模型与可见插件函数。",
            object_schema({"agent_id": text("team_members 返回的 Agent ID"), "goal": text("任务目标与完成标准"),
                "context": text("必需资料"),
                "resources": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                "timeout": {"type": "integer", "minimum": 30, "maximum": 3600}}, ("agent_id", "goal")), self.delegate)
        self.tool("team_tasks", "查看专业团队任务、最新进度和结果，或取消未完成任务。主 Agent 读到完成/失败结果后自动取消仍在排队的对应完成通知，无需再次处理。中断任务不会自动重新执行。",
            object_schema({"action": {"type": "string", "enum": ["list", "get", "cancel"]}, "id": text()}, ("action",)), self.manage)

        visible_schema = {'anyOf': [{'type': 'array', 'items': {'type': 'string'}, 'maxItems': 100}, {'type': 'null'}],
            'description': '可见插件 ID；null 表示所有插件，空数组表示不提供插件工具。团队待确认和报告函数需要包含 team。'}
        self.tool('team_create_member', '创建持久化团队 Agent。提供独立的人格提示词，固定自管理人格；立即声明并可委派，不重载插件，不影响其他成员。先查看现有成员，避免重复创建。model_id 留空继承默认模型。',
            object_schema({'name': text('成员名称'), 'description': text('职责和适用任务'),
                'prompt': text('完整人格和工作方式，不要把一次性任务当成人格'),
                'visible_plugins': visible_schema, 'model_id': text('框架模型条目 ID，留空继承默认')},
                ('name', 'description', 'prompt')), self.create_member_tool)
        self.tool('team_get_member', '读取团队成员完整配置、插件持有的人格、可见插件及模型覆盖信息。编辑前先读取。',
            object_schema({'agent_id': text('团队 Agent ID')}, ('agent_id',)), self.get_member_tool)
        self.tool('team_update_member', '修改现有团队成员，未传字段保持不变。人格或模型修改从下一次任务开始生效，保留当前运行和上下文；人格和可见插件由专业团队通过实例接口控制；Agent 管理中的模型覆盖仍优先。',
            object_schema({'agent_id': text('团队 Agent ID'), 'name': text(), 'description': text(),
                'prompt': text('自管理人格完整内容'), 'visible_plugins': visible_schema,
                'model_id': text('框架模型条目 ID，空字符串继承默认')}, ('agent_id',)), self.update_member_tool)

    def configure_member(self, member):
        agent = self.get_agent(member['id'])
        agent.set_persona(member['persona']['prompt']).with_plugins(member['persona'].get('visible_plugins'))
        return agent

    def bind_member(self, member):
        agent = self.configure_member(member)
        agent.tool('team_report_result', '记录本次团队任务的最终成果', object_schema({'result': text()}, ('result',)), self.report_result)
        agent.tool('team_update_progress', '更新当前任务的简短进度，供主 Agent 查询。仅在阶段成果、阻碍或计划出现实质变化时使用，不必逐条复述工具调用，不要重复相同进度。不会单独唤醒主 Agent。',
            object_schema({'progress': text('已完成什么、正在做什么或遇到的阻碍，最多2000字符')}, ('progress',)), self.update_progress)
        self.add_confirmation_tool(agent)
        agent.on('reset', self.agent_reset)
        agent.on('tool_call', self.agent_tool_call)
        agent.on('tool_round', self.agent_tool_round)
        agent.on('completed', self.agent_completed)

    def sync_agents(self, members):
        self.set_agents([{key: value for key, value in member.items() if key != 'persona'} for member in members])
        for member in members:
            self.bind_member(member)

    def member_id(self, identifier):
        prefix = self.id + ':'
        return identifier[len(prefix):] if identifier.startswith(prefix) else identifier

    def save_member_record(self, data):
        fields = {'id', 'name', 'description', 'persona', 'model_id'}
        if not isinstance(data, dict) or set(data) - fields:
            raise ValueError('团队成员字段无效')
        members = self.members()
        identifier = data.get('id') or uuid.uuid4().hex[:12]
        old = next((row for row in members if row['id'] == identifier), None)
        if data.get('id') and old is None:
            raise ValueError('团队成员不存在')
        if old is None and len(members) >= 500:
            raise ValueError('团队成员数量已达上限')
        record = {**(old or {}), **data, 'id': identifier, 'persona_mode': 'managed', 'persona_id': ''}
        persona = record.get('persona')
        if not isinstance(persona, dict) or set(persona) - {'prompt', 'visible_plugins'}:
            raise ValueError('自管理人格无效')
        persona = managed_persona(persona.get('prompt'), persona.get('visible_plugins'))
        normalized = self.runtime.agents.definition(self.id, {key: value for key, value in record.items() if key != 'persona'})
        model_id = normalized['model_id']
        if model_id:
            _, model = self.runtime.config.settings.selected_model(model_id=model_id)
            if model is None or not model.capabilities.text:
                raise ValueError('请选择已启用的文本模型')
        record = {key: normalized[key] for key in ('name', 'description', 'persona_mode', 'persona_id', 'model_id')}
        record['id'] = identifier
        record['persona'] = persona
        updated = [record if row['id'] == identifier else row for row in members] if old else [*members, record]
        self.runtime.store.kv_set('team:members', updated)
        self.agent(identifier, record['name'], record['description'], persona_id=record['persona_id'],
            model_id=record['model_id'], persona_mode=record['persona_mode'])
        if old is None:
            self.bind_member(record)
        else:
            self.configure_member(record)
        self.runtime.store.log('info', self.id, 'team.member.saved', data={'agent_id': self.id + ':' + identifier})
        return self.member_record(identifier)

    def member_record(self, identifier):
        identifier = self.member_id(identifier)
        member = next((row for row in self.members() if row['id'] == identifier), None)
        if member is None:
            raise ValueError('团队成员不存在')
        return {**member, 'agent': self.runtime.agents.profile(self.id + ':' + identifier)}

    async def get_member_tool(self, inv, args):
        return {**self.member_record(args['agent_id']), 'available_plugins': [
            {'id': plugin.id, 'available': self.runtime.registry.availability(plugin.id)['available']}
            for plugin in self.runtime.registry.plugins]}

    async def create_member_tool(self, inv, args):
        return self.save_member_record({'name': args['name'], 'description': args['description'],
            'persona': {'prompt': args['prompt'], 'visible_plugins': args.get('visible_plugins')},
            'model_id': args.get('model_id', '')})

    async def update_member_tool(self, inv, args):
        identifier = self.member_id(args['agent_id'])
        old = self.member_record(identifier)
        data = {key: value for key, value in args.items() if key in ('name', 'description', 'model_id')}
        data['id'] = identifier
        if 'prompt' in args or 'visible_plugins' in args:
            data['persona'] = {**(old.get('persona') or {}), **{key: args[key] for key in ('prompt', 'visible_plugins') if key in args}}
        return self.save_member_record(data)

    async def report_result(self, invocation, args):
        invocation.metadata["data"]["report"] = args["result"]
        return {"recorded": True}

    async def agent_tool_call(self, event):
        inv = event["invocation"]
        if inv.task_id and event["phase"] == "after":
            self.runtime.store.execute("UPDATE tasks SET data=json_set(data,'$.last_tool',?,'$.tool_calls',coalesce(json_extract(data,'$.tool_calls'),0)+1) WHERE id=?", (event["name"], inv.task_id))

    async def update_progress(self, invocation, args):
        progress = args['progress'].strip()
        if not progress or len(progress) > 2000:
            raise ValueError('进度不能为空或超过2000字符')
        changed = self.runtime.store.execute("UPDATE tasks SET data=json_set(data,'$.progress',?,'$.progress_at',?),updated=? WHERE id=? AND status IN ('running','waiting') AND json_extract(data,'$.run_id')=?",
            (progress, time.time(), time.time(), invocation.task_id, invocation.run_id)).rowcount
        if not changed:
            raise ValueError('当前没有可更新进度的团队任务')
        return {'recorded': True, 'progress': progress}

    async def agent_tool_round(self, event):
        inv = event['invocation']
        if not inv.task_id:
            return
        self.runtime.store.execute("UPDATE tasks SET data=json_set(data,'$.tool_rounds',coalesce(json_extract(data,'$.tool_rounds'),0)+1) WHERE id=?", (inv.task_id,))
        inv.inject_temporary('本轮工具调用已经结束。判断是否出现了值得主 Agent 知道的阶段成果、阻碍或计划变化；有实质变化时用 team_update_progress 更新简短进度，否则直接继续任务。不必每轮更新，已更新的内容不要重复，也不要为了进度提醒额外循环调用。任务完成时直接给出成果。')

    async def agent_completed(self, event):
        inv = event["invocation"]
        if inv.task_id:
            self.runtime.store.execute("UPDATE tasks SET data=json_set(data,'$.agent_completed',1) WHERE id=?", (inv.task_id,))

    def context(self, invocation):
        return {"pending_requests": self.request_records(), "professional_team": [{"id": row["id"], "name": row["name"], "description": row["description"], "ready": row["ready"]}
            for row in self.runtime.agents.list() if row["plugin_id"] == self.id]}

    async def page_members(self, request):
        return {"items": [self.member_record(row["id"]) for row in self.members()], "revision": self.runtime.agents.revision}

    async def save_member(self, request):
        record = self.save_member_record(await request.json())
        return {'id': record['id'], 'revision': self.runtime.agents.revision}

    async def delete_member(self, request):
        identifier = request.path_params['identifier']
        self.member_record(identifier)
        await self.agent_reset({'agent_id': self.id + ':' + identifier})
        # Re-read after awaiting; another member may have been created meanwhile.
        updated = [row for row in self.members() if row['id'] != identifier]
        self.runtime.store.kv_set('team:members', updated)
        self.remove_agent(identifier)
        self.runtime.store.log('info', self.id, 'team.member.deleted', data={'agent_id': self.id + ':' + identifier})
        return {'ok': True, 'revision': self.runtime.agents.revision}

    def tasks(self):
        return [{**row, "data": json.loads(row["data"])} for row in self.runtime.store.rows(
            "SELECT * FROM tasks WHERE json_extract(data,'$.plugin_id')=? ORDER BY updated DESC LIMIT 100", (self.id,))]

    async def page_tasks(self, request):
        return self.tasks()

    async def page_task_action(self, request):
        return await self.call_tool("team_tasks", await request.json())

    async def list_members(self, inv, args):
        return [{key: row[key] for key in ('id', 'name', 'description', 'ready', 'busy', 'persona_source', 'persona_name', 'model_name')}
            for row in self.runtime.agents.list() if row['plugin_id'] == self.id]

    async def start(self):
        self.background(self.worker())

    async def delegate(self, inv, args):
        identifier = args["agent_id"]
        identifier = identifier if identifier.startswith(self.id + ":") else self.id + ":" + identifier
        profile = self.runtime.agents.snapshot(identifier)
        if profile["plugin_id"] != self.id:
            raise ValueError("请选择专业团队成员")
        goal, context = args["goal"], args.get("context", "")
        if not goal.strip() or len(goal) > 10000 or len(context) > 40000:
            raise ValueError("任务目标或资料无效")
        task_id = uuid.uuid4().hex[:12]
        data = {**args, "agent_id": identifier, "agent_name": profile["name"], "plugin_id": self.id,
            "created": time.time(), "parent_run": inv.run_id,
            "target": self.runtime.main_target()}
        self.runtime.store.execute("INSERT INTO tasks VALUES (?,?,'pending',?)", (task_id, encode(data), time.time()))
        return {"id": task_id, "agent_id": identifier, "agent_name": profile["name"], "status": "pending", "report": "完成后 wake 主 Agent"}

    def acknowledge_results(self, rows, invocation):
        if not invocation or invocation.agent_id != 'main' or invocation.origin != 'agent':
            return rows
        for row in rows:
            if row['status'] not in ('done', 'failed'):
                continue
            # Reading the result and suppressing its redundant wake are synchronous.
            # Also mark unqueued results reported so the worker cannot enqueue them later.
            self.cancel_wake('team-result:' + row['id'])
            self.runtime.store.execute("UPDATE tasks SET data=json_set(data,'$.reported',json('true'),'$.observed_by_main',1) WHERE id=?", (row['id'],))
            row['data'].update(reported=True, observed_by_main=True)
        return rows

    async def manage(self, inv, args):
        if args["action"] == "list":
            return self.acknowledge_results(self.tasks(), inv)
        row = self.runtime.store.one("SELECT * FROM tasks WHERE id=? AND json_extract(data,'$.plugin_id')=?", (args.get("id", ""), self.id))
        if not row:
            raise ValueError("任务不存在")
        if args["action"] == "cancel" and row["status"] in ("pending", "running", "waiting"):
            self.runtime.store.execute("UPDATE tasks SET status='cancelled',updated=? WHERE id=?", (time.time(), row["id"]))
            task = self.active.get(row["id"])
            if task:
                task.cancel()
            return {"id": row["id"], "status": "cancelled"}
        return self.acknowledge_results([{**row, "data": json.loads(row["data"])}], inv)[0]

    async def worker(self):
        while True:
            for row in self.runtime.store.rows("SELECT * FROM tasks WHERE status IN ('done','failed') AND json_extract(data,'$.plugin_id')=? AND coalesce(json_extract(data,'$.reported'),0)=0 LIMIT 10", (self.id,)):
                data = json.loads(row["data"])
                await self.emit("wake", encode({"task_id": row["id"], "agent_id": data["agent_id"], "agent_name": data["agent_name"],
                    "goal": data["goal"], "status": row["status"], "result": data.get("result", "")}),
                    target=data["target"], priority=40, uid="team-result:" + row["id"],
                    meta={"task_id": row["id"], "result_is_data": True})
                data["reported"] = True
                self.runtime.store.execute("UPDATE tasks SET data=? WHERE id=?", (encode(data), row["id"]))
            row = self.runtime.store.one("SELECT * FROM tasks WHERE status='pending' AND json_extract(data,'$.plugin_id')=? ORDER BY updated LIMIT 1", (self.id,))
            if not row:
                await asyncio.sleep(1)
                continue
            self.runtime.store.execute("UPDATE tasks SET status='running',updated=? WHERE id=?", (time.time(), row["id"]))
            job = self.background(self.run_task(row))
            self.active[row["id"]] = job
            def finished(task, identifier=row["id"]):
                self.active.pop(identifier, None)
                if task in self.jobs:
                    self.jobs.remove(task)
                if not task.cancelled():
                    task.exception()
            job.add_done_callback(finished)
            await asyncio.sleep(0)

    async def run_task(self, row):
        data = json.loads(row["data"])
        run_id = "team:" + row["id"] + ":" + uuid.uuid4().hex[:8]
        data["run_id"] = run_id
        self.runtime.store.execute("UPDATE tasks SET data=? WHERE id=?", (encode(data), row["id"]))
        inv = Invocation(run_id, data["target"], task_id=row["id"])
        locks = [self.runtime.resource_locks.setdefault(name, asyncio.Lock()) for name in sorted(set(data.get("resources", [])))]
        acquired = []
        status, result = "done", ""
        try:
            for lock in locks:
                await lock.acquire()
                acquired.append(lock)
            agent = self.get_agent(data["agent_id"])
            outcome = await agent.wake(data["goal"], invocation=inv, run_id=run_id, context=data.get("context", ""),
                instructions="完成团队委派任务，必要时用 team_report_result 记录成果；需要主 Agent 判断、用户补充信息或确认操作时使用 team_wait_confirmation，收到返回结果后继续，不要重新派发。",
                timeout=data.get("timeout", 300))
            result = outcome["data"].get("report") or outcome["result"]
        except asyncio.CancelledError:
            status, result = "interrupted", "团队任务已中断，未自动重放"
            raise
        except Exception as exc:
            status = "failed"
            result = str(exc)[:500] if type(exc) in (ValueError, RuntimeError) else type(exc).__name__
        finally:
            for lock in reversed(acquired):
                lock.release()
            current = self.runtime.store.one("SELECT status FROM tasks WHERE id=?", (row["id"],))
            if current and current["status"] == "cancelled":
                status = "cancelled"
            latest = self.runtime.store.one("SELECT data FROM tasks WHERE id=?", (row["id"],))
            if latest:
                data.update(json.loads(latest["data"]))
            data.update(result=result, finished=time.time())
            self.runtime.store.execute("UPDATE tasks SET data=?,status=?,updated=? WHERE id=?", (encode(data), status, time.time(), row["id"]))
            self.runtime.store.log("info" if status == "done" else "warning", self.id, "team.task." + status,
                run_id=run_id, data={"agent_id": data["agent_id"], "task_id": row["id"]})
