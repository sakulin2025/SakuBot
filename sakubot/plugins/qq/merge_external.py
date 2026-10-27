"""Offline deployment migration from the retired external_reply plugin."""
import json
import os
from pathlib import Path
import sqlite3
import time


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as file:
        file.write(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def migrate(root):
    root = Path(root)
    path = root / 'config.json'
    config = json.loads(path.read_text())
    db = sqlite3.connect(root / 'sakubot.sqlite3')
    row = db.execute("SELECT value FROM kv WHERE key='external_reply:config'").fetchone()
    needs = 'external_reply' in config.get('plugins', []) or row is not None or any(key.startswith('external_reply:') for key in config.get('agent_settings', {}))
    if not needs:
        db.close()
        print('QQ 合并迁移已完成。')
        return
    backup = root / 'migrations' / ('before-qq-merge-' + str(time.time_ns()))
    write(backup / 'config.json', config)
    archive = sqlite3.connect(backup / 'sakubot.sqlite3')
    db.backup(archive)
    archive.close()
    os.chmod(backup / 'sakubot.sqlite3', 0o600)
    enabled = 'external_reply' in config.get('plugins', [])
    config['plugins'] = [key for key in config.get('plugins', []) if key != 'external_reply']
    if enabled and 'qq' not in config['plugins']:
        config['plugins'].append('qq')
    preferences = config.get('agent_settings', {})
    for local_id in ('judge', 'summarizer'):
        old, new = 'external_reply:' + local_id, 'qq:' + local_id
        if old in preferences:
            preferences.setdefault(new, preferences.pop(old))
    with db:
        if not db.execute("SELECT 1 FROM kv WHERE key='qq:external_reply'").fetchone():
            data = json.loads(row[0]) if row else {'templates': [], 'sessions': []}
            data['enabled'] = enabled
            db.execute('INSERT INTO kv(key,value) VALUES (?,?)', ('qq:external_reply', json.dumps(data, ensure_ascii=False)))
        db.execute("DELETE FROM kv WHERE key='external_reply:config'")
        for local_id in ('judge', 'summarizer'):
            for prefix in ('agent:history:', 'agent:pending:'):
                old, new = prefix + 'external_reply:' + local_id, prefix + 'qq:' + local_id
                if not db.execute('SELECT 1 FROM kv WHERE key=?', (new,)).fetchone():
                    db.execute('UPDATE kv SET key=? WHERE key=?', (new, old))
        for key in ('personas', 'team:members'):
            record = db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
            if not record:
                continue
            value = json.loads(record[0])
            profiles = value.values() if key == 'personas' else [item.get('persona') or {} for item in value]
            for profile in profiles:
                visible = profile.get('visible_plugins')
                if isinstance(visible, list) and 'external_reply' in visible:
                    profile['visible_plugins'] = list(dict.fromkeys('qq' if item == 'external_reply' else item for item in visible))
            db.execute('UPDATE kv SET value=? WHERE key=?', (json.dumps(value, ensure_ascii=False), key))
    write(path, config)
    db.close()
    print('外部消息回应已并入 QQ，配置和数据库已备份。')


if __name__ == '__main__':
    import sys
    migrate(sys.argv[1] if len(sys.argv) > 1 else 'data')
