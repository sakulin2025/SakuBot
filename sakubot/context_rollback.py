"""Rollback the model timeline without deleting operational audit records."""
import json
import time

from .store import encode


def rollback(runtime, event_id, revision):
    instance = runtime.agents.get('main')
    store = runtime.store
    if runtime.current_run or instance.busy or instance.resetting or store.one(
            "SELECT id FROM events WHERE kind='wake' AND status='pending' AND (expires=0 OR expires>?) LIMIT 1", (time.time(),)):
        raise RuntimeError('主对话正在运行或有待处理消息，请先停止运行并处理队列')
    boundary = runtime.chat.boundary()
    if revision != boundary['revision']:
        raise RuntimeError('会话已改变，请刷新后重新选择回退位置')
    row = store.one('SELECT * FROM events WHERE id=?', (event_id,))
    if not row or not runtime.chat.visible(row) or row['kind'] != 'wake':
        raise ValueError('请选择有效的唤醒消息作为回退位置')
    memo = store.kv_get('agent:main-summary', {'cutoff': 0, 'text': ''})
    if event_id <= memo['cutoff']:
        raise RuntimeError('这条消息已纳入历史摘要，无法单独回退；可选择摘要之后的消息或清除上下文')
    # An absorbed wake belongs to its original turn; never split a tool chain.
    meta = json.loads(row['meta'])
    if meta.get('absorbed_run_id'):
        parent = store.one('SELECT event_id FROM runs WHERE id=?', (meta['absorbed_run_id'],))
        if parent and parent['event_id'] < event_id:
            raise RuntimeError('该消息已合并到较早轮次，请从该轮最初的唤醒消息回退')
    rows = store.rows('SELECT id,meta,status FROM events WHERE id>=?', (event_id,))
    updated = {**boundary, 'revision': boundary['revision'] + 1}
    with store.db:
        for item in rows:
            metadata = json.loads(item['meta'])
            metadata.update(exclude_context=True, exclude_main=True, rolled_back_at=time.time(), rollback_event_id=event_id)
            store.db.execute('UPDATE events SET meta=? WHERE id=?', (encode(metadata), item['id']))
        for key, value in (('chat:boundary', updated), ('agent:history:main', []), ('agent:pending:main', [])):
            store.db.execute('INSERT OR REPLACE INTO kv(key,value) VALUES (?,?)', (key, encode(value)))
    instance.history, instance.pending = [], []
    runtime.live.models.clear()
    store.log('warning', 'agents', 'context.rolled_back', data={'event_id': event_id, 'affected': len(rows), 'revision': updated['revision']})
    runtime.live.publish('context.cleared', agent_id='main', **updated)
    return runtime.chat.snapshot()
