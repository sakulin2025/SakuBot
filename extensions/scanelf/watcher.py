"""One disposable WebSocket connection shared by every script binding."""
import asyncio
import hashlib
import time
import uuid
from contextlib import aclosing

from .client import PluginError, normalize_mac


class DeviceWatcher:
    def __init__(self, plugin):
        self.plugin = plugin
        self.references = set()
        self.task = None
        self.lock = asyncio.Lock()

    async def subscribe(self, params, emit):
        # Publish once to the source; the framework filters and fans out to bindings.
        reference = uuid.uuid4().hex
        async with self.lock:
            self.references.add(reference)
            if not self.task or self.task.done():
                self.task = self.plugin.background(self.run())

        async def close():
            async with self.lock:
                self.references.discard(reference)
                if not self.references:
                    task, self.task = self.task, None
                    if task:
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
        return close

    async def reconnect(self):
        async with self.lock:
            task, self.task = self.task, None
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if self.references:
                self.task = self.plugin.background(self.run())

    @staticmethod
    def index(rows):
        result = {}
        for row in rows:
            mac = normalize_mac(row.get('mac'))
            if not mac or type(row.get('online')) is not bool or mac in result:
                raise PluginError('ScanElf 设备 MAC 或在线状态无效。')
            if not row.get('ignored'):
                result[mac] = row
        return result

    async def devices(self, snapshot):
        rows = snapshot['items']
        if snapshot['total'] > len(rows):
            # The server caps WS frames at 500 devices. Complete a changed snapshot
            # through the paginated API; absent rows must never imply "offline".
            rows = await self.plugin.client.devices(refresh=True)
        return self.index(rows)

    async def publish(self, previous, current, packet):
        _, memories = await self.plugin.memories()
        base = hashlib.sha256(self.plugin.client.base_url().encode()).hexdigest()[:12]
        for mac, row in current.items():
            before = previous.get(mac)
            if before is not None and before['online'] == row['online']:
                continue
            payload = {'mac': mac, 'online': row['online'],
                'previous_online': before['online'] if before else None,
                'device': self.plugin.enrich(row, memories), 'at': time.time()}
            families = ['device_discovered'] if before is None else ['device_state_changed', 'device_online' if row['online'] else 'device_offline']
            uid = 'scanelf-ws:' + base + ':' + mac + ':' + str(row['online']) + ':' + str(packet.get('sent_at') or uuid.uuid4().hex)
            for family in families:
                await self.plugin.emit_trigger(family + '.' + mac, payload, uid=family + ':' + uid)

    async def run(self):
        delay = 5
        last_warning = 0
        last_connected = 0
        while True:
            connected_at = None
            previous = None
            snapshot = None
            announced = False
            try:
                async with aclosing(self.plugin.client.stream()) as packets:
                    async for packet in packets:
                        if not announced:
                            connected_at = time.monotonic()
                            if not last_connected or connected_at - last_connected >= 120:
                                self.plugin.runtime.store.log('info', self.plugin.id, 'scanelf.trigger.connected')
                                last_connected = connected_at
                            announced = True
                        if packet['type'] == 'snapshot':
                            snapshot = packet
                        info = self.plugin.client.status_info(packet)
                        if not info['data_reliable']:
                            # Do not turn scanner downtime or stale observations into transitions.
                            previous = None
                            continue
                        if snapshot is None:
                            continue
                        if packet['type'] == 'heartbeat' and previous is not None:
                            continue
                        current = await self.devices(snapshot)
                        if not self.plugin.client.status_info(packet)['data_reliable']:
                            previous = None
                            continue
                        if previous is not None:
                            await self.publish(previous, current, packet)
                        previous = current
                raise PluginError('ScanElf WebSocket 已关闭。')
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if connected_at is not None and time.monotonic() - connected_at >= 60:
                    delay = 5
                if time.monotonic() - last_warning >= 120 or not last_warning:
                    error = str(exc) if isinstance(exc, PluginError) else type(exc).__name__
                    self.plugin.runtime.store.log('warning', self.plugin.id, 'scanelf.trigger.disconnected',
                        data={'error': error, 'retry_seconds': delay})
                    last_warning = time.monotonic()
            # A new connection creates a baseline; disconnect gaps are not invented events.
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)
