#!/usr/bin/env python3
"""Explicit maintenance: snapshot stopped data, reset migrated plugins and main context."""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

IDS=['ssh_devices','ha_control','minecraft_status','scanelf','qweather','alist_manage','deepseek_balance','image_gallery','context_reminders']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    status=subprocess.check_output(['docker','inspect','--format','{{.State.Running}}','sakubot'],text=True).strip()
    if status!='false':raise SystemExit('Stop sakubot before taking the consistent snapshot.')
    data=Path(os.environ.get('SAKUBOT_RUNTIME_DATA', str(Path.home()/'ContainerService/napcat/data/sakubot')))
    previous=os.umask(0o077)
    try:
        backup=root/'backups'/('pre-plugin-reset-'+str(time.time_ns()))
        backup.mkdir(parents=True,mode=0o700)
        shutil.copytree(data,backup/'data',symlinks=True)
        shutil.copytree(root/'extensions',backup/'extension-source',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('sakubot-plugin-audit.json','sakubot-plugin-audit.log'):
            src=Path('/tmp')/name
            if src.exists():shutil.copy2(src,backup/name);(backup/name).chmod(0o600)
        oldkey=data/'plugin_data/ssh_devices/id_ed25519'
        result={'at':time.time(),'plugins':IDS,'backup':str(backup),
                'old_ssh_private_key_sha256':hashlib.sha256(oldkey.read_bytes()).hexdigest() if oldkey.exists() else '',
                'config_sha256':hashlib.sha256((data/'config.json').read_bytes()).hexdigest(),
                'qq_sha256':hashlib.sha256((data/'plugin_data/qq/config.json').read_bytes()).hexdigest()}
        db=sqlite3.connect(data/'sakubot.sqlite3')
        try:
            result['personas_before']=db.execute("SELECT key,value FROM kv WHERE key LIKE 'persona%' ORDER BY key").fetchall()
            with db:
                for identifier in IDS:
                    db.execute('DELETE FROM kv WHERE substr(key,1,?)=?',(len(identifier)+1,identifier+':'))
                db.execute("UPDATE events SET status='cancelled',error='插件数据与主对话重置' WHERE status IN ('pending','running','waiting')")
                db.execute("UPDATE deliveries SET status='cancelled',error='主对话重置' WHERE status IN ('pending','sending')")
                cutoff=db.execute('SELECT coalesce(max(id),0) FROM events').fetchone()[0]
                old=db.execute("SELECT value FROM kv WHERE key='chat:boundary'").fetchone()
                revision=(json.loads(old[0]).get('revision',0) if old else 0)+1
                for key,value in [('agent:main-summary',{'cutoff':cutoff,'text':''}),('agent:history:main',[]),('agent:pending:main',[]),('chat:boundary',{'cutoff':cutoff,'revision':revision,'at':time.time()})]:
                    db.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))
                db.execute("INSERT INTO logs(at,level,source,event,run_id,tool_call_id,data) VALUES (?,'warning','agents','context.cleared','',NULL,?)",(time.time(),json.dumps({'agent_id':'main','cutoff':cutoff,'reason':'external-plugin-data-reset'})))
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        finally:db.close()
        for identifier in IDS:
            folder=data/'plugin_data'/identifier
            if folder.exists():shutil.rmtree(folder)
            program=data/'plugins'/identifier
            if program.exists():shutil.rmtree(program)
            shutil.copytree(root/'extensions'/identifier,program,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('ssh','gallery'):
            folder=data/'workspace/artifacts'/name
            if folder.exists():shutil.rmtree(folder)
        for folder in (data/'artifacts').glob('*'):
            metadata=folder/'metadata.json'
            if metadata.is_file() and json.loads(metadata.read_text()).get('plugin') in IDS:shutil.rmtree(folder)
        # Retain the import marker to prevent accidentally restoring old AstrBot data.
        result['context_cutoff']=cutoff
        (backup/'reset-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        Path('/tmp/sakubot-reset-backup-path').write_text(str(backup))
        print('Snapshot and reset complete:',backup)
    finally:os.umask(previous)

if __name__=='__main__':main()
