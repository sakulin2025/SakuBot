"""Source trust is granted by authenticated administration or a trusted wake.

Selection of an output source is never evidence of input authority. Absorbing an
untrusted input permanently revokes trust-management authority for that wake.
"""
import json


def metadata(event):
    value = event.get('meta') or {}
    return json.loads(value) if isinstance(value, str) else value


def trusted_input(runtime, event):
    data = metadata(event)
    key = data.get('conversation_source')
    if isinstance(key, str) and key:
        return bool(data.get('source_trusted_at_receive', False)) and runtime.conversation.is_trusted(key)
    # The web console is an authenticated management surface, not an external source.
    return event.get('source') == 'web-chat'


def observe(runtime, invocation, event):
    if '_trust_origin' not in invocation.metadata:
        invocation.metadata['_trust_origin'] = event
    if not trusted_input(runtime, event):
        invocation.metadata['_trust_tainted'] = True


def may_manage(runtime, invocation):
    if invocation.agent_id != 'main' or invocation.origin != 'agent' or invocation.metadata.get('_trust_tainted'):
        return False
    events = invocation.metadata.get('wake_events', [])
    origin = invocation.metadata.get('_trust_origin') or (events[0] if events else None)
    return bool(origin and trusted_input(runtime, origin)
        and all(trusted_input(runtime, event) for event in events))


def attach_warning(runtime, event, invocation):
    from .wake_prompt import RISK_DEFAULT, context, render
    observe(runtime, invocation, event)
    data = metadata(event)
    key = data.get('conversation_source')
    if not key or trusted_input(runtime, event):
        return event
    try:
        warning = render(runtime.config.settings.conversation.untrusted_source_template, context(runtime, invocation))
        if not warning:
            raise ValueError('风险警告渲染结果为空')
    except ValueError as exc:
        runtime.store.log('warning', 'conversation', 'source_risk.template.failed', run_id=invocation.run_id, data={'error': str(exc)[:500]})
        warning = render(RISK_DEFAULT, context(runtime, invocation))
    data['source_risk_warning'] = warning
    encoded = json.dumps(data, ensure_ascii=False)
    runtime.store.execute('UPDATE events SET meta=? WHERE id=?', (encoded, event['id']))
    return {**event, 'meta': encoded}
