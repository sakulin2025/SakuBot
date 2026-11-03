"""Detect new training records and publish durable framework triggers only."""
import asyncio
import hashlib
import time
from datetime import datetime, timezone


def parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        t = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return t.replace(tzinfo=timezone.utc).timestamp() if t.tzinfo is None else t.timestamp()
    except ValueError:
        return None


def row_summary(row):
    return {key: row.get(key) for key in ('id', 'name', 'source', 'sources', 'start_time', 'end_time', 'duration_sec')}


def workout_group(row, seen):
    identifier = str(row.get('id') or '')
    start = parse_time(row.get('start_time'))
    if not identifier:
        return None
    for key, item in seen.items():
        if identifier in item.get('ids', []):
            return key
    name = str(row.get('name') or '').strip().casefold()
    for key, item in seen.items():
        if name and start is not None and item.get('start') is not None and name == item.get('name') and abs(start - item['start']) <= 300:
            return key
    return hashlib.sha256((identifier + ':' + str(start)).encode()).hexdigest()[:24]


class Polling:
    def setup_polling(self):
        self.poll_wakeup = asyncio.Event()
        self.poll_error = ''
        self.next_poll = None
        self.poll_lock = asyncio.Lock()

    def settings_saved(self):
        self.poll_wakeup.set()

    async def poll_loop(self):
        while True:
            try:
                if not self.config.get('poll_enabled', False):
                    self.next_poll = None
                    await self.poll_wakeup.wait()
                    self.poll_wakeup.clear()
                    continue
                self.next_poll = time.time() + int(self.config.get('poll_interval_minutes', 5)) * 60
                await self.poll_once()
                try:
                    await asyncio.wait_for(self.poll_wakeup.wait(), timeout=int(self.config.get('poll_interval_minutes', 5)) * 60)
                    self.poll_wakeup.clear()
                except TimeoutError:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.poll_error = str(exc)[:300] if isinstance(exc, ValueError) else type(exc).__name__
                self.runtime.store.log('warning', self.id, 'freereps.poll.failed', data={'error': self.poll_error})
                try:
                    await asyncio.wait_for(self.poll_wakeup.wait(), timeout=60)
                    self.poll_wakeup.clear()
                except TimeoutError:
                    pass

    async def poll_once(self):
        async with self.poll_lock:
            base = self.config.get('base_url', '').rstrip('/')
            snapshot = self.state.get('monitor', {})
            if snapshot.get('base_url') != base:
                snapshot = {'base_url': base, 'baseline': False, 'seen': {}}
            now = time.time()
            lookback = int(self.config.get('lookback_days', 7))
            begin = datetime.fromtimestamp(now - lookback * 86400, timezone.utc).isoformat()
            end = datetime.fromtimestamp(now + 60, timezone.utc).isoformat()
            records = await self.client.workouts(begin, end)
            if not self.config.get('poll_enabled') or self.config.get('base_url', '').rstrip('/') != base:
                return
            seen = snapshot.setdefault('seen', {})
            outbox = snapshot.setdefault('trigger_pending', {})
            baseline = snapshot.get('baseline', False)
            for row in reversed(records):
                group = workout_group(row, seen)
                if not group:
                    continue
                identifier = str(row['id'])
                current = seen.get(group)
                if current:
                    if identifier not in current['ids']:
                        current['ids'].append(identifier)
                    current['last_seen'] = now
                    continue
                seen[group] = {'ids': [identifier], 'start': parse_time(row.get('start_time')),
                    'name': str(row.get('name') or '').strip().casefold(), 'last_seen': now}
                if baseline:
                    uid = 'workout-added:' + hashlib.sha256(base.encode()).hexdigest()[:12] + ':' + group
                    outbox[uid] = {'workout': row_summary(row), 'observed_at': now}
            snapshot['baseline'] = True
            snapshot['last_poll_at'] = now
            snapshot['seen'] = {key: value for key, value in seen.items() if now - value.get('last_seen', now) <= max(31, lookback * 2) * 86400}
            # Commit observations and pending events together before handing off to the framework.
            self.state.set('monitor', snapshot)
            for uid, payload in list(outbox.items()):
                if not self.config.get('poll_enabled') or self.config.get('base_url', '').rstrip('/') != base:
                    break
                await self.emit_trigger('workout_added.' + str(payload['workout']['id']), payload, uid=uid)
                outbox.pop(uid)
                self.state.set('monitor', snapshot)
            self.poll_error = ''
