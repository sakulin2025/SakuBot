import json
import time
import uuid

from ..store import encode


def redact(value):
    if isinstance(value, dict):
        return {key: ('***' if (key.lower() in ('authorization','token','secret','password','api_key') or key.lower().endswith(('_token','_secret','_password','_api_key')))
                      else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class Operations:
    def __init__(self, store, boot_id):
        self.store, self.boot_id = store, boot_id
        store.db.executescript('''CREATE TABLE IF NOT EXISTS system_operations (
            id TEXT PRIMARY KEY, action TEXT NOT NULL, status TEXT NOT NULL,
            created REAL NOT NULL, updated REAL NOT NULL, boot_id TEXT NOT NULL,
            run_id TEXT NOT NULL, requester TEXT NOT NULL, payload TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '{}', result TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '', logs TEXT NOT NULL DEFAULT '');
            CREATE INDEX IF NOT EXISTS system_operations_queue ON system_operations(status,created);''')
        if 'context' not in {row['name'] for row in store.rows('PRAGMA table_info(system_operations)')}:
            store.execute("ALTER TABLE system_operations ADD COLUMN context TEXT NOT NULL DEFAULT '{}'")
        store.execute("UPDATE system_operations SET status='interrupted',updated=?,error='进程中断；未自动重放，先检查实际状态' WHERE status='running'", (time.time(),))

    def create(self, action, payload, run_id='', requester='console', context=None):
        identifier = uuid.uuid4().hex
        now = time.time()
        self.store.execute('INSERT INTO system_operations(id,action,status,created,updated,boot_id,run_id,requester,payload,context) VALUES(?,?,\'queued\',?,?,?,?,?,?,?)',
            (identifier, action, now, now, self.boot_id, run_id, requester, encode(payload), encode(context or {})))
        return self.get(identifier)

    def get(self, identifier, private=False):
        row = self.store.one('SELECT * FROM system_operations WHERE id=?', (identifier,))
        if not row:
            raise ValueError('管理操作不存在')
        row['payload'], row['result'], row['context'] = json.loads(row['payload']), json.loads(row['result']), json.loads(row['context'])
        return row if private else redact(row)

    def list(self, limit=100):
        return [self.get(row['id']) for row in self.store.rows('SELECT id FROM system_operations ORDER BY created DESC LIMIT ?', (limit,))]

    def update(self, identifier, status, *, result=None, error=''):
        self.store.execute('UPDATE system_operations SET status=?,updated=?,result=?,error=? WHERE id=?',
            (status, time.time(), encode(result or {}), error[:1000], identifier))

    def log(self, identifier, message):
        self.store.execute('UPDATE system_operations SET logs=substr(logs || ?,-30000),updated=? WHERE id=?',
            (str(message), time.time(), identifier))

    def cancel(self, identifier):
        if not self.store.execute("UPDATE system_operations SET status='cancelled',updated=? WHERE id=? AND status='queued'", (time.time(), identifier)).rowcount:
            raise ValueError('仅可取消尚未执行的管理操作')
        return self.get(identifier)
