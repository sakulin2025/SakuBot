"""Build per-script SDK snapshots from event and tool declarations."""
import fnmatch
import re
from .typing_codegen import TypeWriter, safe_name


def event_contracts(runtime, sources):
    contracts, unknown = {}, []
    for source_id in sources:
        declaration = runtime.scripts.sources.resolve(source_id)
        if not declaration:
            unknown.append(source_id)
        else:
            contracts[source_id] = declaration['event_schema']
    return contracts, unknown


def development(runtime, *, sources=(), parameters=None, tool_plugins=None):
    writer = TypeWriter()
    contracts, unknown = event_contracts(runtime, sources)
    for index, (source, schema) in enumerate(contracts.items()):
        writer.alias('SourceData' + str(index), schema)
    if not contracts or unknown:
        writer.lines.append('UnknownEventData: TypeAlias = dict[str, object]\n')
    types = ['SourceData' + str(index) for index in range(len(contracts))]
    if not contracts or unknown:
        types.append('UnknownEventData')
    writer.lines.append('EventData: TypeAlias = ' + ' | '.join(types) + '\n')
    writer.alias('ScriptParams', parameters or {'type':'object','properties':{},'additionalProperties':False})
    selected = None if tool_plugins is None else set(tool_plugins)
    tools = {}
    for tool in runtime.registry.tools.values():
        if tool.audience == 'main' or (selected is not None and tool.plugin_id not in selected):
            continue
        if not runtime.registry.availability(tool.plugin_id)['available']:
            continue
        if not re.fullmatch(r'[a-zA-Z_]\w*',tool.plugin_id) or not re.fullmatch(r'[a-zA-Z_]\w*',tool.name) or safe_name(tool.plugin_id)!=tool.plugin_id or safe_name(tool.name)!=tool.name:
            continue
        tools.setdefault(tool.plugin_id,[]).append(tool)
    unknown_results = []
    for owner, entries in sorted(tools.items()):
        methods = []
        for tool in sorted(entries,key=lambda tool:tool.name):
            props = tool.parameters.get('properties',{})
            if any(not key.isidentifier() or safe_name(key)!=key or key=='self' for key in props):
                continue
            arguments = []
            for key, value in props.items():
                annotation = writer.type(value, owner+'_'+tool.name+'_'+key)
                arguments.append(key + ': ' + annotation + ('' if key in tool.parameters.get('required',[]) else ' = ...'))
            result = writer.type(tool.result_schema or {},owner+'_'+tool.name+'Result')
            if not tool.result_schema:
                unknown_results.append(owner + '.' + tool.name)
            methods.append('    async def ' + tool.name + '(self' + (', *, ' + ', '.join(arguments) if arguments else '') + ') -> ' + result + ': ...\n')
        writer.lines.append('class ' + safe_name(owner) + 'Tools:\n' + (''.join(methods) or '    pass\n'))
    writer.lines.append('class Tools:\n' + (''.join('    '+owner+': '+safe_name(owner)+'Tools\n' for owner in sorted(tools)) or '    pass\n'))
    writer.lines.append('from sakubot.automation.sdk import Context\n\nclass ScriptContext(Context[EventData, ScriptParams]):\n    tools: Tools\n')
    return {'sdk':writer.source(), 'event_contracts':contracts, 'unknown_sources':unknown,
        'unknown_results':unknown_results, 'sources':list(sources),
        'example':'from script_types import ScriptContext\n\nasync def main(ctx: ScriptContext) -> object:\n    data = ctx.event["data"]\n    ctx.log("事件到达", source=ctx.event["source"])\n    return data\n',
        'conventions':{'ctx':'Context 类实例','ctx.event':'普通 dict；使用 ctx.event["data"]，不能用 .data',
            'ctx.params':'普通 dict，使用下标读取必填字段，get 读取可选字段','ctx.state':'State 实例，使用 get/set/delete',
            'tools':'await ctx.tools.<插件ID>.<函数名>(参数名=值)，仅脚本可调用工具；未声明结果类型返回 object'}}


def validate_event(script, event):
    import jsonschema
    if not isinstance(event,dict) or not isinstance(event.get('source'),str) or not isinstance(event.get('id'),str) or type(event.get('at')) not in (int,float) or not isinstance(event.get('data'),dict):
        raise ValueError('事件必须是含 id:string、source:string、at:Unix秒数、data:dict 的字典')
    sources = script.get('event_sources',[])
    if sources and not any(fnmatch.fnmatchcase(event['source'],source) for source in sources):
        raise ValueError('事件来源不符合脚本声明；手动运行事件脚本需提供匹配来源的完整 event 样本')
    matches = [(key,value) for key,value in script.get('event_contracts',{}).items() if fnmatch.fnmatchcase(event['source'],key)]
    if matches:
        _, schema = max(matches,key=lambda item:len(item[0].replace('*','')))
        try:
            jsonschema.validate(event['data'],schema)
        except jsonschema.ValidationError as exc:
            raise ValueError('事件 data 不符合脚本保存时的类型：' + '.'.join(map(str,exc.absolute_path)) + '：' + exc.message) from None
