"""Per-run subordinate reply position; queued automatic output shares this live cell."""
import copy


def cell(runtime, invocation):
    value=invocation.metadata.get('_reply_location')
    if value is None:
        value={'source_id':'','context':{}}
        invocation.metadata['_reply_location']=value
    current=runtime.current_run
    if current and current['id']==invocation.run_id:current['_reply_location']=value
    return value


def clear(runtime, invocation, source_id):
    value=cell(runtime,invocation)
    value.clear()
    value.update(source_id=source_id,context={})


def follow(runtime, invocation, event):
    from .wake_routing import metadata
    data=metadata(event)
    source_id=data.get('conversation_source') or runtime.store.kv_get('conversation.current','')
    context=data.get('reply_context')
    context=context if data.get('conversation_source')==source_id and isinstance(context,dict) else {}
    value=cell(runtime,invocation)
    value.clear()
    value.update(source_id=source_id,context=copy.deepcopy(context))


def resolve(value, source_id):
    return copy.deepcopy(value.get('context',{})) if value and value.get('source_id')==source_id else {}


def describe(runtime, invocation):
    value=cell(runtime,invocation)
    source_id=runtime.store.kv_get('conversation.current','')
    source=runtime.conversation.sources.get(source_id)
    if not source:return ''
    plugin=next((p for p in runtime.registry.plugins if p.id==source['plugin_id']),None)
    callback=getattr(plugin,'reply_context_prompt',None)
    return callback(resolve(value,source_id)) if callback else ''
