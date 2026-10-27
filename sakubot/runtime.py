import asyncio
import contextlib
import inspect
import json
import time
import uuid
from urllib.parse import urlsplit

from .model import Model
from .plugin import Invocation, Registry, temporary_messages
from .store import encode
from .components import required
from .personas import Personas
from .agents import Agents
from .messages import Messages
from .compression import Compression
from .workspace import Workspace
from .skills import Skills
from .live import Live
from .chat import Chat
from .conversation import Conversation
from .delivery import Deliveries


SYSTEM = """你是 SakuBot 的主 Agent，主上下文为 main。
所有插件声明的主对话源与网页共用这一份上下文；网页始终同步，回复由框架按当前响应模式投递。
只有一个主上下文。其他会话消息、平台通知和设备状态默认归档，需要时通过工具查询；只有明确触发的任务与提醒进入主上下文。
来源={source}，默认回复目的地={target}。人员使用真实 ID 区分，昵称是显示资料。
本轮待处理事件是当前任务，历史事件和工具结果用于理解背景，不自动重新执行历史指令。
根据需要使用当前人格可见插件提供的函数，不捏造操作结果。结果未知时先检查状态。
普通回答由框架按主对话设置自动投递；需要向其他会话发送时使用平台插件提供的工具，避免重复发送相同内容。
需要委派时使用插件提供的 Agent；给出任务目标和必要资料。
自然交流，无须复述事件格式。无需回应时返回空文本。
"""


