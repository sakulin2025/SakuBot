"""Worker-side SDK. Protocol stdout is separate from user prints."""
import asyncio
import json
import sys


class ScriptToolError(RuntimeError):
    pass


class State:
    def __init__(self, context, values):
        self.context, self.values = context, values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value
        self.context.send({'op':'state','values':self.values})

    def delete(self, key):
        self.values.pop(key, None)
        self.context.send({'op':'state','values':self.values})


class Context:
    def __init__(self, boot, output, input_stream):
        self.params = boot['params']
        self.event = boot['event']
        self.run_id = boot['run_id']
        self.script_id = boot['script_id']
        self.workspace = boot['workspace']
        self.data_dir = boot['data_dir']
        self.state = State(self, boot['state'])
        self.output, self.input_stream = output, input_stream
        self.lock = asyncio.Lock()
        self.number = 0

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

    async def call(self, plugin, tool, arguments=None):
        return await self.rpc('call', plugin=plugin, tool=tool, arguments=arguments or {})

    async def wake(self, content, *, data=None, send_result_to_source=True):
        return await self.rpc('wake', content=content, data=data, send_result_to_source=send_result_to_source)

    async def notify(self, content, *, send_result_to_source=True, include_context=False):
        return await self.rpc('notify', content=content, send_result_to_source=send_result_to_source, include_context=include_context)

    def log(self, message, **data):
        self.send({'op':'log','message':str(message),'data':data})
