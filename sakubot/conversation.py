"""Plugin-owned main conversation sources. Routing is resolved at delivery time."""
import asyncio
import inspect
import re
import time
import uuid

from .store import encode


PARTS = {'text', 'image', 'video', 'file', 'audio'}
EVENTS = PARTS | {'stream', 'tool', 'lifecycle'}


class Conversation:
    def __init__(self, runtime):
        self.runtime = runtime
        self.sources = {}
        self.jobs = set()

    def declare(self, owner, identifier, name, handlers, availability=None, timeout=30):
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,40}', identifier):
            raise ValueError('对话源 ID 无效')
        key = owner + '.' + identifier
        if key in self.sources or set(handlers) - EVENTS or not all(callable(fn) for fn in handlers.values()):
            raise ValueError('对话源重复或接口无效')
        self.sources[key] = {'id': key, 'plugin_id': owner, 'name': str(name)[:100],
            'handlers': dict(handlers), 'availability': availability, 'timeout': timeout, 'queue': asyncio.Queue(maxsize=256), 'worker': None}
        self.runtime.registry.revision = uuid.uuid4().hex
        return key

    def remove(self, owner, identifier):
        key = owner + '.' + identifier
        source = self.sources.pop(key, None)
        if source and source['worker']:
            source['worker'].cancel()
        if source:
            self.runtime.registry.revision = uuid.uuid4().hex

    def remove_owner(self, owner):
        for source in list(self.sources.values()):
            if source['plugin_id'] == owner:
                self.remove(owner, source['id'].split('.', 1)[1])

    def status(self, source):
        try:
            value = source['availability']() if source['availability'] else {'available': True}
            return {'available': bool(value.get('available', True)), 'reason': str(value.get('reason', ''))[:300]}
        except Exception:
            return {'available': False, 'reason': '状态获取失败'}

    def catalog(self):
        current = self.runtime.store.kv_get('conversation.current', '')
        return {'current': current, 'items': [{'id': source['id'], 'plugin_id': source['plugin_id'],
            'name': source['name'], 'capabilities': list(source['handlers']), **self.status(source)}
            for source in self.sources.values()]}

    def select(self, identifier):
        if identifier not in self.sources:
            raise ValueError('对话源未声明')
        self.runtime.store.kv_set('conversation.current', identifier)
        self.runtime.live.publish('conversation.source', current=identifier)

    def targets(self):
        settings = self.runtime.config.settings.conversation
        return ([self.runtime.store.kv_get('conversation.current', '')] if settings.mode == 'intelligent'
                else settings.targets)

    async def receive(self, owner, identifier, content, *, actor='', label='', uid=None, meta=None):
        key = owner + '.' + identifier
        if key not in self.sources:
            raise ValueError('对话源已卸载')
        if not isinstance(content, str) or not content.strip() or len(content) > 200000:
            raise ValueError('消息正文无效')
        # Replayed inbound packets must not move the current source again.
        uid = 'main-source:' + key + ':' + (uid or uuid.uuid4().hex)
        old = self.runtime.store.one('SELECT id,uid,kind,status FROM events WHERE uid=?', (uid,))
        if old:
            return old
        if self.runtime.config.settings.conversation.mode == 'intelligent':
            self.select(key)
        return await self.runtime.emit('wake', owner, content, target='main', actor=actor, label=label,
            uid=uid, priority=100, meta={**(meta or {}), 'conversation_source': key, 'role': 'user'})

    def publish(self, kind, *, response_id, run_id='', exclude=(), **data):
        packet = {'type': kind, 'response_id': response_id, 'run_id': run_id, **data}
        exclusions = set(exclude) | set(packet.pop('_exclude', []))
        # Selection is checked again by each worker immediately before the external call.
        for key in dict.fromkeys(self.targets()):
            source = self.sources.get(key)
            if not key or key in exclusions:
                continue
            if not source:
                self.record({'id': key, 'plugin_id': key.split('.')[0]}, packet, 'unavailable')
                continue
            if kind == 'tool' and not self.runtime.config.settings.conversation.tool_events:
                continue
            if kind not in source['handlers']:
                self.record(source, packet, 'unsupported')
                continue
            if not self.status(source)['available']:
                self.record(source, packet, 'unavailable')
                continue
            if source['queue'].full() and kind in PARTS:
                # Keep final content ahead of transient process updates under backpressure.
                retained = []
                while not source['queue'].empty():
                    queued = source['queue'].get_nowait()
                    source['queue'].task_done()
                    if queued['type'] in PARTS:
                        retained.append(queued)
                for queued in retained:
                    source['queue'].put_nowait(queued)
            if source['queue'].full():
                self.record(source, packet, 'failed', '对话源积压已满')
                continue
            source['queue'].put_nowait({**packet, '_exclude': list(exclusions)})
            if source['worker'] is None or source['worker'].done():
                job = asyncio.create_task(self.worker(source))
                source['worker'] = job
                self.jobs.add(job)
                job.add_done_callback(self.jobs.discard)

    def record(self, source, packet, status, error=''):
        # Stream/process successes remain transient; final parts have durable delivery records.
        if packet['type'] not in PARTS and status == 'sent':
            return
        if packet['type'] not in PARTS:
            if status not in ('unsupported', 'unavailable', 'superseded'):
                self.runtime.store.log('warning', source['plugin_id'], 'conversation.delivery.' + status,
                    run_id=packet['run_id'], data={'source': source['id'], 'type': packet['type'], 'error': error})
            return
        self.runtime.store.execute("INSERT INTO deliveries(id,target,text,action,params,status,error,at) VALUES (?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, source['id'], packet.get('text', ''), 'conversation.' + packet['type'],
             encode(packet), status, error, time.time()))

    async def worker(self, source):
        while True:
            packet = await source['queue'].get()
            if self.sources.get(source['id']) is not source:
                source['queue'].task_done()
                return
            if source['id'] not in self.targets():
                if self.runtime.config.settings.conversation.mode == 'intelligent' and packet['type'] in PARTS:
                    self.publish(packet['type'], **{key: value for key, value in packet.items() if key != 'type'})
                self.record(source, packet, 'superseded')
                source['queue'].task_done()
                continue
            handler = source['handlers'].get(packet['type'])
            if handler is None:
                self.record(source, packet, 'unsupported')
                source['queue'].task_done()
                continue
            if not self.status(source)['available']:
                self.record(source, packet, 'unavailable')
                source['queue'].task_done()
                continue
            delivery_id = uuid.uuid4().hex
            durable = packet['type'] in PARTS
            if durable:
                self.runtime.store.execute("INSERT INTO deliveries(id,target,text,action,params,status,at) VALUES (?,?,?,?,?,'sending',?)",
                    (delivery_id, source['id'], packet.get('text', ''), 'conversation.' + packet['type'], encode(packet), time.time()))
            try:
                value = handler({**{key: value for key, value in packet.items() if not key.startswith('_')}, 'delivery_id': delivery_id})
                if inspect.isawaitable(value):
                    await asyncio.wait_for(value, source['timeout'])
                if durable:
                    self.runtime.store.execute("UPDATE deliveries SET status='sent' WHERE id=?", (delivery_id,))
            except BaseException as exc:
                if durable:
                    self.runtime.store.execute("UPDATE deliveries SET status='uncertain',error=? WHERE id=?", (type(exc).__name__, delivery_id))
                else:
                    self.record(source, packet, 'failed', type(exc).__name__)
                if isinstance(exc, asyncio.CancelledError):
                    raise
            finally:
                source['queue'].task_done()

    async def respond(self, parts, *, run_id='', response_id=None, exclude=(), delivery_target=''):
        if isinstance(parts, str):
            parts = [{'type': 'text', 'text': parts}]
        if not isinstance(parts, list) or not parts or len(parts) > 30:
            raise ValueError('响应内容无效')
        for part in parts:
            if not isinstance(part, dict) or part.get('type') not in PARTS:
                raise ValueError('响应类型无效')
            field = 'text' if part['type'] == 'text' else 'url'
            if not isinstance(part.get(field), str) or not part[field].strip():
                raise ValueError('响应内容缺少 ' + field)
        parts = [{key: value for key, value in part.items() if key in ('type', 'text', 'url', 'name', 'mime')} for part in parts]
        if len(encode(parts)) > 200000:
            raise ValueError('响应过大')
        response_id = response_id or uuid.uuid4().hex
        uid = 'response:' + response_id
        if self.runtime.store.one('SELECT id FROM events WHERE uid=?', (uid,)):
            return response_id
        text = '\n'.join(part.get('text', '') for part in parts if part['type'] == 'text')
        self.runtime.store.event('context', 'agent', text, target='main', uid=uid,
            meta={'role': 'assistant', 'run_id': run_id, 'response_id': response_id, 'parts': parts,
                'delivery_target': delivery_target})
        if delivery_target:
            # Explicit destinations use plugin-owned adapters; the web receives the persisted response.
            for index, part in enumerate(parts):
                self.runtime.deliveries.enqueue_part(delivery_target, part, 'response:' + response_id + ':' + str(index))
            return response_id
        for index, part in enumerate(parts):
            self.publish(part['type'], response_id=response_id, run_id=run_id, exclude=exclude,
                part_index=index, final=True, **{key: value for key, value in part.items() if key != 'type'})
        return response_id

    def process(self, kind, **data):
        self.runtime.live.publish(kind, **data)
        if data.get('agent_id') != 'main':
            return
        current = self.runtime.current_run
        if current and current['id'] == data.get('run_id') and current.get('reply_target'):
            return
        category = 'stream' if kind.startswith('model.') else 'tool' if kind.startswith('tool.') else 'lifecycle'
        self.publish(category, response_id=data.get('request_id') or data.get('run_id', ''),
            event=kind, **data)

    async def stop(self):
        jobs = list(self.jobs)
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        self.sources.clear()
