"""Generic HA events, sharing one disposable WebSocket across all bindings."""
from .event_docs import PARAMETERS, EVENT, ID_DESCRIPTION
import asyncio
import json
import time
import uuid

import websockets
from urllib.parse import urlsplit, urlunsplit
from sakubot.plugin import object_schema


FAMILIES = {
    'entity_state_changed': '实体状态与属性变化',
    'entity_turned_on': '实体开启', 'entity_turned_off': '实体关闭',
    'entity_unavailable': '实体不可用', 'entity_available': '实体恢复可用',
    'entity_attribute_changed': '实体属性变化',
}


def register(plugin):
    watcher = EntityWatcher(plugin)

    def options():
        items = [plugin.client.entity_metadata(item) for item in plugin.client.allowed_entities().values()]
        return {'entity_id': [{'value': row['entity_id'], 'label': row['display_name'] + ' · ' + row['entity_id']} for row in items]}

    def validate(params):
        if params.get('entity_id'):
            plugin.client.entity(params['entity_id'])

    def match(event, params):
        old, new = event.get('old_state') or {}, event.get('new_state') or {}
        return (not params.get('entity_id') or event['entity_id'] == params['entity_id']) and (
            not params.get('domain') or event['entity_id'].split('.')[0] == params['domain']) and (
            not params.get('from_state') or old.get('state') == params['from_state']) and (
            not params.get('to_state') or (new.get('state') == params['to_state'] and old.get('state') != new.get('state')))

    for family, title in FAMILIES.items():
        plugin.trigger_source(family + '.*', title, PARAMETERS, EVENT, id_description=ID_DESCRIPTION,
            subscribe=watcher.subscribe, options=options, match=match, validate=validate,
            legacy_ids=(family,) if family == 'entity_state_changed' else ())


class EntityWatcher:
    def __init__(self, plugin):
        self.plugin = plugin
        self.references = set()
        self.task = None
        self.lock = asyncio.Lock()

    async def subscribe(self, params, emit):
        reference = uuid.uuid4().hex
        async with self.lock:
            self.references.add(reference)
            if not self.task or self.task.done():
                self.task = self.plugin.background(self.run())
        async def close():
            async with self.lock:
                self.references.discard(reference)
                if not self.references and self.task:
                    task, self.task = self.task, None
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
        return close

    async def publish(self, event):
        data = event.get('data', {})
        entity_id = data.get('entity_id')
        # Never broaden observation beyond the configured HA rooms/entity policies.
        if entity_id not in self.plugin.client.allowed_entities():
            return
        old, new = data.get('old_state'), data.get('new_state')
        before, after = (old or {}).get('state'), (new or {}).get('state')
        families = ['entity_state_changed']
        if before != after:
            if after == 'on': families.append('entity_turned_on')
            if after == 'off': families.append('entity_turned_off')
            if after in ('unavailable', 'unknown'): families.append('entity_unavailable')
            if before in ('unavailable', 'unknown') and after not in (None, 'unavailable', 'unknown'):
                families.append('entity_available')
        if (old or {}).get('attributes') != (new or {}).get('attributes'):
            families.append('entity_attribute_changed')
        payload = {'entity_id': entity_id, 'old_state': old, 'new_state': new, 'at': event.get('time_fired')}
        uid = str(event.get('context', {}).get('id') or uuid.uuid4().hex) + ':' + str(event.get('time_fired')) + ':' + entity_id
        for family in families:
            await self.plugin.emit_trigger(family + '.' + entity_id, payload, uid=family + ':' + uid)

    async def run(self):
        delay, logged = 5, 0
        while True:
            try:
                self.plugin.client.allowed_entities()
                base = urlsplit(self.plugin.client.base)
                url = urlunsplit(('wss' if base.scheme == 'https' else 'ws', base.netloc, base.path.rstrip('/') + '/api/websocket', '', ''))
                async with websockets.connect(url, open_timeout=15, ping_interval=20, ping_timeout=20, max_size=2**20) as ws:
                    greeting = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if greeting.get('type') != 'auth_required': raise RuntimeError('HA WebSocket 鉴权握手无效')
                    await ws.send(json.dumps({'type': 'auth', 'access_token': self.plugin.config.get('token', '')}))
                    if json.loads(await asyncio.wait_for(ws.recv(), 20)).get('type') != 'auth_ok': raise RuntimeError('HA WebSocket 鉴权失败')
                    await ws.send(json.dumps({'id': 1, 'type': 'subscribe_events', 'event_type': 'state_changed'}))
                    if not json.loads(await asyncio.wait_for(ws.recv(), 20)).get('success'): raise RuntimeError('HA 状态订阅失败')
                    delay = 5
                    async for raw in ws:
                        packet = json.loads(raw)
                        if packet.get('type') == 'event': await self.publish(packet.get('event', {}))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if time.time() - logged >= 120:
                    self.plugin.runtime.store.log('warning', self.plugin.id, 'ha.trigger.disconnected', data={'error': type(exc).__name__})
                    logged = time.time()
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)
