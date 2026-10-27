import json
import re
import sqlite3
import time
import uuid


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    """Single-process SQLite store. Mutations are synchronous and short; never await in a transaction."""
    def __init__(self, root):
        self.on_event = None
        self.on_log = None
        self.db = sqlite3.connect(root / "sakubot.sqlite3")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, uid TEXT UNIQUE NOT NULL, at REAL NOT NULL,
          kind TEXT NOT NULL, source TEXT NOT NULL, actor TEXT NOT NULL,
          label TEXT NOT NULL, target TEXT NOT NULL, text TEXT NOT NULL,
          meta TEXT NOT NULL, status TEXT NOT NULL,
          priority INTEGER NOT NULL, expires REAL NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS queue ON events(status, priority, id);
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, event_id INTEGER, started REAL, finished REAL,
          status TEXT, trace TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS deliveries (
          id TEXT PRIMARY KEY, target TEXT NOT NULL, text TEXT NOT NULL,
          action TEXT NOT NULL, params TEXT NOT NULL, status TEXT NOT NULL,
          result TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS processed_messages (
          id INTEGER PRIMARY KEY, uid TEXT UNIQUE NOT NULL, at REAL NOT NULL, session_id TEXT NOT NULL, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS processed_messages_session ON processed_messages(session_id,id);
        CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS logs (
          id INTEGER PRIMARY KEY, at REAL NOT NULL, level TEXT NOT NULL,
          source TEXT NOT NULL, event TEXT NOT NULL, run_id TEXT NOT NULL,
          tool_call_id INTEGER, data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS logs_run ON logs(run_id,id);
        CREATE TABLE IF NOT EXISTS tool_calls (
          id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, call_id TEXT NOT NULL,
          tool_name TEXT NOT NULL, plugin_id TEXT NOT NULL,
          origin TEXT NOT NULL, arguments TEXT NOT NULL, output TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL, started REAL NOT NULL, finished REAL, error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS calls_run ON tool_calls(run_id,id);

        """)
        for table, column in (("events", "authority"), ("tool_calls", "authority")):
            if column in {row["name"] for row in self.db.execute("PRAGMA table_info(" + table + ")")}:
                self.db.execute("ALTER TABLE " + table + " DROP COLUMN " + column)
        self.db.execute("PRAGMA user_version=5")
        # A crash may occur after an external action; do not replay uncertain work.
        self.db.execute("UPDATE events SET status='interrupted', error='进程中断，需人工检查后决定是否重新唤醒' WHERE status IN ('running','waiting')")
        self.db.execute("UPDATE runs SET status='interrupted', finished=? WHERE status IN ('running','waiting')", (time.time(),))
        self.db.execute("UPDATE deliveries SET status='uncertain', error='进程中断，远端结果未知，不自动重试' WHERE status='sending'")
        self.db.execute("UPDATE tool_calls SET status='interrupted',finished=?,error='进程中断，结果可能未知' WHERE status IN ('running','waiting')", (time.time(),))
        self.db.commit()

    def rows(self, sql, args=()):
        return [dict(row) for row in self.db.execute(sql, args)]

    def one(self, sql, args=()):
        row = self.db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def execute(self, sql, args=()):
        cursor = self.db.execute(sql, args)
        self.db.commit()
        return cursor

    def event(self, kind, source, text, *, actor="", label="", target="", meta=None,
              uid=None, priority=20, expires=0, status=None):
        uid = uid or uuid.uuid4().hex
        cursor = self.execute("""INSERT OR IGNORE INTO events
          (uid,at,kind,source,actor,label,target,text,meta,status,priority,expires)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            uid, time.time(), kind, source, str(actor), label, target, text, encode(meta or {}),
            status or ("pending" if kind == "wake" else "recorded"), priority, expires))
        row = self.one("SELECT * FROM events WHERE uid=?", (uid,))
        if cursor.rowcount and self.on_event:
            self.on_event(row)
        return row

    def claim(self):
        now = time.time()
        self.db.execute("UPDATE events SET status='expired' WHERE status='pending' AND expires>0 AND expires<?", (now,))
        row = self.one("""SELECT * FROM events WHERE status='pending'
          ORDER BY priority + min(30, (? - at)/120) DESC, id ASC LIMIT 1""", (now,))
        if row:
            self.db.execute("UPDATE events SET status='running' WHERE id=?", (row["id"],))
        self.db.commit()
        return row

    def kv_get(self, key, default=None):
        row = self.one("SELECT value FROM kv WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def kv_set(self, key, value):
        self.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, encode(value)))

    def log(self, level, source, event, *, run_id="", tool_call_id=None, data=None):
        at = time.time()
        identifier = self.execute("INSERT INTO logs (at,level,source,event,run_id,tool_call_id,data) VALUES (?,?,?,?,?,?,?)",
            (at, level, source, event, run_id, tool_call_id, encode(data or {}))).lastrowid
        if self.on_log:
            self.on_log({'id': identifier, 'at': at, 'source': source, 'event': event, 'run_id': run_id, 'data': data or {}})
        return identifier

    def list_records(self, table):
        if not isinstance(table, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', table):
            raise ValueError("未知记录类型")
        if 'data' not in {row['name'] for row in self.rows('PRAGMA table_info(' + table + ')')}:
            raise ValueError('记录表没有 data 字段')
        return [{**row, "data": json.loads(row["data"])} for row in self.rows(f"SELECT * FROM {table}")]
