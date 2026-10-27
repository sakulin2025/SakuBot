import time
from pathlib import Path

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    name = "memory"

    def setup(self):
        self.runtime.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
          key TEXT PRIMARY KEY, text TEXT NOT NULL,
          source TEXT NOT NULL, updated REAL NOT NULL);
        """)
        if "scope" in {row["name"] for row in self.runtime.store.rows("PRAGMA table_info(memories)")}:
            self.runtime.store.execute("ALTER TABLE memories DROP COLUMN scope")
        self.page("manage", "长期记忆", Path(__file__).parent / "web" / "dist", icon="memory", order=10, aliases=("/memories",))
        self.api("memories", self.page_list)
        self.api("memories", self.page_write, methods=("POST",))
        self.tool("memory_search", "检索统一长期记忆，按关键词查找或列出最近记录。",
            object_schema({"query": text("关键词，留空列出最近记录"),
                           "limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
            self.search)
        self.tool("memory_write", "记录或更新用户要求、人物关系和重要经历。保留信息来源，不把猜测写成事实。key 为可维护的唯一名字，delete=true 删除。",
            object_schema({"key": text(), "text": text(), "source": text(),
                           "delete": {"type": "boolean"}}, ("key",)), self.write)
        self.tool("event_search", "检索同一经历中的历史事件、群聊和工具完成记录。可指定来源会话、关键词和序号，按时间倒序分页。",
            object_schema({"query": text(), "target": text(), "before": {"type": "integer", "minimum": 0},
                           "limit": {"type": "integer", "minimum": 1, "maximum": 50}}),
            self.events)

    def context(self, invocation):
        return self.runtime.store.rows("SELECT * FROM memories ORDER BY updated DESC LIMIT 60")

    async def page_list(self, request):
        return self.runtime.store.rows("SELECT * FROM memories ORDER BY updated DESC LIMIT 500")

    async def page_write(self, request):
        return await self.call_tool("memory_write", await request.json())

    async def search(self, inv, args):
        rows = self.runtime.store.rows("SELECT * FROM memories WHERE (instr(key,?)>0 OR instr(text,?)>0) ORDER BY updated DESC LIMIT 500",
                                       (args.get("query", ""), args.get("query", "")))
        return rows[:args.get("limit", 20)]

    async def write(self, inv, args):
        key = args["key"].strip()
        if not key or len(key) > 200:
            raise ValueError("记忆 key 需为1到200字符")
        if args.get("delete"):
            self.runtime.store.execute("DELETE FROM memories WHERE key=?", (key,))
            return {"deleted": key}
        content = args.get("text", "").strip()
        if not content or len(content) > 20000:
            raise ValueError("记忆正文需为1到20000字符")
        self.runtime.store.execute("INSERT OR REPLACE INTO memories (key,text,source,updated) VALUES (?,?,?,?)",
            (key, content, args.get("source") or ("run:" + inv.run_id), time.time()))
        return {"saved": key}

    async def events(self, inv, args):
        before = args.get("before") or 9223372036854775807
        query, target = args.get("query", ""), args.get("target", "")
        rows = self.runtime.store.rows("""SELECT * FROM events WHERE id<? AND instr(text,?)>0
          AND (?='' OR target=?) ORDER BY id DESC LIMIT ?""", (before, query, target, target, args.get("limit", 20)))
        return {"items": rows, "next_before": rows[-1]["id"] if rows else None}
