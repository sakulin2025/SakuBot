"""One-time deployment migration; the core does not import platform migration code."""
import json
import os
from pathlib import Path
import sqlite3
import time


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as file:
        file.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


def migrate(root):
    root = Path(root)
    path = root / 'config.json'
    original = json.loads(path.read_text())
    destination = root / 'plugin_data' / 'qq' / 'config.json'
    old = {key: original[key] for key in ('owner_id', 'napcat_ws', 'napcat_token') if key in original}
    backup = None
    if old:
        backup = root / 'migrations' / ('before-qq-plugin-' + str(time.time_ns()))
        atomic(backup / 'config.json', original)
        if not destination.exists():
            atomic(destination, old)
        for key in old:
            original.pop(key)
        atomic(path, original)
    settings = json.loads(destination.read_text()) if destination.exists() else {}
    owner = str(settings.get('owner_id', ''))
    db = sqlite3.connect(root / 'sakubot.sqlite3')
    if backup is not None:
        archive = sqlite3.connect(backup / 'sakubot.sqlite3')
        db.backup(archive)
        archive.close()
        os.chmod(backup / 'sakubot.sqlite3', 0o600)
    with db:
        # Replace only the untouched, formerly generated default persona.
        row = db.execute("SELECT value FROM kv WHERE key='personas'").fetchone()
        if row:
            personas = json.loads(row[0])
            default = personas.get('default', {})
            if default.get('prompt') == '你是 SakuBot，拥有自己 QQ 账号的个人助手。自然、坦诚地与主人交流，持续记住共同经历。':
                default['prompt'] = '你是 SakuBot，主人的个人助手。自然、坦诚地与主人交流，持续记住共同经历。'
                db.execute("UPDATE kv SET value=? WHERE key='personas'", (json.dumps(personas, ensure_ascii=False),))
        for identifier, target, raw in db.execute("SELECT id,target,meta FROM events WHERE source='qq'").fetchall():
            meta = json.loads(raw)
            if 'exclude_main' in meta:
                continue
            main = target == 'main' or (owner and target == 'private:' + owner) or bool(meta.get('conversation_source'))
            meta.update(exclude_main=not main)
            if not main:
                meta['exclude_context'] = True
            elif meta.get('role') != 'assistant':
                meta['role'] = 'user'
            meta['source_label'] = 'QQ'
            db.execute('UPDATE events SET meta=? WHERE id=?', (json.dumps(meta, ensure_ascii=False), identifier))
        for identifier, target, text in db.execute("SELECT id,target,text FROM deliveries WHERE status='pending' AND action='send_msg'").fetchall():
            packet = {'target': target, 'text': text, 'delivery_id': identifier, 'type': 'text'}
            db.execute("UPDATE deliveries SET action='adapter:qq.message',params=? WHERE id=?", (json.dumps(packet, ensure_ascii=False), identifier))
    db.close()


if __name__ == '__main__':
    import sys
    migrate(sys.argv[1] if len(sys.argv) > 1 else 'data')
    print('QQ 配置与历史元数据已迁移；未删除记录。')
