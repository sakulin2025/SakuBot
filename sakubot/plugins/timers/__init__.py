import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from datetime import datetime

from sakubot.plugin import Plugin, object_schema, text
from sakubot.store import encode


class Extension(Plugin):
    name = "timers"

    def setup(self):
        self.runtime.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS schedules (
          id TEXT PRIMARY KEY, data TEXT NOT NULL, next_at REAL NOT NULL);
        """)
        # Convert legacy aliases and compound targets once; new inputs use the enum below.
        for row in self.runtime.store.rows('SELECT id,data FROM schedules'):
            data = json.loads(row['data'])
            old = data.get('target') or 'main'
            if old == 'owner':
                data['target'] = 'main'
            elif ':' in old:
                data['target'], data['target_id'] = old.split(':', 1)
            else:
                data['target'] = old
            try:
                self.destination(data)
            except ValueError:
                data['enabled'] = False
                self.runtime.store.log('warning', self.id, 'schedule.target.invalid', data={'schedule_id': row['id']})
            self.runtime.store.execute('UPDATE schedules SET data=? WHERE id=?', (encode(data), row['id']))
        self.page("manage", "定时任务", Path(__file__).parent / "web" / "dist", icon="clock", order=10, aliases=("/schedules",))
        self.api("schedules", self.page_list)
        self.api("schedules", self.page_manage, methods=("POST",))
        self.tool("schedule_manage", "管理持久定时任务。mode=wake 唤醒主 Agent，context 仅记录，notify 仅发固定文字。target 只能是 main/private/group：main 使用主上下文并按当前主对话路由回应；private/group 必须同时提供 target_id，通知或唤醒后的最终文本固定投递到指定私聊/群，不改变主对话当前响应源。所有唤醒仍使用唯一主上下文。owner 不再接受。可指定带时区的 at，或 interval_seconds 重复。停机期间重复任务只补一次。",
            object_schema({"action": {"type": "string", "enum": ["list", "save", "delete"]},
                           "id": text("更新/删除的任务 ID，新增留空"), "name": text(), "content": text(),
                           "mode": {"type": "string", "enum": ["context", "wake", "notify"]},
                           "at": text("一次性时间，例如 2026-10-26T09:00:00+08:00"),
                           "interval_seconds": {"type": "integer", "minimum": 0, "maximum": 31536000},
                           "target": {"type": "string", "enum": ["main", "private", "group"], "default": "main", "description": "main=当前主对话路由；private=固定私聊；group=固定群聊"},
                           "target_id": text("target 为 private/group 时必填 QQ号/群号，仅数字；main 时省略"), "enabled": {"type": "boolean"},
                           "include_context": {"type": "boolean"}}, ("action",)), self.manage)

    async def page_list(self, request):
        return self.runtime.store.list_records("schedules")

    async def page_manage(self, request):
        return await self.call_tool("schedule_manage", await request.json())

    async def start(self):
        self.background(self.loop())

    @staticmethod
    def destination(data):
        target = data.get('target', 'main')
        if target not in ('main', 'private', 'group'):
            raise ValueError('target 仅支持 main、private、group；不再接受 owner 或带冒号的目标')
        if target == 'main':
            data.pop('target_id', None)
            return 'main'
        identifier = data.get('target_id', '')
        if not isinstance(identifier, str) or not re.fullmatch(r'[1-9][0-9]{0,19}', identifier):
            raise ValueError('private/group 必须提供仅含数字的 target_id')
        return target + ':' + identifier

    async def manage(self, inv, args):
        store = self.runtime.store
        if args["action"] == "list":
            return store.list_records("schedules")
        identifier = args.get("id") or uuid.uuid4().hex[:12]
        old = store.one("SELECT * FROM schedules WHERE id=?", (identifier,))
        if args["action"] == "delete":
            store.execute("DELETE FROM schedules WHERE id=?", (identifier,))
            return {"deleted": identifier}
        data = {**(json.loads(old["data"]) if old else {}), **{k: v for k, v in args.items() if k not in ("id", "action")}}
        if not data.get("name") or not data.get("content"):
            raise ValueError("请提供任务名称和内容")
        data.setdefault("enabled", True)
        data.setdefault("mode", "wake")
        data.setdefault("include_context", False)
        data.setdefault('target', 'main')
        self.destination(data)
        interval = int(data.get("interval_seconds", 0))
        if interval and interval < 30:
            raise ValueError("重复间隔至少30秒")
        if data.get("at") and interval:
            raise ValueError("一次性时间和重复间隔只选一个；改类型时清空另一个字段")
        if data.get("at"):
            at = datetime.fromisoformat(data["at"])
            if at.tzinfo is None:
                raise ValueError("时间必须带时区，例如 +08:00")
            next_at = at.timestamp()
        elif interval:
            next_at = old["next_at"] if old and "interval_seconds" not in args else time.time() + interval
        else:
            raise ValueError("请提供一次性 at 或 interval_seconds")
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
                # Deterministic event ID bridges a crash between enqueue and schedule advance.
                destination = self.destination(data)
                await self.emit(data.get("mode", "wake"), data["content"],
                    target=destination, priority=10,
                    meta={"schedule_id": row["id"], "name": data["name"], "scheduled_at": row["next_at"],
                        "reply_target": '' if destination == 'main' else destination},
                    uid=f"schedule:{row['id']}:{row['next_at']}", include_context=data.get("include_context", False))
                interval = data.get("interval_seconds", 0)
                if interval:
                    self.runtime.store.execute("UPDATE schedules SET next_at=? WHERE id=?", (now + interval, row["id"]))
                else:
                    data["enabled"] = False
                    self.runtime.store.execute("UPDATE schedules SET data=? WHERE id=?", (encode(data), row["id"]))
