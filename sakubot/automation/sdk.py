"""Worker-side SDK. Protocol stdout is separate from user prints."""
import asyncio
import json
import sys
from typing import Any, Generic, cast
from .types import DataT, ParamsT, Event


class ScriptToolError(RuntimeError):
    pass


class State:
    def __init__(self, context, values):
        self.context, self.values = context, values

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value
        self.context.send({'op':'state','values':self.values})

    def delete(self, key: str) -> None:
        self.values.pop(key, None)
        self.context.send({'op':'state','values':self.values})


class _ToolNamespace:
    def __init__(self, context, plugin):
        self.context, self.plugin = context, plugin

    def __getattr__(self, name):
        async def call(**arguments):
            return await self.context.call(self.plugin, name, arguments)
        return call


class _Tools:
    def __init__(self, context):
        self.context = context

    def __getattr__(self, plugin):
        return _ToolNamespace(self.context, plugin)


class Context(Generic[DataT, ParamsT]):
    params: ParamsT
    event: Event[DataT]
    tools: Any
    run_id: str
    script_id: str
    workspace: str
    data_dir: str
    state: State

    def __init__(self, boot, output, input_stream):
        self.params = cast(ParamsT, boot['params'])
        self.event = cast(Event[DataT], boot['event'])
        self.tools = _Tools(self)
        self.run_id = boot['run_id']
        self.script_id = boot['script_id']
        self.workspace = boot['workspace']
        self.data_dir = boot['data_dir']
        self.state = State(self, boot['state'])
        self.output, self.input_stream = output, input_stream
        self.lock = asyncio.Lock()
        self.number = 0

    def send(self, packet: dict[str, Any]) -> None:
        self.output.write(json.dumps(packet, ensure_ascii=False, allow_nan=False) + '\n')
        self.output.flush()

    async def rpc(self, op: str, **arguments: Any) -> Any:
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

    async def call(self, plugin: str, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self.rpc('call', plugin=plugin, tool=tool, arguments=arguments or {})

    async def wake(self, content: str, *, data: Any = None, send_result_to_source: bool = True) -> dict[str, Any]:
        return await self.rpc('wake', content=content, data=data, send_result_to_source=send_result_to_source)

    async def notify(self, content: str, *, send_result_to_source: bool = True, include_context: bool = False) -> dict[str, Any]:
        return await self.rpc('notify', content=content, send_result_to_source=send_result_to_source, include_context=include_context)

    def log(self, message: str, **data: Any) -> None:
        self.send({'op':'log','message':str(message),'data':data})
