"""Per-wake delivery control for the main agent; destinations are source IDs."""


def rename_delivery_tools(value):
    if not isinstance(value, str):
        return value
    return value.replace('report_to_owner', 'message_enable_delivery').replace('cancel_report', 'message_disable_delivery')


def install(runtime, invocation):
    from .plugin import Tool, object_schema

    async def set_delivery(inv, enabled):
        inv.send_result_to_source = enabled
        if runtime.current_run and runtime.current_run['id'] == inv.run_id:
            runtime.current_run['send_result_to_source'] = enabled
        return {'ok': True, 'send_result_to_source': enabled,
            'targets': runtime.conversation.targets(), 'web_synced': True}

    async def enable(inv, args):
        return await set_delivery(inv, True)

    async def disable(inv, args):
        return await set_delivery(inv, False)

    for name, description, handler in (
        ('message_enable_delivery', '开启本轮向当前主会话源自动投递最终回复及支持的过程事件。目的地不一定是主人私聊；先核对当前源和内容的保密边界。只影响当前轮，网页始终可见。原工具名 report_to_owner 已更名，请使用本函数。', enable),
        ('message_disable_delivery', '关闭本轮向主会话源自动投递最终回复及过程事件；网页始终可见，不撤回已发送内容，也不阻止显式消息发送。原工具名 cancel_report 已更名，请使用本函数。', disable),
    ):
        invocation.temporary_tools[name] = Tool(name, description, object_schema(), handler, plugin_id='messaging')
