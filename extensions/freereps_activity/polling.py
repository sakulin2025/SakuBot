import asyncio
import hashlib
import time
import uuid
from datetime import datetime, timezone, timedelta
from .client import local_times, LOCAL_ZONE


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
    if not identifier or start is None:
        return None
    for key, item in seen.items():
        if identifier in item.get('ids', []):
            return key
    name = str(row.get('name') or '').strip().casefold()
    for key, item in seen.items():
        if name and name == item.get('name') and abs(start - item.get('start', 0)) <= 300:
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
                snapshot = {'base_url': base, 'baseline': False, 'seen': {}, 'pending': {}, 'history': []}
            now = time.time()
            lookback = int(self.config.get('lookback_days', 7))
            begin = datetime.fromtimestamp(now - lookback * 86400, timezone.utc).isoformat()
            end = datetime.fromtimestamp(now + 60, timezone.utc).isoformat()
            records = await self.client.workouts(begin, end)
            if not self.config.get('poll_enabled') or self.config.get('base_url', '').rstrip('/') != base:
                return
            seen = snapshot.setdefault('seen', {})
            pending = snapshot.setdefault('pending', {})
            baseline = snapshot.get('baseline', False)
            rules = self.state.get('rules', {})
            for row in reversed(records):
                group = workout_group(row, seen)
                if not group:
                    continue
                identifier = str(row['id'])
                start = parse_time(row.get('start_time'))
                ended = parse_time(row.get('end_time'))
                current = seen.get(group)
                if current:
                    if identifier not in current['ids']:
                        current['ids'].append(identifier)
                    current['last_seen'] = now
                    newly_completed = not current.get('completed', True) and ended is not None and ended <= now
                    if not newly_completed:
                        continue
                    current['completed'] = True
                else:
                    seen[group] = {'ids': [identifier], 'start': start, 'name': str(row.get('name') or '').strip().casefold(),
                        'last_seen': now, 'completed': ended is not None and ended <= now}
                if not baseline or ended is None or ended > now or now - ended > int(self.config.get('max_age_hours', 24)) * 3600:
                    continue
                self.publish_trigger('workout_completed', {'workout':row_summary(row),'observed_at':now},uid='workout:'+group)
                for rule in rules.values():
                    if not rule.get('enabled'):
                        continue
                    wanted = rule.get('workout_type', '').strip().casefold()
                    if wanted and wanted not in str(row.get('name') or '').casefold():
                        continue
                    key = rule['id'] + ':' + group
                    pending[key] = {'uid': 'freereps:' + key, 'rule_id': rule['id'], 'mode': rule['mode'],
                        'prompt': rule.get('prompt', ''), 'notify_text': rule.get('notify_text', ''),
                        'include_context': rule.get('include_context', False), 'workout': row_summary(row),
                        'observed_at': now, 'ready_at': now + int(rule.get('delay_minutes', 0)) * 60}
            snapshot['baseline'] = True
            snapshot['last_poll_at'] = now
            snapshot['seen'] = {key: value for key, value in seen.items() if now - value.get('last_seen', now) <= max(31, lookback * 2) * 86400}
            self.state.set('monitor', snapshot)
            self.poll_error = ''
            self.publish_trigger('sync_completed', {'count':len(records),'observed_at':now},uid='sync:'+str(now))
            await self.deliver_pending(snapshot)

    async def deliver_pending(self, snapshot):
        rules = self.state.get('rules', {})
        now = time.time()
        for key, item in list(snapshot.get('pending', {}).items()):
            rule = rules.get(item['rule_id'])
            if not rule or not rule.get('enabled') or not self.config.get('poll_enabled'):
                continue
            if item['ready_at'] > now:
                continue
            workout = local_times(item['workout'])
            text = ('FreeReps 检测到一条新的训练记录。记录何时同步不代表训练刚刚结束。\n'
                + '训练类型：' + str(workout.get('name') or '未知') + '\n训练结束：' + str(workout.get('end_time') or '未知')
                + '\n训练 ID：' + str(workout.get('id') or '未知'))
            if item['mode'] == 'wake' and item.get('prompt'):
                text += '\n处理要求：' + item['prompt']
            if item['mode'] == 'notify':
                text = item.get('notify_text') or '发现新的训练记录。'
            uid = item['uid']
            recorded_uid = 'notify:' + uid if item['mode'] == 'notify' else uid
            try:
                # The event is committed before pending is removed; after restart its stable UID avoids duplicate delivery.
                if not self.event_status(recorded_uid):
                    await self.emit(item['mode'], text, target='main', uid=uid,
                        include_context=item.get('include_context', False) if item['mode'] == 'notify' else False,
                        meta={'freereps_workout': workout, 'observed_at': datetime.fromtimestamp(item['observed_at'], LOCAL_ZONE).isoformat()})
                snapshot['pending'].pop(key, None)
                snapshot.setdefault('history', []).insert(0, {'id': uid, 'name': workout.get('name', ''),
                    'ended_at': workout.get('end_time', ''), 'at': now, 'mode': item['mode'], 'status': '已提交'})
                snapshot['history'] = snapshot['history'][:100]
                self.state.set('monitor', snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.poll_error = '事件提交失败：' + (str(exc)[:200] if isinstance(exc, ValueError) else type(exc).__name__)
                self.runtime.store.log('warning', self.id, 'freereps.event.failed', data={'error': self.poll_error})
