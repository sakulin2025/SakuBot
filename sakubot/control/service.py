"""Core-owned management queue shared by authenticated console and Agent extension."""
import asyncio
import os
import jsonschema
import platform
import time
import uuid

from .operations import Operations
from .configuration import Configuration
from .plugins import Plugins
from .projects import Projects
from .restart import Restart

ACTIONS = {'plugin.toggle','plugin.reload','plugin.delete','plugin.import','plugin.export',
           'project.build','project.publish','project.rollback','config.patch','system.restart'}


class Control:
    def __init__(self, runtime):
        self.runtime = runtime
        self.boot_id = os.environ.get('SAKUBOT_BOOT_ID') or uuid.uuid4().hex
        self.started = time.time()
        self.lock = asyncio.Lock()
        self.operations = Operations(runtime.store, self.boot_id)
        self.plugins = Plugins(self)
        self.projects = Projects(self)
        self.configuration = Configuration(self)
        self.restart = Restart(self)
        self.agent_concurrency = runtime.config.settings.agent_concurrency
        self.job = None

    def start(self):
        if self.job is None or self.job.done():
            self.job = asyncio.create_task(self.worker(), name='system-management')

    async def stop(self):
        if self.job:
            self.job.cancel()
            await asyncio.gather(self.job, return_exceptions=True)
            self.job = None

    def status(self):
        from .. import __version__
        return {'version':__version__, 'boot_id':self.boot_id, 'uptime_seconds':round(time.time()-self.started),
            'platform':platform.system(), 'python':platform.python_version(),
            'restart_supported':self.restart.supported(), 'running':self.runtime.current_run, 'error':self.runtime.error,
            'plugins':self.runtime.registry.installed_catalog(), 'config':self.runtime.config.public(),
            'paths':{'plugins':str(self.runtime.config.root/'plugins'), 'projects':str(self.projects.root),
                     'revisions':str(self.projects.revisions), 'sdk':'/app/plugin-sdk'},
            'operations':self.operations.list(30)}

    def submit(self, action, payload, *, invocation=None, requester='console'):
        if not isinstance(action, str) or action not in ACTIONS or not isinstance(payload, dict):
            raise ValueError('管理操作或参数无效')
        self.validate(action, payload)
        if invocation is not None:
            if invocation.agent_id != 'main' or invocation.origin != 'agent':
                raise ValueError('仅主智能体可提交系统管理操作')
            requester = 'system_control'
            if not self.runtime.registry.loaded(requester):
                raise ValueError('系统管理插件未启用')
        if action == 'system.restart':
            if not self.restart.supported():
                raise ValueError('当前启动方式不支持内部重启')
            if self.runtime.store.one("SELECT id FROM system_operations WHERE action='system.restart' AND status IN ('queued','running','restarting') LIMIT 1"):
                raise ValueError('已有待执行的重启')
            if payload.get('resume') and not isinstance(payload['resume'], str):
                raise ValueError('重启后目标须为文本')
            payload = {**payload, 'send_result_to_source':payload.get('send_result_to_source', invocation.send_result_to_source if invocation else True)}
        operation = self.operations.create(action, payload, invocation.run_id if invocation else '', requester, context={'notify': invocation is not None and action != 'system.restart', 'send_result_to_source':invocation.send_result_to_source if invocation else False})
        self.runtime.store.log('info','control','management.queued',run_id=invocation.run_id if invocation else '',
            data={'operation_id':operation['id'],'action':action})
        return {'operation_id':operation['id'],'status':'queued','execution':'after_current_wake' if invocation else 'queued'}

    @staticmethod
    def validate(action, payload):
        from ..plugin import object_schema
        boolean={'type':'boolean'}
        base={'id':{'type':'string','pattern':'^[a-z][a-z0-9_]{0,40}$'}, 'force':boolean}
        fields={
            'plugin.toggle':({**base,'enabled':boolean},('id','enabled')),
            'plugin.reload':(base,('id',)),
            'plugin.delete':({**base,'purge':boolean,'confirm':{'const':True}},('id','confirm')),
            'plugin.import':({'path':{'type':'string','minLength':1},'include_data':boolean},('path',)),
            'plugin.export':({'id':base['id'],'include_data':boolean},('id',)),
            'project.build':({'id':base['id']},('id',)),
            'project.publish':({**base,'version':{'type':'string','minLength':64,'maxLength':64},'enable':boolean},('id','version')),
            'project.rollback':({**base,'revision':{'type':'string','pattern':'^[0-9a-f-]+$'},'enable':boolean},('id','revision')),
            'system.restart':({'reason':{'type':'string','minLength':1,'maxLength':2000}, 'progress':{'type':'string','maxLength':20000},
                               'resume':{'type':'string','maxLength':20000},'send_result_to_source':boolean},('reason',)),
        }
        if action == 'config.patch':
            from ..config import Settings
            if set(payload)-set(Settings.model_fields): raise ValueError('配置字段无效')
            return
        properties, required=fields[action]
        try:
            jsonschema.validate(payload, object_schema(properties,required))
        except jsonschema.ValidationError as exc:
            raise ValueError('管理操作参数无效：'+'.'.join(str(item) for item in exc.absolute_path)) from None

    async def notify_completed(self):
        if not self.runtime.config.settings.ready(): return
        rows=self.runtime.store.rows("SELECT id FROM system_operations WHERE status IN ('done','failed','interrupted') AND json_extract(context,'$.notify')=1 ORDER BY created LIMIT 20")
        for row in rows:
            op=self.operations.get(row['id'])
            if self.runtime.registry.loaded('system_control'):
                await self.runtime.emit('wake','system_control',
                    '管理操作已结束。操作：'+op['action']+'；状态：'+op['status']+'；操作 ID：'+op['id']+
                    ('。错误：'+op['error'] if op['error'] else '')+'。按需使用 system_operations 查询详情并继续任务。',
                    uid='management-result:'+op['id'], meta={'management_operation':op['id']},
                    send_result_to_source=op['context'].get('send_result_to_source',False))
            self.runtime.store.execute("UPDATE system_operations SET context=json_set(context,'$.notify',json('false')) WHERE id=?",(op['id'],))

    async def execute(self, op):
        p, action = op['payload'], op['action']
        if action == 'plugin.toggle': return await self.plugins.toggle(p['id'],p['enabled'],force=p.get('force',False))
        if action == 'plugin.reload': return await self.plugins.reload(p['id'],force=p.get('force',False))
        if action == 'plugin.delete': return await self.plugins.delete(p['id'],purge=p.get('purge',False),confirm=p.get('confirm',False),force=p.get('force',False))
        if action == 'plugin.import': return await self.plugins.import_archive(p['path'],p.get('include_data',False))
        if action == 'plugin.export':
            path = await self.plugins.export_archive(p['id'],p.get('include_data',False))
            target = self.runtime.config.root/'workspace'/'artifacts'/('plugin-'+p['id']+'-'+op['id'][:8]+'.zip')
            target.parent.mkdir(parents=True,exist_ok=True)
            import shutil
            shutil.move(str(path),target)
            return {'path':str(target)}
        if action == 'project.build': return await self.projects.build(p['id'],op['id'])
        if action in ('project.publish','project.rollback'):
            return await self.projects.publish(p['id'],p.get('version',''), enable=p.get('enable',True),force=p.get('force',False),rollback=p.get('revision','') if action.endswith('rollback') else '')
        if action == 'config.patch': return await self.configuration.patch(p)
        if action == 'system.restart':
            await self.restart.execute(op)
            return None
        raise ValueError('不支持的管理操作')

    def quiescing(self):
        return self.restart.requested or bool(self.runtime.store.one("SELECT id FROM system_operations WHERE action='system.restart' AND status IN ('queued','running','restarting') AND boot_id=? LIMIT 1", (self.boot_id,)))

    def ready(self, op):
        if self.restart.requested: return False
        # Agent operations run after its whole wake has been committed, never inside its own tool.
        if op['run_id']:
            if self.runtime.current_run and self.runtime.current_run['id']==op['run_id']: return False
            row = self.runtime.store.one('SELECT status FROM runs WHERE id=?',(op['run_id'],))
            if row and row['status'] == 'running': return False
        if op['action'] == 'system.restart':
            return not self.runtime.current_run and not any(self.runtime.agent_jobs.values())
        return True

    async def worker(self):
        while True:
            try:
                await self.restart.recover()
                await self.configuration.maintain()
                await self.notify_completed()
                queued = self.runtime.store.rows("SELECT id FROM system_operations WHERE status='queued' ORDER BY created LIMIT 100")
                for item in queued:
                    op = self.operations.get(item['id'],private=True)
                    if op['status'] != 'queued': continue
                    if not self.ready(op): continue
                    if op['requester']=='system_control' and not self.runtime.registry.loaded('system_control'):
                        self.operations.update(op['id'],'cancelled',error='系统管理插件已停用')
                        continue
                    self.operations.update(op['id'],'running')
                    try:
                        result = await self.execute(op)
                        if not (op['action']=='system.restart' and self.restart.requested):
                            self.operations.update(op['id'],'done',result=result)
                    except asyncio.CancelledError:
                        if not self.restart.requested:
                            self.operations.update(op['id'],'interrupted',error='进程停止；请检查实际执行结果')
                        raise
                    except Exception as exc:
                        error = str(exc)[:1000] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
                        self.operations.update(op['id'],'failed',error=error)
                        self.runtime.store.log('error','control','management.failed',data={'operation_id':op['id'],'error':error})
                    else:
                        self.runtime.store.log('info','control','management.completed',data={'operation_id':op['id'],'action':op['action']})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.runtime.store.log('error','control','management.worker_failed',data={'error':type(exc).__name__})
            await asyncio.sleep(.5)
