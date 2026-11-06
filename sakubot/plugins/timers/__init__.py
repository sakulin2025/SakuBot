from .tool_arguments import ARGUMENTS
from .tool_types import R_schedule_manage
from .tool_types import RESULTS
import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sakubot.plugin import Plugin, object_schema, text
from sakubot.store import encode


class Extension(Plugin):
    tool_result_types = RESULTS
    tool_argument_types = ARGUMENTS
    name = "timers"

    def setup(self):
        self.runtime.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS schedules (
          id TEXT PRIMARY KEY, data TEXT NOT NULL, next_at REAL NOT NULL);
        """)
        # Preserve old explicit destinations for review; never silently redirect them.
        for row in self.runtime.store.rows('SELECT id,data FROM schedules'):
            data = json.loads(row['data'])
            target = data.get('target') or 'main'
            if target not in ('main', 'owner'):
                data['legacy_target'] = target + (':' + str(data.get('target_id')) if data.get('target_id') and ':' not in target else '')
                data['enabled'] = False
                self.runtime.store.log('warning', self.id, 'schedule.legacy_target.paused', data={'schedule_id': row['id']})
            data['target'] = 'main'
            data.pop('target_id', None)
            data.setdefault('send_result_to_source', True)
            self.runtime.store.execute('UPDATE schedules SET data=? WHERE id=?', (encode(data), row['id']))
        from .triggers import register
        register(self)
        self.page("manage", "定时任务", Path(__file__).parent / "web" / "dist", icon="clock", order=10, aliases=("/schedules",), group_id='system')
        self.api("schedules", self.page_list)
        self.api("script-options", self.script_options)
        self.api("schedules", self.page_manage, methods=("POST",))
        self.tool("schedule_manage", "管理主会话定时任务。mode=wake 唤醒主智能体，context 加入上下文，notify 显示固定通知，script 执行脚本而不调用模型。script 模式提供 script_id 和 script_params，无需 content。时间可选带时区的 at、interval_seconds 间隔或 daily_time 每天当地时间，三选一。send_result_to_source 控制唤醒结果或通知是否发送到当前主对话源；网页始终显示。每天任务指定 IANA timezone，默认 Asia/Shanghai；停机期间重复任务只触发一次。",
            None, self.manage)

    def script_references(self, identifier):
        return bool(self.runtime.store.one("SELECT id FROM schedules WHERE json_extract(data,'$.mode')='script' AND json_extract(data,'$.script_id')=? LIMIT 1", (identifier,)))

    async def script_options(self, request):
        return self.runtime.scripts.repo.list("scripts")

    async def page_list(self, request):
        return self.runtime.store.list_records("schedules")

    async def page_manage(self, request):
        return await self.call_tool("schedule_manage", await request.json())

    async def start(self):
        self.background(self.loop())

    @staticmethod
    def next_daily(clock, zone_name, after):
        if not isinstance(clock, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', clock):
            raise ValueError('每日时间格式须为 HH:MM')
        try:
            zone = ZoneInfo(zone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValueError('时区无效，请使用 IANA 时区名称')
        hour, minute = map(int, clock.split(':'))
        day = datetime.fromtimestamp(after, zone).date()
        for offset in range(370):
            date = day + timedelta(days=offset)
            local = datetime(date.year, date.month, date.day, hour, minute, tzinfo=zone, fold=0)
            # Skip nonexistent local times at spring DST transitions.
            if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                continue
            if local.timestamp() > after:
                return local.timestamp()
        raise ValueError('无法计算下一次每日触发时间')

    async def manage(self, inv, args) -> R_schedule_manage:
        store = self.runtime.store
        if args["action"] == "list":
            return store.list_records("schedules")
        identifier = args.get("id") or uuid.uuid4().hex[:12]
        old = store.one("SELECT * FROM schedules WHERE id=?", (identifier,))
        if args["action"] == "delete":
            store.execute("DELETE FROM schedules WHERE id=?", (identifier,))
            return {"deleted": identifier}
        data = {**(json.loads(old["data"]) if old else {}), **{k: v for k, v in args.items() if k not in ("id", "action")}}
        if not data.get("name") or (data.get("mode", "wake") != "script" and not data.get("content")):
            raise ValueError("请提供任务名称和内容")
        data.setdefault("enabled", True)
        data.setdefault("mode", "wake")
        data.setdefault("include_context", False)
        if args.get('target') not in (None, '', 'main', 'owner') or args.get('target_id'):
            raise ValueError('定时任务只支持主会话，请使用 send_result_to_source 控制是否报告')
        data['target'] = 'main'
        data.pop('target_id', None)
        data.pop('legacy_target', None)
        data.setdefault('send_result_to_source', True)
        if not isinstance(data['send_result_to_source'], bool):
            raise ValueError('是否发送到主对话源须为布尔值')
        if data['mode'] not in ('wake', 'context', 'notify', 'script'):
            raise ValueError('事件类型无效')
        if data['mode'] == 'script':
            import jsonschema
            script = self.runtime.scripts.repo.get(data.get('script_id'))
            jsonschema.validate(data.get('script_params', {}), script['parameters'])
        interval = int(data.get('interval_seconds') or 0)
        daily = data.get('daily_time') or ''
        if interval < 0 or interval > 31536000 or (interval and interval < 30):
            raise ValueError('重复间隔须在 30 至 31536000 秒之间')
        if sum(bool(x) for x in (data.get('at'), interval, daily)) != 1:
            raise ValueError('一次性时间、重复间隔和每日时间须且只能选择一个')
        if data.get('at'):
            at = datetime.fromisoformat(data['at'])
            if at.tzinfo is None:
                raise ValueError('时间必须带时区，例如 +08:00')
            next_at = at.timestamp()
        elif interval:
            unchanged = old and json.loads(old['data']).get('interval_seconds') == interval and not json.loads(old['data']).get('at') and not json.loads(old['data']).get('daily_time')
            next_at = old['next_at'] if unchanged else time.time() + interval
        else:
            zone = data.get('timezone') or 'Asia/Shanghai'
            data['timezone'] = zone
            candidate = self.next_daily(daily, zone, time.time())
            previous = json.loads(old['data']) if old else {}
            unchanged = old and previous.get('daily_time') == daily and (previous.get('timezone') or 'Asia/Shanghai') == zone
            next_at = old['next_at'] if unchanged else candidate
        store.execute("INSERT OR REPLACE INTO schedules VALUES (?,?,?)", (identifier, encode(data), next_at))
        return {"id": identifier, "data": data, "next_at": next_at}

    async def loop(self):
        while True:
            await asyncio.sleep(1)
            now = time.time()
            for row in self.runtime.store.rows("SELECT * FROM schedules WHERE next_at<=? AND json_extract(data,'$.enabled')=1 ORDER BY next_at LIMIT 100", (now,)):
                data = json.loads(row["data"])
                if not data.get("enabled", True):
                    continue
                try:
                    # Deterministic ID bridges a crash between enqueue and schedule advance.
                    if data.get('mode') == 'script':
                        self.runtime.scripts.enqueue(data['script_id'], params=data.get('script_params', {}),
                            event={'source':'timers.schedule','id':row['id'],'at':now,'data':{'scheduled_at':row['next_at']}},
                            uid=f"timer-script:{row['id']}:{row['next_at']}")
                    else:
                        await self.emit(data.get('mode', 'wake'), data['content'],
                            target='main', priority=10,
                            meta={'schedule_id': row['id'], 'name': data['name'], 'scheduled_at': row['next_at']},
                            uid=f"schedule:{row['id']}:{row['next_at']}", include_context=data.get('include_context', False),
                            send_result_to_source=data.get('send_result_to_source', True) if data.get('mode', 'wake') != 'context' else True)
                    interval = data.get('interval_seconds', 0)
                    if interval:
                        self.runtime.store.execute('UPDATE schedules SET next_at=? WHERE id=?', (now + interval, row['id']))
                    elif data.get('daily_time'):
                        next_at = self.next_daily(data['daily_time'], data.get('timezone') or 'Asia/Shanghai', now)
                        self.runtime.store.execute('UPDATE schedules SET next_at=? WHERE id=?', (next_at, row['id']))
                    else:
                        data['enabled'] = False
                        self.runtime.store.execute('UPDATE schedules SET data=? WHERE id=?', (encode(data), row['id']))
                except Exception as exc:
                    data['enabled'] = False
                    self.runtime.store.execute('UPDATE schedules SET data=? WHERE id=?', (encode(data), row['id']))
                    self.runtime.store.log('error', self.id, 'schedule.failed', data={'schedule_id': row['id'], 'error': str(exc)})
