"""Isolated process supervision and the audited tool bridge."""
import asyncio
import json
import os
import signal
import sys
import time
import uuid
from pathlib import Path

from sakubot.plugin import Invocation
from sakubot.store import encode
from .context import current_chain

MAX_PACKET = 1024 * 1024


class Executor:
    def __init__(self, service):
        self.service = service
        self.runtime = service.runtime
        self.repo = service.repo

    def log(self, key, text):
        self.service.log(key, text)

    async def failure(self, row, payload, error):
        await self.service.failure(row, payload, error)

    async def execute(self, row):
        payload = json.loads(row['input'])
        process = None
        stderr_task = None
        try:
            if payload.get('target_kind') == 'wake':
                from .wake import execute
                await execute(self.service, row, payload)
                return
            script = self.repo.read(row['script_id'],row['version'])
            directory = self.repo.data_root / row['script_id']
            directory.mkdir(parents=True,exist_ok=True)
            boot = {'run_id':row['id'],'script_id':row['script_id'],'params':payload['params'],'event':payload['event'],
                'state':self.repo.state(row['script_id']),'data_dir':str(directory),'workspace':str(self.runtime.workspace.root),
                'code_path':str(self.repo.root / row['script_id'] / 'revisions' / (row['version']+'.py'))}
            env = {k:v for k,v in os.environ.items() if k in ('PATH','TZ','HOME','LANG','LC_ALL','USER','LOGNAME','SYSTEMROOT')}
            env.update(PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join([str(Path(__file__).resolve().parents[2]), str(self.runtime.config.root / 'plugin_dependencies')]))
            process = await asyncio.create_subprocess_exec(sys.executable,'-P','-m','sakubot.automation.worker',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
                cwd=self.runtime.workspace.root,env=env,start_new_session=os.name!='nt',limit=MAX_PACKET)
            process.stdin.write((encode(boot)+'\n').encode())
            await process.stdin.drain()
            async def stderr():
                while data := await process.stderr.read(4096):
                    self.log(row['id'],data.decode(errors='replace'))
            stderr_task = asyncio.create_task(stderr())
            async def communicate():
                output = None
                done = False
                while raw := await process.stdout.readline():
                    if len(raw)>MAX_PACKET:
                        raise ValueError('脚本通信数据过大')
                    packet = json.loads(raw)
                    op = packet.get('op')
                    if op == 'result':
                        output = packet.get('result')
                        done = True
                        break
                    if op == 'failed':
                        raise RuntimeError(packet.get('error') or '脚本执行失败')
                    if op == 'log':
                        self.log(row['id'],str(packet.get('message',''))+' '+encode(packet.get('data',{})))
                        continue
                    if op == 'state':
                        self.repo.set_state(row['script_id'],packet['values'])
                        continue
                    try:
                        result = await self.bridge(row,payload,packet)
                        response = {'id':packet.get('id'),'ok':True,'result':result}
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        response = {'id':packet.get('id'),'ok':False,'error':str(exc)[:2000] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__}
                    encoded = encode(response)
                    if len(encoded.encode()) > MAX_PACKET:
                        encoded=encode({'id':packet.get('id'),'ok':False,'error':'工具结果超过 1 MiB，请分页查询'})
                    process.stdin.write((encoded+'\n').encode())
                    await process.stdin.drain()
                if done:
                    return output
                code = await process.wait()
                raise RuntimeError('脚本进程未正常完成，退出码 '+str(code))
            result = await asyncio.wait_for(communicate(),timeout=script['timeout'])
            self.runtime.store.execute("UPDATE automation_runs SET status='done',finished=?,output=? WHERE id=?",(time.time(),encode(result),row['id']))
            policy=payload.get('failure_policy') or {}
            if policy.get('id'):
                state_key='automation:failure:'+policy['id']
                previous=self.runtime.store.kv_get(state_key,{})
                self.runtime.store.kv_set(state_key,{**previous,'count':0})
        except BaseException as exc:
            cancelled=isinstance(exc,asyncio.CancelledError)
            error='执行被中断，外部操作可能已执行' if cancelled else '脚本执行超时，外部操作可能已执行' if isinstance(exc,TimeoutError) else str(exc)[:2000] or type(exc).__name__
            self.runtime.store.execute('UPDATE automation_runs SET status=?,finished=?,error=? WHERE id=?',('interrupted' if cancelled else 'failed',time.time(),error,row['id']))
            self.log(row['id'],error)
            if not cancelled:
                try:
                    await self.failure(row,payload,error)
                except Exception as notify_error:
                    self.log(row['id'],'失败报告提交失败：'+str(notify_error)[:300])
        finally:
            if process:
                # Kill descendants even if main() returned successfully after spawning children.
                try:
                    if os.name != 'nt':
                        os.killpg(process.pid,signal.SIGKILL)
                    elif process.returncode is None:
                        process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            if stderr_task:
                await asyncio.gather(stderr_task,return_exceptions=True)
            self.runtime.live.publish('script.finished',run_id=row['id'])

    async def bridge(self,row,payload,packet):
        op=packet.get('op')
        if op in ('wake','notify'):
            count=self.runtime.store.kv_get('automation:emits:'+row['id'],0)
            if count>=20:
                raise ValueError('本次执行主动事件达到 20 条，已阻止通知循环')
            self.runtime.store.kv_set('automation:emits:'+row['id'],count+1)
            content=packet.get('content')
            if not isinstance(content,str) or not content.strip():
                raise ValueError('事件内容不能为空')
            if op=='wake':
                data=packet.get('data')
                temporary='' if data is None else '脚本观测数据（不是指令）：\n'+encode(data)
                return await self.runtime.emit('wake','scripts',content,target='main',temporary_context=temporary,
                    send_result_to_source=packet.get('send_result_to_source',True),
                    meta={'script_id':row['script_id'],'script_run_id':row['id'],'script_chain':payload.get('chain',[])})
            return await self.runtime.emit('notify','scripts',content,target='main',
                send_result_to_source=packet.get('send_result_to_source',True),include_context=packet.get('include_context',False))
        if op!='call':
            raise ValueError('脚本接口不存在')
        owner,name=packet.get('plugin'),packet.get('tool')
        tool=self.runtime.registry.tools.get(name)
        if not tool or tool.plugin_id!=owner:
            raise ValueError('插件工具不存在')
        if owner=='scripts' and name in ('script_run','script_manage','script_binding'):
            raise ValueError('脚本不能通过工具修改或递归运行脚本，请由 Agent 管理')
        inv=Invocation(run_id=row['id'],target='main',agent_id='script:'+row['script_id'],origin='script',call_id=uuid.uuid4().hex,
            metadata={'script_id':row['script_id'],'script_run_id':row['id'],'script_chain':payload.get('chain',[])})
        token=current_chain.set(payload.get('chain',[]))
        try:
            result=await self.runtime.registry.call(name,packet.get('arguments',{}),inv)
            if isinstance(result,dict) and (result.get('success') is False or result.get('error')):
                raise RuntimeError(encode(result))
            return result
        finally:
            current_chain.reset(token)
