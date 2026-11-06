"""Current plugin documentation for script authors, without generated SDKs."""
import inspect
import json
from pathlib import Path

HELPERS = {
    'script_wake': 'await tools["script_wake"](content, data=None, send_result_to_source=True)：唤醒主智能体。',
    'script_notify': 'await tools["script_notify"](content, send_result_to_source=True, include_context=False)：发送固定通知。',
    'script_log': 'tools["script_log"](message, **data)：同步写执行日志。',
    'script_state_get': 'tools["script_state_get"](key, default=None)：同步读取该脚本的持久状态。',
    'script_state_set': 'tools["script_state_set"](key, value)：同步保存该脚本的 JSON 状态。',
    'script_state_delete': 'tools["script_state_delete"](key)：同步删除该脚本的状态。',
}
EXAMPLE = '''async def main(ctx, event, tools):
    tools["script_log"]("事件到达", source=event["source"])
    return {"source": event["source"], "data": event["data"]}
'''


def plugin_directory(runtime, owner):
    plugin = next((p for p in runtime.registry.plugins if p.id == owner), None)
    return Path(inspect.getfile(type(plugin))).parent if plugin else None


def tool_documentation(runtime, tool):
    root = plugin_directory(runtime, tool.plugin_id)
    path = root/'tool_documentation.json' if root else None
    if path and path.is_file():
        try:
            return json.loads(path.read_text()).get(tool.name, {})
        except (ValueError, OSError):
            pass
    return {}


def tools(runtime, *, plugin='', query='', selected=None):
    return [{'plugin':tool.plugin_id, **tool.schema()['function'], **tool_documentation(runtime, tool)}
            for tool in runtime.registry.tools.values()
            if tool.audience != 'main' and (not plugin or tool.plugin_id == plugin)
            and (selected is None or tool.plugin_id in selected)
            and (not query or query.casefold() in (tool.name+' '+tool.description).casefold())
            and runtime.registry.availability(tool.plugin_id)['available']]


def development(runtime, *, sources=(), parameters=None, tool_plugins=None):
    entries = tools(runtime, selected=tool_plugins)
    owners = sorted({item['plugin'] for item in entries})
    plugin_docs = []
    for owner in owners:
        root = plugin_directory(runtime, owner)
        files = []
        if root:
            paths = list((root/'skills').rglob('*.md')) if (root/'skills').is_dir() else []
            paths += [root/'README.md'] if (root/'README.md').is_file() else []
            for path in sorted(paths):
                files.append({'path':str(path.relative_to(root)), 'content':path.read_text(errors='replace')})
        plugin_docs.append({'plugin':owner,'files':files})
    events = []
    for source in sources:
        definition = runtime.scripts.sources.resolve(source)
        events.append({key:value for key,value in definition.items() if key in ('id','name','parameters','event_schema','id_description')}
                      if definition else {'id':source,'declared':False})
    return {'instructions':'每次新建或修改脚本，都必须重新查阅本次返回的当前插件文档、工具说明和相关事件说明。不得使用记忆或上次开发经验猜测方法名、参数、返回字段。文档未说明时先读取插件源码或询问，不自行编造。',
        'entrypoint':'main(ctx, event, tools)',
        'ctx':{'run_id':'运行ID','script_id':'脚本ID','workspace':'共享工作空间目录','data_dir':'脚本数据目录','params':'本次参数，普通字典'},
        'event':{'id':'事件ID','source':'来源ID','at':'Unix秒','data':'插件提供的普通字典'},
        'helpers':HELPERS,'example':EXAMPLE,'parameters':parameters or {},
        'events':events,'tools':entries,'plugins':plugin_docs}