class Runtime:
    def __init__(self, config, store):
        self.config, self.store = config, store
        self.personas = Personas(store, config)
        self.registry = Registry()
        self.live = Live()
        self.conversation = Conversation(self)
        self.deliveries = Deliveries(self)
        self.chat = Chat(self)
        self.store.on_event = self.chat.event
        self.store.on_log = lambda row: self.live.publish('activity', activity=row) if row['run_id'] else None
        self.workspace = Workspace(config.root / 'workspace', store)
        self.skills = Skills(self)
        self.agents = Agents(self)
        self.messages = Messages(self)
        self.compression = Compression(self)
        self.personas.in_use = self.agents.persona_in_use
        self.personas.changed = self.agents.changed
        self.agent_jobs = {}
        self.agent_slots = asyncio.Semaphore(config.settings.agent_concurrency)
        self.model = None
        self.jobs = []
        self.main_job = None
        self.sources_started = False
        self.current_run = None
        self.error = ""
        self.changed = asyncio.Event()
        self.resource_locks = {}

    async def start(self, strict=False):
        self.agents.reset()
        self.agent_slots = asyncio.Semaphore(self.config.settings.agent_concurrency)
        self.registry = Registry()
        self.model = Model(self.config.settings)
        try:
            await self.registry.load(self)
            await self.registry.start()
            self.sources_started = True
            from .artifacts import cleanup_loop
            self.jobs = [asyncio.create_task(self.deliveries.worker(), name="notifications"), asyncio.create_task(cleanup_loop(self.config.root), name="artifact-cleanup")]
            await self.sync_main_worker()
            self.error = ""
            self.store.log("info", "runtime", "runtime.started", data={"enabled": self.config.settings.enabled})
        except Exception as exc:
            await self.registry.stop()
            self.error = "插件加载失败（" + type(exc).__name__ + "），Agent 已暂停，可在设置页修复"
            self.store.log("error", "runtime", "runtime.failed", data={"error": type(exc).__name__})
            if strict:
                raise

    async def sync_main_worker(self):
        if self.config.settings.ready():
            if self.main_job is None or self.main_job.done():
                self.main_job = asyncio.create_task(self.worker(), name="main-agent")
        elif self.main_job is not None:
            self.main_job.cancel()
            await asyncio.gather(self.main_job, return_exceptions=True)
            self.main_job = None

    async def set_main_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("状态无效")
        settings = self.config.settings.model_copy(deep=True)
        settings.enabled = enabled
        if enabled:
            self.agents.snapshot("main")
        self.config.save(settings)
        self.model.settings = settings
        await self.sync_main_worker()
        self.agents.changed()
        self.store.log("info", "agents", "main.enabled" if enabled else "main.disabled")

    def clear_main_context(self):
        instance = self.agents.get('main')
        if self.current_run or instance.busy or instance.resetting or self.store.one(
                "SELECT id FROM events WHERE kind='wake' AND status='pending' AND (expires=0 OR expires>?) LIMIT 1", (time.time(),)):
            raise RuntimeError('主对话正在运行或有待处理消息')
        cutoff = self.store.one('SELECT coalesce(max(id),0) AS id FROM events')['id']
        boundary = {'cutoff': cutoff, 'revision': self.chat.boundary()['revision'] + 1, 'at': time.time()}
        # Retain audit rows, but exclude earlier events from prompts and the chat page.
        with self.store.db:
            for key, value in (
                ('agent:main-summary', {'cutoff': cutoff, 'text': ''}),
                ('agent:history:main', []), ('agent:pending:main', []),
                ('chat:boundary', boundary),
            ):
                self.store.db.execute('INSERT OR REPLACE INTO kv(key,value) VALUES (?,?)', (key, encode(value)))
        instance.history, instance.pending = [], []
        self.store.log('warning', 'agents', 'context.cleared', data={'agent_id': 'main', 'cutoff': cutoff})
        self.live.models.clear()
        self.live.publish('context.cleared', agent_id='main', **boundary)
        return {'ok': True}

    async def stop(self):
        if self.main_job is not None:
            self.main_job.cancel()
            await asyncio.gather(self.main_job, return_exceptions=True)
            self.main_job = None
        self.sources_started = False
        for task in self.jobs:
            task.cancel()
        await asyncio.gather(*self.jobs, return_exceptions=True)
        self.jobs = []
        await self.conversation.stop()
        await self.registry.stop()
        await self.workspace.shell_runner.stop()
        await self.messages.stop()
        self.agents.reset()
        agent_jobs = {task for tasks in self.agent_jobs.values() for task in tasks if task is not asyncio.current_task()}
        for task in agent_jobs:
            task.cancel()
        await asyncio.gather(*agent_jobs, return_exceptions=True)
        self.agent_jobs.clear()
        if self.model:
            await self.model.close()

    @staticmethod
    def main_target():
        return 'main'

    def validate_target(self, target):
        if not isinstance(target, str) or not target or len(target) > 256 or any(ord(char) < 32 for char in target):
            raise ValueError('事件目标无效')
        return target

    async def emit(self, kind, source, content, *, actor="", label="", target="", meta=None,
                   uid=None, priority=20, expires=0, include_context=False, temporary_context=""):
        if kind not in ("context", "wake", "notify"):
            raise ValueError("事件类型仅支持 context / wake / notify")
        if not isinstance(content, str) or len(content) > 200000:
            raise ValueError("事件正文必须为文本，最多200000字符")
        target = self.main_target() if not target or target == 'owner' else target
        self.validate_target(target)
        uid = uid or uuid.uuid4().hex
        if kind == 'notify':
            if not content.strip():
                raise ValueError('通知文字不能为空')
            row = self.store.event('notify', source, content, target=target, uid='notify:' + uid,
                meta={**(meta or {}), 'role': 'assistant', 'exclude_context': not include_context})
            if target == 'main':
                self.conversation.publish('text', response_id='notify:' + uid, text=content, final=True)
                return {'id': row['id'], 'uid': uid, 'kind': kind}
            delivery_id = 'notify:' + uid
            self.deliveries.enqueue(target, content, delivery_id)
            return {'id': row['id'], 'uid': uid, 'kind': kind, 'delivery_id': delivery_id}
        if temporary_context:
            temporary_messages(temporary_context)
            if kind != 'wake':
                raise ValueError('临时上下文仅用于 wake')
            meta = {**(meta or {}), 'temporary_context': temporary_context}
        row = self.store.event(kind, source, content, actor=actor, label=label, target=target,
            meta=meta, uid=uid, priority=priority, expires=expires)
        self.changed.set()
        if kind == 'wake':
            self.store.log('info', source, 'event.queued', data={'event_id': row['id'], 'target': target})
        return {'id': row['id'], 'uid': uid, 'kind': kind, 'status': row['status']}

    def cancel_wake(self, identifier):
        column = 'id' if isinstance(identifier, int) else 'uid'
        row = self.store.one('SELECT id,uid,kind,status,source FROM events WHERE '+column+'=?', (identifier,))
        if not row or row['kind'] != 'wake':
            return {'cancelled': False, 'status': row['status'] if row else 'missing'}
        changed = self.store.execute("UPDATE events SET status='cancelled',meta=json_set(meta,'$.exclude_context',json('true')) WHERE id=? AND status='pending' AND kind='wake'", (row['id'],)).rowcount
        status = 'cancelled' if changed else row['status']
        if changed:
            self.store.log('info', row['source'], 'event.cancelled', data={'event_id': row['id'], 'uid': row['uid']})
            self.live.publish('event.cancelled', event_id=row['id'], uid=row['uid'])
        return {'id': row['id'], 'uid': row['uid'], 'cancelled': bool(changed), 'status': status}

    async def deliver_reply(self, invocation, result):
        await self.conversation.respond(result, run_id=invocation.run_id,
            delivery_target=invocation.metadata.get('reply_target', ''),
            response_id=invocation.metadata.get('response_id', invocation.run_id + ':final'), exclude=[source for source, texts in invocation.metadata.get('sent_source_texts', {}).items() if result in texts])

    def prepare_agent(self, inv):
        if "agent_profile" not in inv.metadata:
            profile = self.agents.snapshot(inv.agent_id)
            inv.metadata["agent_profile"] = profile
            inv.persona_id = profile["effective_persona_id"]
            inv.model_id = profile["effective_model_id"]
        return inv.metadata["agent_profile"]

    async def run_agent(self, identifier, goal, *, invocation, context="", run_id=None):
        owner = self.agents.raw(identifier)["plugin_id"]
        return await self.agents.get(identifier, owner).wake(goal, invocation=invocation, context=context, run_id=run_id)

    def prompt(self, event, inv):
        profile = self.prepare_agent(inv)
        settings = self.config.settings
        system = SYSTEM.format(source=event["source"], target=inv.target)
        if inv.metadata.get('reply_target'):
            system += '\n本轮最终文本将由框架自动投递到 ' + inv.metadata['reply_target'] + '，不要再用发送工具重复发送最终回复。当前主对话响应源不改变。'
        cutoff = self.store.one("SELECT max(id) AS id FROM events")["id"] or 0
        memo = self.store.kv_get("agent:main-summary", {"cutoff": 0, "text": ""})
        events = self.store.rows("SELECT * FROM events WHERE id>? AND id<=? ORDER BY id DESC", (memo["cutoff"], cutoff))
        candidates = []
        for row in events:
            if row["id"] == event["id"]:
                continue
            if row["kind"] == "wake" and row["status"] in ("pending", "running") and row["id"] != event["id"]:
                continue  # Future queued instructions are handled once, in their own turn.
            metadata = json.loads(row["meta"])
            if metadata.get("exclude_context") or metadata.get("exclude_main"):
                continue
            if row["kind"] == "wake" and row["status"] in ("cancelled", "expired"):
                continue
            item = {key: row[key] for key in ("id", "at", "source", "actor", "label", "target")}
            item["text"] = row["text"]
            item["metadata"] = {key: value for key, value in metadata.items() if key not in ("segments", "raw", "packet", "temporary_context")}
            if 'injected_context' in item['metadata']:
                item['metadata']['injected_context'] = [x for x in item['metadata']['injected_context'] if not x.get('_temporary')]
            content = encode(item)
            candidates.append({"role": "assistant" if metadata.get("role") == "assistant" else "user", "content": content, "_event_id": row["id"]})
        contributions = []
        visible_plugins = self.registry.visible_plugin_ids(inv)
        for plugin in self.registry.plugins:
            if plugin.id not in visible_plugins:
                continue
            context = getattr(plugin, "context", None)
            if context:
                contributions.append({"plugin_id": plugin.id, "data": context(inv)})
        memory_text = encode(contributions)[:min(12000, settings.context_chars // 4)]
        # Explicitly repeat the active event: a high-priority older wake must not get lost in recent traffic.
        active = {key: event[key] for key in ("id", "source", "actor", "label", "target", "text")}
        instance = self.agents.get("main")
        injected = instance.take_pending() + json.loads(event["meta"]).get("injected_context", [])
        inv.temporary_context = temporary_messages(json.loads(event['meta']).get('temporary_context', '')) + [
            {'role': row['role'], 'content': row['content']} for row in injected if row.get('_temporary')]
        injected = [row for row in injected if not row.get('_temporary')]
        summary = [{"role": "assistant", "content": "历史上下文摘要：" + memo["text"], "_summary": True}] if memo["text"] else []
        return [{"role": "system", "content": profile["prompt"] + "\n" + system + "\n插件上下文：" + memory_text},
            *summary, *reversed(candidates), *injected, {"role": "user", "content": "本轮待处理事件：" + encode(active)}]

    async def refresh_capabilities(self, messages, invocation):
        visible = self.registry.visible_plugin_ids(invocation)
        content = []
        for plugin in self.registry.plugins:
            if plugin.id in visible:
                try:
                    contribution = plugin.prompt_context(invocation)
                    if inspect.isawaitable(contribution):
                        contribution = await contribution
                except Exception as exc:
                    self.store.log('warning', plugin.id, 'plugin.context.failed', run_id=invocation.run_id,
                        data={'error': type(exc).__name__})
                    continue
                if contribution:
                    content.append(contribution)
        messages[:] = [message for message in messages if not message.get('_capabilities')]
        if content:
            messages.insert(1 if messages and messages[0].get('role') == 'system' else 0,
                {'role': 'system', 'content': '\n\n'.join(content), '_capabilities': True})

    async def agent_loop(self, messages, inv, *, lightweight=False, max_steps=None):
        self.prepare_agent(inv)
        usage = []
        for step in range(max_steps or self.config.settings.max_steps):
            if inv.instance:
                inv.instance.ensure_active()
            provider, selected = self.model.settings.selected_model(model_id=inv.model_id)
            available = self.registry.available(inv) if selected and selected.capabilities.tools else []
            tools = [tool.schema() for tool in available]
            await self.refresh_capabilities(messages, inv)
            await self.compression.compact(messages, inv, tools)
            if inv.instance:
                await inv.instance.dispatch("model_request", {"run_id": inv.run_id, "step": step+1, "invocation": inv})
            temporary = inv.temporary_context + inv.temporary_next
            inv.temporary_next = []
            request_messages = list(messages)
            if temporary:
                request_messages[1:1] = [row for row in temporary if not row.get('_observation')]
                request_messages.extend(row for row in temporary if row.get('_observation'))
                traced = [{'role': row['role'], 'preview_paths': row['_preview_paths']} if row.get('_preview_paths') else row for row in temporary]
                inv.metadata.setdefault('temporary_contexts', []).append({'step': step + 1, 'messages': traced})
            snapshot = [{"plugin_id": tool.plugin_id, **tool.schema()} for tool in available]
            inv.metadata.setdefault("function_snapshots", []).append({"step": step + 1, "at": time.time(),
                "model_id": selected.id if selected else "", "functions": snapshot})
            self.save_trace(inv, messages, usage)
            started = time.monotonic()
            self.store.log("info", "model", "model.request", run_id=inv.run_id,
                data={"step": step + 1, "provider_id": provider.id if provider else "", "model_id": selected.model_id if selected else "", "functions": [tool.name for tool in available]})
            request_id = inv.run_id + ':' + str(step + 1)
            if inv.agent_id == 'main':
                inv.metadata['response_id'] = request_id
                self.conversation.process('model.started', request_id=request_id, run_id=inv.run_id, agent_id=inv.agent_id, step=step + 1)
            async def delta(text):
                self.conversation.process('model.delta', request_id=request_id, run_id=inv.run_id, agent_id=inv.agent_id, text=text)
            try:
                message, used = await self.model.complete(request_messages, tools, model_id=inv.model_id,
                    on_delta=delta if inv.agent_id == 'main' else None)
                if inv.agent_id == 'main':
                    self.conversation.process('model.completed', request_id=request_id, run_id=inv.run_id, agent_id=inv.agent_id)
            except BaseException as exc:
                if inv.agent_id == 'main':
                    self.conversation.process('model.failed', request_id=request_id, run_id=inv.run_id, agent_id=inv.agent_id)

                self.store.log("error", "model", "model.failed", run_id=inv.run_id, data={"error": str(exc)[:500] if type(exc) is RuntimeError else type(exc).__name__})
                raise
            self.store.log("info", "model", "model.completed", run_id=inv.run_id,
                data={"step": step + 1, "duration_ms": round((time.monotonic() - started) * 1000), "usage": used})
            usage.append(used)
            messages.append(message)
            self.save_trace(inv, messages, usage)
            calls = message.get("tool_calls") or []
            if not calls:
                return message.get("content") or "", usage
            for call in calls:
                inv.call_id = call["id"]
                try:
                    function = call["function"]
                    result = await self.registry.call(function["name"], function["arguments"], inv)
                    content = encode(result)
                except Exception as exc:
                    # Tool validation and deliberate ValueErrors may be displayed; never leak remote exception headers.
                    content = encode({"error": str(exc)[:500] if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__,
                                      "note": "无自动重试；执行结果不明时先检查状态。"})
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": content[:20000]})
                self.save_trace(inv, messages, usage)
            if inv.instance:
                await inv.instance.dispatch('tool_round', {'run_id': inv.run_id, 'step': step + 1,
                    'calls': calls, 'invocation': inv})
        raise RuntimeError("本轮已达到工具调用轮数上限；任务未自动重放")

    def save_trace(self, inv, messages, usage):
        self.store.execute("UPDATE runs SET trace=? WHERE id=?", (encode({"messages": messages, "usage": usage,
            "temporary_contexts": inv.metadata.get("temporary_contexts", []),
            "function_snapshots": inv.metadata.get("function_snapshots", []), "compressions": inv.metadata.get("compressions", []),
            "persona_id": inv.persona_id, "agent_id": inv.agent_id, "model_id": inv.model_id,
            "instance_id": inv.instance.generation if inv.instance else "",
            "agent_profile": {key: value for key, value in inv.metadata.get("agent_profile", {}).items() if key != "prompt" and not key.startswith("_")}}), inv.run_id))

    async def worker(self):
        while True:
            event = self.store.claim()
            if not event:
                self.changed.clear()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(self.changed.wait(), 1)
                continue
            run_id = uuid.uuid4().hex
            reply_target = json.loads(event['meta']).get('reply_target', '')
            self.current_run = {"id": run_id, "event_id": event["id"], "started": time.time(), 'reply_target': reply_target}
            self.store.execute("INSERT INTO runs VALUES (?,?,?,NULL,'running','{}','')", (run_id, event["id"], time.time()))
            inv = Invocation(run_id, event["target"], event["actor"], instance=self.agents.get("main"))
            inv.metadata['reply_target'] = reply_target
            self.conversation.process("run.started", run_id=run_id, event_id=event["id"], agent_id="main")
            self.store.log("info", "agent", "agent.started", run_id=run_id, data={"event_id": event["id"], "agent_id": "main"})
            try:
                self.prepare_agent(inv)
                await inv.instance.dispatch("started", {"run_id": run_id, "invocation": inv})
                result, usage = await asyncio.wait_for(self.agent_loop(self.prompt(event, inv), inv), 600)
                if result.strip():
                    await self.deliver_reply(inv, result)
                self.store.execute("UPDATE events SET status='done' WHERE id=?", (event["id"],))
                self.store.execute("UPDATE runs SET status='done', finished=? WHERE id=?", (time.time(), run_id))
                await inv.instance.dispatch("completed", {"run_id": run_id, "result": result, "usage": usage, "invocation": inv})
                self.error = ""
                self.store.log("info", "agent", "agent.completed", run_id=run_id)
                self.conversation.process("run.completed", run_id=run_id, event_id=event["id"], agent_id="main")
            except BaseException as exc:
                interrupted = isinstance(exc, asyncio.CancelledError)
                error = "运行被中断，远端操作可能已执行" if interrupted else (
                    str(exc)[:500] if isinstance(exc, (RuntimeError, ValueError)) else type(exc).__name__)
                self.store.execute("UPDATE events SET status=?,error=? WHERE id=?",
                                   ("interrupted" if interrupted else "failed", error, event["id"]))
                self.store.execute("UPDATE runs SET status=?,finished=?,error=? WHERE id=?",
                                   ("interrupted" if interrupted else "failed", time.time(), error, run_id))
                self.error = error
                self.store.log("warning" if interrupted else "error", "agent", "agent.interrupted" if interrupted else "agent.failed", run_id=run_id, data={"error": error})
                await inv.instance.dispatch("cancelled" if interrupted else "failed", {"run_id": run_id, "error": error, "invocation": inv})
                self.conversation.process("run.failed", run_id=run_id, event_id=event["id"], error=error, agent_id="main")
                if interrupted:
                    raise
            finally:
                self.current_run = None

    def status(self):
        return {"enabled": self.config.settings.enabled, "configured": self.config.settings.ready(),
                "registry_revision": self.registry.revision, "agents_revision": self.agents.revision,
                "main_session": "main",
                "running": self.current_run, "error": self.error,
                "queue": self.store.rows("SELECT status,count(*) AS count FROM events WHERE kind='wake' GROUP BY status"),
                "plugins": [{"name": plugin.id} for plugin in self.registry.plugins],
                "tools": [{"name": tool.name, "description": tool.description, "plugin_id": tool.plugin_id} for tool in self.registry.tools.values() if self.registry.availability(tool.plugin_id)["available"]]}

    def function_catalog(self, agent_id="main"):
        profile = self.agents.profile(agent_id)
        _, model = self.config.settings.selected_model(model_id=profile["effective_model_id"])
        invocation = Invocation("catalog", self.main_target(),
            agent_id=agent_id, persona_id=profile["effective_persona_id"], instance=self.agents.get(agent_id))
        return [{"name": tool.name, "plugin_id": tool.plugin_id, "source_label": "系统" if required(tool.plugin_id) else tool.plugin_id, "description": tool.description,
            "parameters": tool.parameters, "available": bool(model and model.capabilities.tools)}
            for tool in self.registry.available(invocation)]
