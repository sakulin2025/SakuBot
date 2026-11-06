"""Internal JSONL transport. Public script arguments are ordinary dictionaries."""
import asyncio
import json


class ScriptToolError(RuntimeError):
    pass


class Connection:
    def __init__(self, boot, output, input_stream):
        self.boot, self.output, self.input_stream = boot, output, input_stream
        self.lock = asyncio.Lock()
        self.number = 0
        self.state = dict(boot['state'])

    def send(self, packet):
        self.output.write(json.dumps(packet, ensure_ascii=False, allow_nan=False) + '\n')
        self.output.flush()

    async def rpc(self, op, **arguments):
        async with self.lock:
            self.number += 1
            self.send({'op':op,'id':self.number,**arguments})
            line = await asyncio.to_thread(self.input_stream.readline)
            if not line:
                raise RuntimeError('框架连接已关闭')
            packet = json.loads(line)
            if packet.get('id') != self.number:
                raise RuntimeError('脚本通信顺序无效')
            if not packet.get('ok'):
                raise ScriptToolError(packet.get('error') or '调用失败')
            return packet.get('result')

    def arguments(self):
        ctx = {key:self.boot[key] for key in ('run_id','script_id','workspace','data_dir','params')}
        def remote(name):
            async def invoke(**arguments):
                return await self.rpc('call', tool=name, arguments=arguments)
            return invoke
        tools = {name:remote(name) for name in self.boot['tools']}
        async def wake(content, *, data=None, send_result_to_source=True):
            return await self.rpc('wake', content=content, data=data, send_result_to_source=send_result_to_source)
        async def notify(content, *, send_result_to_source=True, include_context=False):
            return await self.rpc('notify', content=content, send_result_to_source=send_result_to_source, include_context=include_context)
        def log(message, **data):
            self.send({'op':'log','message':str(message),'data':data})
        def set_state(key, value):
            self.state[key] = value
            self.send({'op':'state','values':self.state})
        def delete_state(key):
            self.state.pop(key, None)
            self.send({'op':'state','values':self.state})
        helpers = {'script_wake':wake,'script_notify':notify,'script_log':log,
                   'script_state_get':self.state.get,'script_state_set':set_state,'script_state_delete':delete_state}
        if tools.keys() & helpers.keys():
            raise RuntimeError('脚本运行方法名称冲突')
        tools.update(helpers)
        return ctx, self.boot['event'], tools
