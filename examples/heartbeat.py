"""Copy to data/plugins/heartbeat.py and append heartbeat to enabled plugins.

An example event source which records context once an hour. It does not wake a model.
Local plugins are trusted Python code with the same process permissions as SakuBot.
"""
import asyncio
from datetime import datetime, timezone

from sakubot.plugin import Plugin, object_schema


class Extension(Plugin):
    name = "heartbeat"

    def setup(self):
        self.tool("heartbeat_time", "读取当前 UTC 时间", object_schema(), self.now)

    async def now(self, invocation, arguments):
        return {"utc": datetime.now(timezone.utc).isoformat()}

    async def start(self):
        self.background(self.loop())

    async def loop(self):
        while True:
            await asyncio.sleep(3600)
            await self.emit("context", "心跳事件：SakuBot 运行中。")
