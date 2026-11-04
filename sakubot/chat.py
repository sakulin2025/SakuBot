import asyncio
import json
import secrets
from urllib.parse import urlsplit

from fastapi import Depends, Query, Request, WebSocket, WebSocketDisconnect


class Chat:
    def __init__(self, runtime):
        self.runtime = runtime
        if runtime.store.kv_get('chat:boundary') is None:
            runtime.store.kv_set('chat:boundary', self.boundary())

    def boundary(self):
        value = self.runtime.store.kv_get('chat:boundary')
        if value is not None:
            return value
        # Honor context clears made before the page had a persisted boundary.
        row = self.runtime.store.one("SELECT id,at,data FROM logs WHERE source='agents' AND event='context.cleared' ORDER BY id DESC LIMIT 1")
        return {'cutoff': json.loads(row['data']).get('cutoff', 0), 'revision': row['id'], 'at': row['at']} if row else {'cutoff': 0, 'revision': 0, 'at': 0}

    def visible(self, row):
        if row['id'] <= self.boundary()['cutoff']:
            return False
        metadata = json.loads(row['meta'])
        return not metadata.get('exclude_main', False) and not (row['kind'] == 'context' and metadata.get('exclude_context', False))

    def row(self, row):
        metadata = json.loads(row['meta'])
        role = 'assistant' if metadata.get('role') == 'assistant' else 'user' if metadata.get('role') == 'user' or row['source'] == 'web-chat' else 'event'
        insertion = metadata.get('insertion_mode') == 'next_boundary' or 'insertion_run_id' in metadata
        if metadata.get('insertion_mode') == 'same_source_boundary':
            from .wake_routing import identity
            active = self.runtime.current_run or {}
            insertion = metadata.get('insertion_run_id') == active.get('id') and identity(row) == active.get('wake_source')
        stage = ('submitted' if metadata.get('wake_submitted') else 'merged') if row['status'] == 'running' else ('waiting' if insertion else 'queued') if row['status'] == 'pending' else row['status']
        return {key: row[key] for key in ('id', 'uid', 'at', 'source', 'actor', 'label', 'target', 'text', 'status', 'kind')} | {'role': role, 'meta': metadata, 'wake_stage': stage if row['kind'] == 'wake' else ''}

    def event(self, row):
        if self.visible(row):
            self.runtime.live.publish('message', message=self.row(row))

    def snapshot(self, before=0, limit=100):
        boundary = self.boundary()
        rows = self.runtime.store.rows("SELECT * FROM events WHERE id>? AND id<? AND coalesce(json_extract(meta,'$.exclude_main'),0)=0 AND (kind!='context' OR coalesce(json_extract(meta,'$.exclude_context'),0)=0) ORDER BY id DESC LIMIT ?",
            (boundary['cutoff'], before or 9223372036854775807, limit))
        activity = self.runtime.store.rows("SELECT id,at,source,event,run_id,data FROM logs WHERE run_id!='' AND at>? ORDER BY id DESC LIMIT 80", (boundary['at'],))
        for item in activity:
            item['data'] = json.loads(item['data'])
        processes = []
        if rows:
            ids = [row['id'] for row in rows]
            placeholders = ','.join('?' for _ in ids)
            runs = self.runtime.store.rows('SELECT id,event_id,status,started FROM runs WHERE event_id IN (' + placeholders + ') ORDER BY started', ids)
            for run in runs:
                entries = []
                for log in self.runtime.store.rows("SELECT at,event,data FROM logs WHERE run_id=? AND event IN ('model.request','model.completed','model.failed','compression.started','compression.failed','context.compressed') ORDER BY id", (run['id'],)):
                    data = json.loads(log['data'])
                    if log['event'] == 'model.request':
                        entries.append({'key': 'model:' + str(data.get('step', 1)), 'kind': 'model', 'at': log['at'], 'step': data.get('step', 1), 'status': 'running'})
                    elif log['event'] in ('model.completed', 'model.failed'):
                        previous = next((entry for entry in reversed(entries) if entry['kind'] == 'model' and entry['status'] == 'running'), None)
                        if previous:
                            previous['status'] = 'done' if log['event'] == 'model.completed' else 'failed'
                    elif log['event'] == 'compression.started':
                        entries.append({'key': 'compression:' + str(data.get('id', log['at'])), 'kind': 'compression', 'at': log['at'], 'status': 'running'})
                    else:
                        key = 'compression:' + str(data.get('id', log['at']))
                        entry = next((item for item in entries if item['key'] == key), None)
                        if entry:
                            entry.update(status='failed' if log['event'] == 'compression.failed' else 'done', finished=log['at'], error=data.get('error', ''))
                        else:
                            entries.append({'key': key, 'kind': 'compression', 'at': log['at'], 'status': 'failed' if log['event'] == 'compression.failed' else 'done', 'error': data.get('error', '')})
                for tool in self.runtime.store.rows('SELECT call_id,tool_name,status,arguments,output,error,started,finished FROM tool_calls WHERE run_id=? ORDER BY id', (run['id'],)):
                    try:
                        arguments = json.loads(tool['arguments'])
                    except (ValueError, TypeError):
                        arguments = tool['arguments']
                    entries.append({'key': 'tool:' + tool['call_id'], 'kind': 'tool', 'at': tool['started'], 'name': tool['tool_name'],
                        'status': tool['status'], 'finished': tool['finished'], 'arguments': arguments, 'output': tool['output'][:20000], 'error': tool['error']})
                entries.sort(key=lambda entry: entry['at'])
                processes.append({'id': run['id'], 'event_id': run['event_id'], 'status': run['status'], 'entries': entries})
        tools = []
        if self.runtime.current_run:
            for item in self.runtime.store.rows('SELECT * FROM tool_calls WHERE run_id=? ORDER BY id LIMIT 100', (self.runtime.current_run['id'],)):
                tools.append({'key': item['run_id'] + ':' + item['call_id'], 'name': item['tool_name'], 'status': item['status'],
                    'arguments': json.loads(item['arguments']), 'output': item['output'], 'error': item['error'], 'agent_id': 'main'})
        return {'context_revision': boundary['revision'], 'context_cutoff': boundary['cutoff'], 'messages': [self.row(row) for row in reversed(rows)], 'before': rows[-1]['id'] if rows else None,
            'has_more': len(rows) == limit, 'live': list(self.runtime.live.models.values()),
            'tools': tools, 'processes': processes,
            'activity': list(reversed(activity)), 'running': self.runtime.current_run,
            'enabled': self.runtime.config.settings.enabled, 'sequence': self.runtime.live.sequence}

    async def retry(self, event_id):
        store = self.runtime.store
        row = store.one('SELECT * FROM events WHERE id=?', (event_id,))
        if not row or row['kind'] != 'wake' or row['status'] != 'failed' or not self.visible(row):
            raise ValueError('只能重试当前主对话中失败的唤醒消息')
        metadata = json.loads(row['meta'])
        if metadata.get('retry_event_id'):
            existing = store.one('SELECT * FROM events WHERE id=?', (metadata['retry_event_id'],))
            return {'message': self.row(existing), 'duplicate': True}
        if not self.runtime.config.settings.enabled:
            raise ValueError('主智能体已暂停，请先启用')
        self.runtime.agents.snapshot('main')
        retry_meta = dict(metadata)
        for key in ('retry_event_id', 'exclude_context', 'exclude_main', 'rolled_back_at', 'rollback_event_id'):
            retry_meta.pop(key, None)
        retry_meta['retry_of'] = event_id
        result = await self.runtime.emit('wake', row['source'], row['text'],
            actor=row['actor'], label=row['label'], target=row['target'],
            meta=retry_meta, uid='chat-retry:' + str(event_id), priority=row['priority'],
            send_result_to_source=metadata.get('send_result_to_source', True), insertion='queue')
        # Retain the failed message for audit/UI, but do not duplicate its prompt.
        metadata.update(retry_event_id=result['id'], exclude_context=True)
        store.execute('UPDATE events SET meta=? WHERE id=?', (json.dumps(metadata, ensure_ascii=False), event_id))
        self.event(store.one('SELECT * FROM events WHERE id=?', (event_id,)))
        store.log('info', 'chat', 'wake.retried', data={'event_id': event_id, 'retry_event_id': result['id']})
        return {'message': self.row(store.one('SELECT * FROM events WHERE id=?', (result['id'],))), 'duplicate': False}

    async def send(self, text, client_id):
        if not isinstance(text, str) or not text.strip() or len(text) > 100000:
            raise ValueError('消息不能为空或超过100000字符')
        if not isinstance(client_id, str) or not 1 <= len(client_id) <= 100:
            raise ValueError('消息 ID 无效')
        old = self.runtime.store.one('SELECT * FROM events WHERE uid=?', ('web-chat:' + client_id,))
        if old:
            return {'message': self.row(old), 'duplicate': True}
        if not self.runtime.config.settings.enabled:
            raise ValueError('主 Agent 已暂停')
        self.runtime.agents.snapshot('main')
        result = await self.runtime.emit('wake', 'web-chat', text, target='main', actor='owner', label='主人',
            uid='web-chat:' + client_id, priority=100, meta={'channel': 'web'}, send_result_to_source=False,
            insertion=self.runtime.config.settings.conversation.wake_insertion)
        row = self.runtime.store.one('SELECT * FROM events WHERE id=?', (result['id'],))
        return {'message': self.row(row), 'duplicate': False}


