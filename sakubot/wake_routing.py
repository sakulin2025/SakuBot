"""Main-wake source identity, contiguous insertion and source-change notices."""
import json
import time


def metadata(event):
    value = event.get('meta') or {}
    return json.loads(value) if isinstance(value, str) else value


def identity(event):
    data = metadata(event)
    if isinstance(data.get('conversation_source'), str) and data['conversation_source']:
        return 'conversation:' + data['conversation_source']
    if event.get('source') == 'web-chat':
        return 'web-chat'
    return 'event:' + str(event.get('source', '')) + ':' + str(event.get('target', 'main'))


def insertion_metadata(runtime, source, target, data, insertion):
    if target != 'main' or insertion == 'queue':
        return {}
    active = runtime.current_run
    active = active if active and active.get('kind') != 'compression' else None
    if insertion == 'same_source_boundary':
        if not active:
            return {}
        # Different-source requests remain pending. A deliberate source switch
        # can make them eligible at the next boundary of this same run.
    result = {'insertion_mode': insertion}
    if active:
        result['insertion_run_id'] = active['id']
    return result


def absorbable_wakes(runtime, invocation):
    now = time.time()
    rows = runtime.store.rows("SELECT * FROM events WHERE kind='wake' AND status='pending' AND (expires=0 OR expires>?) ORDER BY id", (now,))
    active_events = invocation.metadata.get('wake_events', [])
    active_source = (runtime.current_run or {}).get('wake_source') or (identity(active_events[-1]) if active_events else '')
    settings = runtime.config.settings.conversation
    if settings.wake_insertion == 'same_source_boundary' and settings.same_source_priority and active_source:
        # Only requests explicitly eligible for this active run may bypass other
        # sources. Ordinary queued requests and stale run insertions stay queued.
        return [row for row in rows if row['target'] == 'main'
            and metadata(row).get('insertion_mode') == 'same_source_boundary'
            and metadata(row).get('insertion_run_id') == invocation.run_id
            and identity(row) == active_source]
    batch_source = None
    result = []
    for row in rows:
        data = metadata(row)
        mode = data.get('insertion_mode')
        if row['target'] != 'main' or (mode not in ('next_boundary', 'same_source_boundary') and not data.get('insertion_run_id')):
            break
        source = identity(row)
        if mode == 'same_source_boundary' and (source != active_source or data.get('insertion_run_id') != invocation.run_id):
            break
        if batch_source is not None and source != batch_source:
            break
        batch_source = source
        result.append(row)
    return result


def notice_message(event):
    entry = notice_entry(metadata(event).get('source_change_notice'))
    return {**entry, '_event_id': event['id']} if entry else None


def change_source(runtime, key, invocation, *, explicit=False):
    """Switch immediately, returning a notice for insertion at a valid boundary."""
    from .wake_prompt import CHANGE_DEFAULT, context, render
    conversation = runtime.conversation
    if key not in conversation.sources:
        raise ValueError('对话源未声明，请先调用 message_sources 获取有效 ID')
    previous = runtime.store.kv_get('conversation.current', '')
    if explicit or key != previous:
        from .reply_location import clear
        clear(runtime, invocation, key)
    if key == previous:
        return False, None
    catalog = {item['id']: item for item in conversation.catalog()['items']}
    def descriptor(identifier):
        item = catalog.get(identifier, {})
        return {'id': identifier, 'name': item.get('name') or identifier or '未选择', 'available': item.get('available', False), 'trusted': item.get('trusted', False)}
    previous_source, current_source = descriptor(previous), descriptor(key)
    conversation.select(key)
    if runtime.current_run and runtime.current_run['id'] == invocation.run_id:
        runtime.current_run['wake_source'] = 'conversation:' + key
    settings = runtime.config.settings.conversation
    notice = None
    if settings.source_change_enabled:
        variables = context(runtime, invocation)
        variables.update(previous_source=previous_source, current_source=current_source)
        try:
            rendered = render(settings.source_change_template, variables, source_change=True)
        except ValueError as exc:
            runtime.store.log('warning', 'conversation', 'source_change.template.failed', run_id=invocation.run_id, data={'error': str(exc)[:500]})
            rendered = render(CHANGE_DEFAULT, variables, source_change=True)
        notice = {'text': rendered, 'mode': settings.source_change_mode, 'previous': previous, 'current': key}
    runtime.store.log('info', 'conversation', 'source.changed', run_id=invocation.run_id,
        data={'event_id': invocation.metadata.get('_main_event_id'), 'previous': previous, 'current': key})
    return True, notice


def notice_entry(notice):
    if not notice or not notice.get('text'):
        return None
    return {'role': 'user', 'content': '【主会话源变更提醒】\n' + notice['text'],
        '_temporary': notice.get('mode') == 'temporary'}


def flush_source_notices(invocation, messages):
    for notice in invocation.metadata.pop('_pending_source_notices', []):
        entry = notice_entry(notice)
        if entry:
            messages.append(entry)


def activate(runtime, event, invocation):
    """Called only when a wake starts or is claimed at a safe boundary."""
    from .source_trust import attach_warning
    data = metadata(event)
    key = data.get('conversation_source', '')
    key = key if isinstance(key, str) else ''
    if key and key in runtime.conversation.sources:
        changed, notice = change_source(runtime, key, invocation)
        if changed and notice:
            data['source_change_notice'] = notice
            runtime.store.execute('UPDATE events SET meta=? WHERE id=?', (json.dumps(data, ensure_ascii=False), event['id']))
            event = {**event, 'meta': json.dumps(data, ensure_ascii=False)}
    from .reply_location import follow
    follow(runtime, invocation, event)
    event = attach_warning(runtime, event, invocation)
    if runtime.current_run and runtime.current_run['id'] == invocation.run_id:
        runtime.current_run['wake_source'] = identity(event)
    return event
