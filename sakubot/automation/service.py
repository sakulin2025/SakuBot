"""Durable automation queue, worker bridge and failure policies."""
import asyncio
import json
import re
import time
import uuid

import jsonschema

from sakubot.store import encode
from .repository import Repository, identifier
from .sources import Sources

from .context import current_chain
from .execution import Executor
from . import wake


class Scripts:
    def __init__(self, runtime):
        self.runtime = runtime
        self.repo = Repository(runtime)
        self.sources = Sources(self)
        self.executor = Executor(self)
        self.jobs = {}
        self.maintenance = set()
        self.worker = None
        self.stopping = False
        self.loop_ref = None

    def spawn(self, coroutine):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self.loop_ref and not self.loop_ref.is_closed():
                self.loop_ref.call_soon_threadsafe(self.spawn, coroutine)
                return None
            coroutine.close()
            raise RuntimeError('脚本运行器未启动') from None
        self.loop_ref = loop
        task = asyncio.create_task(coroutine)
        self.maintenance.add(task)
        def done(task):
            self.maintenance.discard(task)
            if not task.cancelled() and task.exception():
                self.runtime.store.log('error','scripts','script.background.failed',data={'error':str(task.exception())[:300]})
        task.add_done_callback(done)
        return task

    def start(self):
        self.loop_ref = asyncio.get_running_loop()
        self.stopping = False
        if not self.worker or self.worker.done():
            self.worker = asyncio.create_task(self.loop(), name='script-queue')

    async def stop(self):
        self.stopping = True
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        await self.sources.stop()
        tasks = list(self.jobs.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*list(self.maintenance), return_exceptions=True)

    def source_manifest(self):
        return self.sources.manifest()

    def bindings(self):
        result = []
        named = set()
        for row in self.repo.list('bindings'):
            source = self.sources.resolve(row['source'])
            available = bool(source and self.runtime.registry.availability(source['plugin_id'])['available'])
            reason = '' if available else '触发源未声明' if not source else '触发源暂不可用'
            eligible = True
            try:
                script = None
                if row.get('target_kind', 'script') == 'wake':
                    wake.validate(row)
                else:
                    script = self.repo.get(row['script_id'])
                    jsonschema.validate(row['params'], script['parameters'])
                if source:
                    jsonschema.validate(row['source_params'], source['parameters'])
                    if source.get('validate'):
                        source['validate'](row['source_params'])
                eligible = script['enabled'] if script else True
                if not eligible:
                    reason = '脚本触发已停用'
            except Exception:
                eligible, reason = False, '参数或脚本已变化，请重新保存绑定'
            if '*' not in row['source']:
                if row['source'] in named:
                    eligible, reason = False, '事件已绑定其他动作，请删除重复绑定'
                named.add(row['source'])
            result.append({**row,'available':available and eligible,'eligible':eligible,'declared':bool(source),'reason':reason})
        return result

    def save_binding(self, data):
        if not isinstance(data, dict):
            raise ValueError('绑定格式无效')
        key = identifier(data.get('id') or uuid.uuid4().hex[:12])
        old = self.runtime.store.one('SELECT data FROM automation_bindings WHERE id=?', (key,))
        old = json.loads(old['data']) if old else {}
        value = {**old, **data, 'id':key}
        value.setdefault('target_kind', 'script')
        if value['target_kind'] not in ('script', 'wake'):
            raise ValueError('绑定目标仅支持 script / wake')
        script = self.repo.get(value.get('script_id')) if value['target_kind'] == 'script' else None
        if script is None:
            wake.validate(value)
            value['script_id'] = ''
            value['params'] = {}
        if not isinstance(value.get('source'),str) or not re.fullmatch(r'[A-Za-z0-9_.*:-]{1,512}',value['source']):
            raise ValueError('来源 ID 无效')
        if '*' not in value['source'] and any(
            row['id'] != key and row['source'] == value['source']
            for row in self.repo.list('bindings')
        ):
            raise ValueError('此事件已绑定动作，请编辑原绑定或先删除原绑定')
        source = self.sources.resolve(value['source'])
        value.setdefault('name', (script['name'] if script else '唤醒主智能体') + ' · ' + (source['name'] if source else value['source']))
        value.setdefault('enabled', True)
        value.setdefault('source_params', {})
        value.setdefault('params', {})
        value.setdefault('on_failure', 'none')
        value.setdefault('failure_threshold', 1)
        value.setdefault('cooldown_seconds', 3600)
        value.setdefault('send_result_to_source', True)
        if not isinstance(value['source_params'],dict) or len(encode(value['source_params']))>50000:
            raise ValueError('来源参数须为不超过 50000 字符的对象')
        if source:
            jsonschema.validate(value['source_params'], source['parameters'])
        if script:
            jsonschema.validate(value['params'], script['parameters'])
        if not isinstance(value['name'],str) or not value['name'].strip() or len(value['name'])>100:
            raise ValueError('绑定名称为 1～100 字')
        if value['on_failure'] not in ('none','wake','notify') or type(value['enabled']) is not bool or type(value['send_result_to_source']) is not bool:
            raise ValueError('失败策略或开关无效')
        if type(value['failure_threshold']) is not int or not 1 <= value['failure_threshold'] <= 100 or type(value['cooldown_seconds']) is not int or not 30 <= value['cooldown_seconds'] <= 2592000:
            raise ValueError('失败阈值为 1～100 次，冷却时间为 30～2592000 秒')
        # Source-specific validation is local only; saving never executes a script.
        validator = source.get('validate') if source else None
        if validator:
            validator(value['source_params'])
        value['updated'] = time.time()
        self.runtime.store.execute('INSERT OR REPLACE INTO automation_bindings VALUES (?,?)', (key, encode(value)))
        self.spawn(self.sources.reconcile())
        return value

    def delete(self, kind, key, confirm=False):
        identifier(key)
        if confirm is not True:
            raise ValueError('请确认删除')
        if kind == 'script':
            self.repo.get(key)
            if self.runtime.store.one("SELECT id FROM automation_runs WHERE script_id=? AND status IN ('running','queued')", (key,)):
                raise ValueError('脚本有运行或排队任务，请先停止')
            if any(row.get('target_kind', 'script') == 'script' and row.get('script_id') == key for row in self.repo.list('bindings')):
                raise ValueError('请先删除脚本的触发绑定')
            for plugin in self.runtime.registry.plugins:
                references = getattr(plugin, 'script_references', None)
                if references and references(key):
                    raise ValueError('脚本仍被插件 ' + plugin.id + ' 使用，请先解除相关任务')
            # Keep revisions and private state for audit; deletion removes registration only.
            self.runtime.store.execute('DELETE FROM automation_scripts WHERE id=?', (key,))
        elif kind == 'binding':
            self.runtime.store.execute('DELETE FROM automation_bindings WHERE id=?', (key,))
            self.runtime.store.execute("UPDATE automation_runs SET status='cancelled',finished=?,error='触发绑定已删除' WHERE binding_id=? AND status='queued'",(time.time(),key))
            self.spawn(self.sources.reconcile())
        else:
            raise ValueError('删除类型无效')
        return {'deleted':key}

    def enqueue_binding(self, binding, event, uid):
        if binding.get('target_kind', 'script') == 'wake':
            return wake.enqueue(self, binding, event, uid)
        return self.enqueue(binding['script_id'], params=binding['params'], event=event, binding=binding, uid=uid)

    def enqueue(self, key, *, params=None, event=None, binding=None, uid=None):
        script = self.repo.get(key)
        if (binding or event) and not script['enabled']:
            return {'status':'disabled'}
        params = params or {}
        jsonschema.validate(params, script['parameters'])
        chain = list(current_chain.get())
        if len(chain) >= 8:
            raise ValueError('脚本触发链达到 8 层，已阻止循环')
        marker = key + '@' + script['version']
        if marker in chain:
            raise ValueError('已阻止同版本脚本循环触发；请先检查执行记录和程序')
        from .script_contracts import validate_event
        event = event if event is not None else {'source':'manual','id':uuid.uuid4().hex,'at':time.time(),'data':{}}
        validate_event(script,event)
        payload = {'params':params,'event':event,
                   'chain':chain + [marker], 'failure_policy':binding or {'id':'script:'+key,**{field:script.get(field,default) for field,default in [('on_failure','none'),('failure_threshold',1),('cooldown_seconds',3600),('send_result_to_source',True)]}}}
        if len(encode(payload).encode()) > 524288:
            raise ValueError('脚本输入超过 512 KiB')
        if uid:
            previous = self.runtime.store.one('SELECT id,status FROM automation_runs WHERE uid=?',(uid,))
            if previous:
                return {**previous,'duplicate':True}
            merged = self.runtime.store.kv_get('automation:merged:' + uid)
            if merged:
                return {'id':merged,'duplicate':True}
        pending = self.runtime.store.rows("SELECT id,status FROM automation_runs WHERE script_id=? AND status IN ('queued','running') ORDER BY queued",(key,))
        if pending and binding and script['concurrency'] == 'skip':
            return {'status':'skipped','active_id':pending[0]['id']}
        if pending and binding and script['concurrency'] == 'merge':
            queued = next((row for row in reversed(pending) if row['status']=='queued'),None)
            if queued:
                # Keep all preceding IDs deduplicated even after replacing the pending payload.
                if uid:
                    self.runtime.store.kv_set('automation:merged:' + uid, queued['id'])
                self.runtime.store.execute('UPDATE automation_runs SET input=?,version=?,binding_id=? WHERE id=?',
                    (encode(payload),script['version'],binding['id'],queued['id']))
                return {'id':queued['id'],'status':'merged'}
        if self.runtime.store.one("SELECT count(*) n FROM automation_runs WHERE status='queued'")['n'] >= 1000:
            raise ValueError('脚本全局排队任务已达 1000 个')
        if len(pending) >= 100:
            raise ValueError('此脚本排队任务已达 100 个')
        run_id = 'script:' + uuid.uuid4().hex
        self.runtime.store.execute('INSERT INTO automation_runs (id,script_id,binding_id,version,status,queued,input,uid) VALUES (?,?,?,?,?,?,?,?)',
            (run_id,key,binding['id'] if binding else '',script['version'],'queued',time.time(),encode(payload),uid))
        self.runtime.live.publish('script.queued',run_id=run_id,script_id=key)
        return {'id':run_id,'status':'queued','version':script['version']}

    def trigger_failure(self, binding, event, uid, error):
        if self.runtime.store.one('SELECT id FROM automation_runs WHERE uid=?', (uid,)):
            return
        if binding.get('target_kind', 'script') == 'wake':
            self.runtime.store.log('error', 'scripts', 'binding.wake.failed', data={'binding_id': binding['id'], 'error': error[:2000]})
            return
        script = self.repo.get(binding['script_id'])
        run_id = 'script:' + uuid.uuid4().hex
        now = time.time()
        payload = {'params':binding['params'],'event':event,'chain':list(current_chain.get()),'failure_policy':binding}
        self.runtime.store.execute("INSERT INTO automation_runs (id,script_id,binding_id,version,status,queued,started,finished,input,error,uid) VALUES (?,?,?,?,'failed',?,?,?,?,?,?)",
            (run_id,script['id'],binding['id'],script['version'],now,now,now,encode(payload),error[:2000],uid))
        self.spawn(self.failure({'id':run_id,'script_id':script['id']},payload,error[:2000]))

    def runs(self, key='', limit=100):
        return self.runtime.store.rows('SELECT id,script_id,binding_id,version,status,queued,started,finished,error FROM automation_runs WHERE (?=\'\' OR script_id=?) ORDER BY queued DESC LIMIT ?', (key,key,max(1,min(limit,100))))

    def detail(self, key):
        row = self.runtime.store.one('SELECT * FROM automation_runs WHERE id=?',(key,))
        if not row:
            raise ValueError('执行记录不存在')
        row['input'] = json.loads(row['input'])
        row['output'] = json.loads(row['output']) if row['output'] else None
        row['tool_calls'] = self.runtime.store.rows('SELECT * FROM tool_calls WHERE run_id=? ORDER BY id',(key,))
        return row

    async def cancel(self, key):
        row = self.detail(key)
        if key in self.jobs:
            self.jobs[key].cancel()
            await asyncio.gather(self.jobs[key],return_exceptions=True)
        elif row['status'] == 'queued':
            self.runtime.store.execute("UPDATE automation_runs SET status='cancelled',finished=? WHERE id=?",(time.time(),key))
        return self.detail(key)

    def log(self, key, text):
        value = str(text)
        self.runtime.store.execute('UPDATE automation_runs SET logs=substr(logs || ?, -262144) WHERE id=?',(value+'\n',key))
        self.runtime.live.publish('script.log',run_id=key,text=value[:4000])

    def task_done(self, key, task):
        self.jobs.pop(key, None)
        error = '执行被中断，外部操作可能已执行' if task.cancelled() else str(task.exception())[:1000] if task.exception() else ''
        if error:
            self.runtime.store.execute("UPDATE automation_runs SET status=?,finished=?,error=? WHERE id=? AND status='running'",
                ('interrupted' if task.cancelled() else 'failed',time.time(),error,key))
            self.runtime.store.log('error','scripts','script.process.failed',data={'run_id':key,'error':error})

    async def loop(self):
        while True:
            try:
                await self.sources.reconcile()
                active_scripts = {row['script_id'] for row in self.runtime.store.rows("SELECT script_id FROM automation_runs WHERE status='running'")}
                for row in self.runtime.store.rows("SELECT * FROM automation_runs WHERE rowid IN (SELECT min(rowid) FROM automation_runs WHERE status='queued' GROUP BY script_id) ORDER BY queued LIMIT 100"):
                    if len(self.jobs) >= 8:
                        break
                    if row['script_id'] in active_scripts:
                        continue
                    active_scripts.add(row['script_id'])
                    self.runtime.store.execute("UPDATE automation_runs SET status='running',started=? WHERE id=?",(time.time(),row['id']))
                    task = asyncio.create_task(self.executor.execute(row))
                    self.jobs[row['id']] = task
                    task.add_done_callback(lambda task,key=row['id']:self.task_done(key,task))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.runtime.store.log('error','scripts','script.queue.failed',data={'error':str(exc)[:300]})
            await asyncio.sleep(1)

    async def failure(self, row, payload, error):
        binding = payload.get('failure_policy') or {}
        key = binding.get('id')
        if not key or binding.get('on_failure','none') == 'none':
            return
        state_key = 'automation:failure:' + key
        state = self.runtime.store.kv_get(state_key, {})
        count = state.get('count',0) + 1
        state['count'] = count
        try:
            if count >= binding.get('failure_threshold',1) and time.time() - state.get('last',0) >= binding.get('cooldown_seconds',3600):
                content = '脚本执行失败：' + row['script_id'] + '\n执行 ID：' + row['id'] + '\n错误：' + error
                await self.runtime.emit(binding['on_failure'],'scripts',content,target='main',uid='script-failure:'+row['id'],
                    send_result_to_source=binding.get('send_result_to_source',True),
                    meta={'script_id':row['script_id'],'script_run_id':row['id'],'script_chain':payload.get('chain',[])})
                state['last'] = time.time()
        finally:
            self.runtime.store.kv_set(state_key,state)