def register_chat_api(app, authorize, runtime, config):
    @app.get('/api/conversation-sources', dependencies=[Depends(authorize)])
    async def sources():
        return runtime.conversation.catalog()

    @app.put('/api/conversation-sources/trust', dependencies=[Depends(authorize)])
    async def set_source_trust(request: Request):
        data = await request.json()
        if not isinstance(data, dict) or set(data) != {'source_id', 'trusted'}:
            raise ValueError('信任设置无效')
        runtime.conversation.set_trust(data['source_id'], data['trusted'])
        return runtime.conversation.catalog()

    @app.put('/api/conversation-sources/current', dependencies=[Depends(authorize)])
    async def select_source(request: Request):
        data = await request.json()
        runtime.conversation.select(data.get('id', ''))
        return runtime.conversation.catalog()

    @app.get('/api/chat', dependencies=[Depends(authorize)])
    async def history(before: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
        return runtime.chat.snapshot(before, limit)

    @app.post('/api/chat', dependencies=[Depends(authorize)])
    async def send(request: Request):
        data = await request.json()
        return await runtime.chat.send(data.get('text'), data.get('client_id'))

    @app.post('/api/chat/stop', dependencies=[Depends(authorize)])
    async def stop(request: Request):
        data = await request.json()
        return await runtime.stop_main_run(data.get('run_id'))

    @app.websocket('/api/chat/live')
    async def live(socket: WebSocket):
        origin = socket.headers.get('origin')
        if origin and urlsplit(origin).netloc.lower() != socket.headers.get('host', '').lower():
            await socket.close(code=4403)
            return
        await socket.accept()
        queue = None
        writer = None
        token = ''
        try:
            auth = await asyncio.wait_for(socket.receive_json(), 10)
            token = auth.get('token', '') if isinstance(auth, dict) else ''
            if not isinstance(token, str) or not secrets.compare_digest(token.encode(), config.token.encode()):
                await socket.close(code=4401)
                return
            queue = runtime.live.subscribe()
            await socket.send_json({'type': 'snapshot', **runtime.chat.snapshot()})

            async def write():
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), 20)
                    except TimeoutError:
                        event = {'type': 'ping'}
                    if event.get('type') == 'resync':
                        while not queue.empty():
                            queue.get_nowait()
                        event = {'type': 'snapshot', **runtime.chat.snapshot()}
                    if not secrets.compare_digest(token.encode(), config.token.encode()):
                        await socket.close(code=4401)
                        return
                    await asyncio.wait_for(socket.send_json(event), 15)

            writer = asyncio.create_task(write())
            async def read():
                while True:
                    packet = await socket.receive_json()
                    if not isinstance(packet, dict):
                        continue
                    if not secrets.compare_digest(token.encode(), config.token.encode()):
                        await socket.close(code=4401)
                        return
                    if packet.get('type') == 'send':
                        try:
                            result = await runtime.chat.send(packet.get('text'), packet.get('client_id'))
                            await queue.put({'type': 'ack', 'client_id': packet.get('client_id'), **result})
                        except (ValueError, RuntimeError) as exc:
                            await queue.put({'type': 'send.error', 'client_id': packet.get('client_id'), 'error': str(exc)[:500]})
            reader = asyncio.create_task(read())
            try:
                await asyncio.wait((writer, reader), return_when=asyncio.FIRST_COMPLETED)
            finally:
                writer.cancel(); reader.cancel()
                await asyncio.gather(writer, reader, return_exceptions=True)
        except (WebSocketDisconnect, TimeoutError, ValueError, RuntimeError):
            pass
        finally:
            if queue is not None:
                runtime.live.clients.discard(queue)
            if writer:
                writer.cancel()
