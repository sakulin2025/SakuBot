#!/usr/bin/env python3
"""Offline, one-time migration. Secrets and original records stay in a private backup outside data."""
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=Path(os.environ.get('ASTRBOT_DATA', str(Path.home()/'ContainerService/napcat/data/astrbot')))
DATA=Path(os.environ.get('SAKUBOT_RUNTIME_DATA', str(Path.home()/'ContainerService/napcat/data/sakubot')))
MAPPING={'ssh_devices':'ssh_devices','ha-control':'ha_control','minecraft_status':'minecraft_status','scanelf':'scanelf','qweather':'qweather','alist-manage':'alist_manage','deepseek_balance':'deepseek_balance','anime-image-store':'image_gallery','astrbot_plugin_cross_reminder':'context_reminders'}

def read(path,default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.migration.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def backup_database(source,destination):
    connection=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True)
    with sqlite3.connect(destination) as target:connection.backup(target)
    connection.close();destination.chmod(0o600)


def main():
    marker=DATA/'plugin_data'/'astrbot_migration.json'
    if marker.exists():raise SystemExit('Migration already completed; current SakuBot records were left intact.')
    backup=ROOT/'backups'/('astrbot-migration-'+str(time.time_ns()))
    backup.mkdir(parents=True,mode=0o700)
    shutil.copy2(DATA/'config.json',backup/'sakubot-config.json')
    backup_database(DATA/'sakubot.sqlite3',backup/'sakubot.sqlite3')
    backup_database(OLD/'data_v4.db',backup/'astrbot.sqlite3')
    for old,new in MAPPING.items():
        origin=OLD/'plugins'/old
        if origin.is_dir():shutil.copytree(origin,backup/'astrbot-plugins'/old,ignore=shutil.ignore_patterns('__pycache__','.git','node_modules'))
        config=OLD/'config'/(old+'_config.json')
        if config.exists():
            destination=backup/'astrbot-config'/config.name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(config,destination);destination.chmod(0o600)
    for name,files in {'ssh-devices':['state.json','host_keys.json','id_ed25519'],'ha-control':['draft.json'],'astrbot_plugin_cross_reminder':['reminders.json']}.items():
        for filename in files:
            source=OLD/'plugin_data'/name/filename
            if source.exists():
                destination=backup/'astrbot-data'/name/filename;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,destination);destination.chmod(0o600)
    # Retain any pre-existing external extension files and plugin data before replacing packages.
    for new in MAPPING.values():
        for category in ('plugins','plugin_data'):
            source=DATA/category/new
            if source.exists():shutil.copytree(source,backup/'sakubot-existing'/category/new)
        shutil.copytree(ROOT/'extensions'/new,DATA/'plugins'/new,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','node_modules'))
    for old,new in MAPPING.items():
        config=read(OLD/'config'/(old+'_config.json'),{})
        for unused in ('allow_member','admin_only','save_dir','inject_header'):config.pop(unused,None)
        if config:write(DATA/'plugin_data'/new/'config.json',config)
    for old,new,files in [('ssh-devices','ssh_devices',['state.json','host_keys.json','id_ed25519']),('ha-control','ha_control',['draft.json'])]:
        for filename in files:
            source=OLD/'plugin_data'/old/filename
            if source.exists():
                destination=DATA/'plugin_data'/new/filename;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,destination);destination.chmod(0o600)
    qq=read(DATA/'plugin_data/qq/config.json',{})
    def target(value):
        if value in ('main','owner','*',''):return 'main'
        if re.fullmatch(r'(private|group):[1-9][0-9]*',str(value)):return value
        match=re.search(r':(FriendMessage|GroupMessage):([1-9][0-9]*)$',str(value),re.I)
        if match:
            kind='private' if match[1].lower()=='friendmessage' else 'group'
            return 'main' if kind=='private' and match[2]==str(qq.get('owner_id','')) else kind+':'+match[2]
        return None
    source=sqlite3.connect('file:'+str(backup/'astrbot.sqlite3')+'?mode=ro',uri=True)
    destination=sqlite3.connect(DATA/'sakubot.sqlite3')
    imported={}
    counts={}
    def put(key,value):
        destination.execute('INSERT OR REPLACE INTO kv(key,value) VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))
    with destination:
        for scope,key,raw in source.execute("SELECT scope_id,key,value FROM preferences WHERE scope='plugin'"):
            old=scope.rsplit('/',1)[-1]
            if old not in ('minecraft_status','scanelf'):continue
            value=json.loads(raw)
            value=value.get('val',value) if isinstance(value,dict) else value
            if old=='minecraft_status' and key=='notifications':
                for rule in value.get('rules',{}).values():
                    original=rule.get('target','main');converted=target(original)
                    rule['legacy_target']=original
                    rule['target']=converted or 'main'
                    if converted is None:rule['enabled']=False
                for baseline in value.get('baselines',{}).values():
                    if baseline.get('pending'):
                        item=baseline['pending'];converted=target(item.get('target','main'))
                        if converted:item['target']=converted
                        else:baseline.pop('pending',None)
            if old=='minecraft_status' and key=='servers':counts['minecraft_servers']=len(value)
            if old=='minecraft_status' and key=='notifications':
                counts['minecraft_rules']=len(value.get('rules',{}))
                counts['minecraft_rules_paused']=sum(not r.get('enabled',True) for r in value.get('rules',{}).values())
            if old=='scanelf' and key.startswith('device_memory:'):counts['scanelf_memories']=len(value)
            put(MAPPING[old]+':'+key,value)
            imported[old+':'+key]=len(value) if isinstance(value,(dict,list)) else 1
        reminders=read(OLD/'plugin_data/astrbot_plugin_cross_reminder/reminders.json',{}).get('items',[])
        for item in reminders:
            original=item.get('target','main');item['legacy_target']=original
            item['target']=target(original) or 'main'
        put('context_reminders:items',reminders)
        row=destination.execute("SELECT value FROM kv WHERE key='personas'").fetchone()
        config=read(DATA/'config.json')
        if row:
            personas=json.loads(row[0]);persona=personas.get(config.get('main_persona_id'))
            if persona and persona.get('visible_plugins') is not None:
                persona['visible_plugins']=sorted(set(persona['visible_plugins'])|set(MAPPING.values()))
                put('personas',personas)
    destination.close();source.close()
    config=read(DATA/'config.json')
    config['plugins']=list(dict.fromkeys(config.get('plugins',[])+list(MAPPING.values())))
    write(DATA/'config.json',config)
    state=read(DATA/'plugin_data/ssh_devices/state.json',{})
    ha=read(DATA/'plugin_data/ha_control/config.json',{})
    report={'backup':str(backup),'plugins':list(MAPPING.values()),'imported':imported,**counts,
        'ssh_devices':len(state.get('devices',{})),'ssh_sessions':len(state.get('sessions',{})),
        'ha_rooms':len(ha.get('rooms',[])),'ha_entities':len(ha.get('entities',[])),'context_reminders':len(reminders),
        'notes':['Live SSH processes are not migrated.','Unrecognized MC destinations are preserved as legacy_target and disabled.','Context reminder targets remain reference data, not automatic sends.','AstrBot services and records were not modified.']}
    write(marker,report)
    write(backup/'migration-report.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
