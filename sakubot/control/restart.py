"""Durable restart handoff. Never resume an old Python coroutine or tool call."""
import asyncio
import json
import os
import time


class Restart:
    def __init__(self, control):
        self.control, self.runtime = control, control.runtime
        self.requested = False

    @staticmethod
    def supported():
        return bool(os.environ.get('SAKUBOT_SUPERVISOR_PORT') and os.environ.get('SAKUBOT_SUPERVISOR_SECRET'))

    async def execute(self, operation):
        if not self.supported():
            raise ValueError('当前进程未由 SakuBot supervisor 启动，请使用 python -m sakubot')
        if self.runtime.current_run:
            raise RuntimeError('主智能体尚未结束，不能执行重启')
        recent=[stamp for stamp in self.runtime.store.kv_get('control:restart-times',[]) if stamp > time.time()-900]
        if len(recent)>=3:
            raise RuntimeError('15 分钟内最多重启 3 次；请先检查重复重启原因')
        self.control.operations.update(operation['id'], 'restarting')
        try:
            async with asyncio.timeout(5):
                reader, writer = await asyncio.open_connection('127.0.0.1', int(os.environ['SAKUBOT_SUPERVISOR_PORT']))
                try:
                    writer.write(json.dumps({'action':'restart', 'operation_id':operation['id'],
                        'secret':os.environ['SAKUBOT_SUPERVISOR_SECRET']}).encode() + b'\n')
                    await writer.drain()
                    reply = json.loads(await reader.readline())
                    if not reply.get('accepted'):
                        raise RuntimeError('监督进程拒绝重启；连续重启至少间隔 30 秒')
                    self.requested = True
                    self.runtime.store.kv_set('control:restart-times',recent+[time.time()])
                finally:
                    writer.close()
                    await writer.wait_closed()
        except BaseException:
            # After an ACK is uncertain the old boot must not retry a restart automatically.
            raise

    async def recover(self):
        accepted = os.environ.get('SAKUBOT_RESTART_OPERATION', '')
        rows=self.runtime.store.rows("""SELECT id FROM system_operations WHERE action='system.restart' AND boot_id<>?
            AND (status='restarting' OR (id=? AND status<>'done') OR json_extract(context,'$.resume_pending')=1)""",
            (self.control.boot_id, accepted))
        for row in rows:
            op=self.control.operations.get(row['id'],private=True)
            data=op['payload']
            resume=data.get('resume')
            if op['status']!='done':
                self.control.operations.update(op['id'],'done',result={'restarted':True,'resumed':False,'resume_pending':bool(resume),'boot_id':self.control.boot_id})
                self.runtime.store.execute("UPDATE system_operations SET context=json_set(context,'$.resume_pending',json(?)) WHERE id=?",('true' if resume else 'false',op['id']))
                self.runtime.store.log('info','control','system.restart.completed',data={'operation_id':op['id']})
            if not resume or not self.runtime.config.settings.ready():
                continue
            await self.runtime.emit('wake','system_control',
                '系统已重启。请先检查实际状态，再继续以下目标，不要重放结果不确定的操作。\n'
                + '重启原因：'+data.get('reason','')+'\n重启前进度：'+data.get('progress','')+'\n后续目标：'+resume,
                uid='system-restart-resume:'+op['id'],
                meta={'management_operation':op['id'],'resumed_after_restart':True},
                send_result_to_source=data.get('send_result_to_source',True))
            self.runtime.store.execute("UPDATE system_operations SET context=json_set(context,'$.resume_pending',json('false')) WHERE id=?",(op['id'],))
            self.control.operations.update(op['id'],'done',result={'restarted':True,'resumed':True,'resume_pending':False,'boot_id':self.control.boot_id})
