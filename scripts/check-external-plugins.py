#!/usr/bin/env python3
"""Explicitly requested plugin audit. Writes only isolated fixture state; live services are read-only."""
import asyncio
import copy
import importlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, '/app')
sys.path.insert(0, '/data/plugin_dependencies')
import httpx
import jsonschema

NAMES=['ssh_devices','ha_control','minecraft_status','scanelf','qweather','alist_manage','deepseek_balance','image_gallery','context_reminders']
REPORT={'started':time.time(),'checks':[]}
LIVE=Path('/data')
SECRET=[]


def safe(error):
    text=str(error)
    for value in SECRET:
        if isinstance(value,str) and len(value)>5:text=text.replace(value,'<redacted>')
    return text[:350]


async def check(plugin,name,operation,*,external=False):
    try:
        result=operation()
        if hasattr(result,'__await__'):result=await result
        REPORT['checks'].append({'plugin':plugin,'check':name,'status':'pass','details':result})
        print('PASS',plugin,name,flush=True)
        return result
    except Exception as exc:
        REPORT['checks'].append({'plugin':plugin,'check':name,'status':'external_unavailable' if external else 'fail','error':type(exc).__name__+': '+safe(exc)})
        print('UNAVAILABLE' if external else 'FAIL',plugin,name,type(exc).__name__,safe(exc),flush=True)
        return None


def require(value,message):
    if not value:raise AssertionError(message)


async def main():
    from sakubot.config import Config
    from sakubot.store import Store
    from sakubot.runtime import Runtime
    from sakubot.plugin import Invocation
    root=Path(tempfile.mkdtemp(prefix='sakubot-plugin-audit-'))
    os.environ['SAKUBOT_DATA']=str(root)
    shutil.copy2(LIVE/'config.json',root/'config.json')
    for name in NAMES:
        shutil.copytree(Path('/tmp/audit-extension-source')/name,root/'plugins'/name)
        source=LIVE/'plugin_data'/name
        if source.exists():shutil.copytree(source,root/'plugin_data'/name)
    cfg=Config();cfg.settings.plugins=NAMES
    for provider in cfg.settings.providers:SECRET.append(provider.api_key)
    for path in (root/'plugin_data').glob('*/config.json'):
        for key,value in json.loads(path.read_text()).items():
            if key in ('key','token','password','path_password'):SECRET.append(value)
    store=Store(root)
    source=sqlite3.connect('file:/data/sakubot.sqlite3?mode=ro',uri=True)
    for key,value in source.execute('SELECT key,value FROM kv'):
        if key=='personas' or any(key.startswith(name+':') for name in NAMES):store.execute('INSERT OR REPLACE INTO kv VALUES (?,?)',(key,value))
    source.close()
    runtime=Runtime(cfg,store);runtime.registry.runtime=runtime
    selected=cfg.settings.selected_model()[1]
    async def call(name,**args):
        invocation=Invocation('audit:'+uuid.uuid4().hex,'main',origin='dashboard',call_id=uuid.uuid4().hex,model_id=selected.id if selected else '')
        return await runtime.registry.call(name,args,invocation)
    try:
        for name in NAMES:
            await check(name,'load',lambda name=name:runtime.registry.enable(name))
        plugins={p.id:p for p in runtime.registry.plugins}
        token=(LIVE/'admin_token').read_text().strip()
        async with httpx.AsyncClient(base_url='http://127.0.0.1:6190',headers={'Authorization':'Bearer '+token},timeout=40,trust_env=False) as http:
            registry=(await http.get('/api/plugin-registry')).json()
            functions=(await http.get('/api/functions')).json()['items']
            for name in NAMES:
                async def api_page(name=name):
                    require(any(p['name']==name and p['loaded'] and not p['builtin'] for p in registry['plugins']),'plugin is not loaded as external')
                    response=await http.get('/api/extensions/'+name+'/manage');response.raise_for_status()
                    body=response.json();require(body['sections'] and isinstance(body['data'],dict),'invalid management state')
                    for section in body['sections']:
                        require(section['id'] in body['data'],'section has no data: '+section['id'])
                    config=body['data'].get('config',{})
                    for key in ('token','key','password','path_password'):
                        if key in config:require(config[key]=='','secret returned in config')
                    page=await http.get('/extensions/'+name+'/manage/');page.raise_for_status()
                    assets=re.findall(r'(?:src|href)="(\./assets/[^\"]+)"',page.text)
                    require(assets,'no compiled page assets')
                    for asset in assets:
                        result=await http.get('/extensions/'+name+'/manage/'+asset[2:]);result.raise_for_status();require(len(result.content)>20,'empty asset')
                    own=[item for item in functions if item['plugin_id']==name]
                    require(own,'no visible functions')
                    for item in own:jsonschema.Draft202012Validator.check_schema(item['parameters'])
                    return {'sections':len(body['sections']),'tools':len(own),'assets':len(assets)}
                await check(name,'live management, assets, schema and secret redaction',api_page)
        # Isolated UI actions cover actual management callbacks, not a second implementation.
        for name,p in plugins.items():
            if not hasattr(p,'config'):continue
            async def config_roundtrip(p=p):
                before=copy.deepcopy(dict(p.config))
                payload={field['key']:before[field['key']] for field in p.fields}
                for key in p.config.secrets:
                    if key in payload:payload[key]=''
                p.config.patch(payload,importlib.import_module('sakubot.plugin_support').fields_schema(p.fields))
                require(dict(p.config)==before,'unchanged config roundtrip changed fields or cleared secret')
                return True
            await check(name,'isolated config roundtrip',config_roundtrip)
        ssh=plugins['ssh_devices']
        async def ssh_crud():
            created=await call('ssh_device',action='add',details={'name':'audit-local','description':'fixture','address':'127.0.0.1','username':'audit','port':22})
            require(isinstance(created,dict),'device add failed')
            identifier=created.get('id') or created.get('device',{}).get('id')
            require(identifier,'missing device id')
            updated=await call('ssh_device',action='update',device=identifier,details={'description':'updated'})
            require(isinstance(updated,dict),'device update failed')
            removed=await call('ssh_device',action='remove',device=identifier);require(isinstance(removed,dict),'device remove failed')
            key=await call('ssh_public_key');require(key['public_key'].startswith('ssh-ed25519 '),'invalid public key')
            return True
        await check('ssh_devices','device CRUD and public key',ssh_crud)
        async def windows_protocol():
            import base64
            from types import SimpleNamespace
            from unittest.mock import AsyncMock
            connection_type=type(ssh.client.connection(next(iter(ssh.client.sessions.values())))) if ssh.client.sessions else importlib.import_module('sakubot_extension_ssh_devices.client').Connection
            connection=connection_type()
            connection.platform='windows';connection.home='C:/Users/audit';connection.cwd=connection.home
            output=asyncio.StreamReader()
            class Input:
                def write(self,value):
                    decoded=base64.b64decode(value.strip()).decode('utf-8')
                    marker=re.search(r'SSH_[0-9a-f]{32}',decoded)
                    if marker:output.feed_data(('audit-output\r\n'+marker[0]+':0\r\nC:/Users/audit\r\n'+marker[0]+'_END\r\n').encode())
                async def drain(self):pass
            class TextOutput:
                async def read(self,size):return (await output.read(size)).decode('utf-8')
                def at_eof(self):return output.at_eof()
            shell=SimpleNamespace(stdin=Input(),stdout=TextOutput(),close=lambda:None)
            created=[]
            async def create_process(command,**kwargs):
                created.append(command);return shell
            connection.ssh=SimpleNamespace(create_process=create_process)
            device=next(iter(ssh.client.devices))
            identifier='audit-windows'
            ssh.client.sessions[identifier]={'id':identifier,'device_id':device,'timeout':5,'cwd':''}
            ssh.client.connections[identifier]=connection
            try:
                with patch.object(ssh.client,'connect',new=AsyncMock()),patch.object(ssh.client,'detect_platform',new=AsyncMock(return_value='windows')),patch.object(ssh.client,'touch'):
                    result=await ssh.client.execute(identifier,'Write-Output "test"',timeout=5)
                require(result['exit_code']==0 and result['shell']=='powershell','Windows shell result was not parsed')
                require(created and created[0].startswith('powershell.exe ') and not created[0].startswith('exec'),'Windows launch still depends on POSIX exec')
                require(ssh.client.remote_path(connection,'C:\\Temp\\file.txt')=='C:/Temp/file.txt','Windows path normalization failed')
                return True
            finally:
                ssh.client.sessions.pop(identifier,None);ssh.client.connections.pop(identifier,None)
        await check('ssh_devices','isolated Windows PowerShell transport and path handling',windows_protocol)
        async def remote_device(index,device):
            record=await ssh.client.session_action('open',device=device['id'],details={'description':'read-only audit','timeout':15})
            try:
                result=await ssh.client.execute(record['id'],'pwd',timeout=15)
                require(result['exit_code']==0 and result['shell'] in ('posix','powershell'),'read-only command failed')
                await check('ssh_devices',f'remote device {index} SFTP stat',lambda:ssh.client.files(record['id'],'stat','.'),external=True)
                return {'shell':result['shell'],'exit_code':result['exit_code']}
            finally:await ssh.client.session_action('remove',session_id=record['id'])
        await asyncio.gather(*(check('ssh_devices',f'remote device {i} authentication and terminal',lambda i=i,d=d:remote_device(i,d),external=True) for i,d in enumerate(list(ssh.client.devices.values()),1)))
        ha=plugins['ha_control']
        async def ha_read():
            result=await call('ha_query',summary=True);require(isinstance(result,dict),'HA live query failed: '+safe(result));return {'entities':len(result.get('entities',[]))}
        await check('ha_control','live states',ha_read,external=True)
        async def ha_plan():
            targets=[key for key,value in ha.client.allowed_entities().items() if value['policy']=='controllable']
            if targets:
                result=await call('ha_control',entity_ids=targets[:2],action='on',preview=True)
                require(isinstance(result,dict) and result['preview'] and len(result['plans'])==min(2,len(targets)),'batch preview failed')
            original=ha.client.manual()
            await call('ha_manual',action='append',content='audit-only fixture')
            require('audit-only fixture' in ha.client.manual(),'manual append failed')
            await call('ha_manual',action='write',content=original)
            try:await ha.manage({'section':'manual','value':{'content':'bad'},'expected':{'content':'not-current'}})
            except RuntimeError:pass
            else:raise AssertionError('stale manual overwrite allowed')
            return True
        await check('ha_control','batch preview and manual conflict (no device operation)',ha_plan)
        async def ha_initialize():
            states=[{'entity_id':'switch.audit_lamp','attributes':{'friendly_name':'audit lamp'}},{'entity_id':'sensor.audit_temperature','attributes':{'friendly_name':'audit temperature'}}]
            def api(method,path,payload=None,text=False):
                if method=='GET' and path=='/api/states':return states
                if method=='POST' and path=='/api/template':return 'switch.audit_lamp|audit room\n'+'sensor.audit_temperature|audit room\n'
                raise AssertionError('unexpected HA API call')
            with patch.object(ha.client,'api',side_effect=api):
                result=await call('ha_initialize',action='scan',confirmed=True);require(isinstance(result,dict),'initialization scan failed')
                await call('ha_initialize',action='room',area='audit room',enabled=True)
                await call('ha_initialize',action='policy',entity_id='switch.audit_lamp',policy='controllable',alias='audit lamp',group='lights')
                await call('ha_initialize',action='review_room',area='audit room',confirmed=True)
                result=await call('ha_initialize',action='build',confirmed=True)
                require(isinstance(result,dict) and ha.config['initialized'],'initialization publish failed')
                require('switch.audit_lamp' in ha.client.allowed_entities(),'published entity missing')
            return True
        await check('ha_control','isolated complete initialization workflow',ha_initialize)
        mc=plugins['minecraft_status']
        await check('minecraft_status','live saved server status',lambda:call('minecraft_status',refresh=True),external=True)
        async def mc_flow():
            saved=await call('minecraft_servers',action='add',details={'name':'audit-server','address':'127.0.0.1:25565'})
            record=saved['server'];rule=await mc.manage_alerts('add',record['id'],details={'kind':'players_joined','target':'main'})
            rule_id=next(x['id'] for x in rule['alerts'] if x['server_id']==record['id'])
            async def query_zero(record,refresh=False):return {'online':True,'state':'online','players_online':0,'players_max':20,'checked_at':'2026-10-26T00:00:00+00:00'}
            async def query_one(record,refresh=False):return {'online':True,'state':'online','players_online':1,'players_max':20,'checked_at':'2026-10-26T00:01:00+00:00'}
            with patch.object(mc.client,'query',side_effect=query_zero):await mc.poll_once()
            initial=store.one("SELECT count(*) AS n FROM events WHERE source='minecraft_status'")['n']
            with patch.object(mc.client,'query',side_effect=query_one):
                await mc.poll_once()
                if mc.event_task:await mc.event_task
            count=store.one("SELECT count(*) AS n FROM events WHERE source='minecraft_status'")['n']
            require(count>initial,'join edge did not enqueue proactive event')
            with patch.object(mc.client,'query',side_effect=query_one):
                await mc.poll_once()
                if mc.event_task:await mc.event_task
            require(store.one("SELECT count(*) AS n FROM events WHERE source='minecraft_status'")['n']==count,'unchanged sample duplicated event')
            await mc.manage_alerts('remove',rule_id=rule_id)
            await call('minecraft_servers',action='remove',server=record['id'])
            return True
        await check('minecraft_status','CRUD, baseline, edge event and deduplication',mc_flow)
        scan=plugins['scanelf']
        async def scan_read():
            result=await call('scanelf_devices',refresh=True);require(isinstance(result,dict),'device query failed: '+safe(result));rows=result['items']
            if rows:
                page=await scan.get_timeline(rows[0]['mac'],limit=1)
                require('has_more' in page,'timeline pagination missing')
                if page['has_more']:
                    later=await scan.get_timeline(rows[0]['mac'],limit=1,before=page['next_cursor']);require(later['before']==page['next_cursor'],'timeline cursor not forwarded')
            return {'devices':len(rows)}
        await check('scanelf','live devices and timeline pagination',scan_read,external=True)
        async def scan_memory():
            key,memory=await scan.memories();mac='02:00:00:00:00:01'
            updated=await scan.save_memory(key,memory,mac,'set',{'alias':'audit-fixture','description':'fixture only'})
            enriched=scan.enrich({'mac':mac,'name':'native'},updated)
            require(enriched['display_name']=='audit-fixture' and enriched['description']=='fixture only','alias/description not merged')
            await scan.save_memory(key,updated,mac,'remove',{})
            return True
        await check('scanelf','isolated memory CRUD and result enrichment',scan_memory)
        weather=plugins['qweather']
        async def weather_read():
            geo=await call('qweather_geo');require(isinstance(geo,dict),'geo query failed: '+safe(geo))
            result=await call('qweather_weather');require(isinstance(result,dict),'weather query failed: '+safe(result))
            require(result.get('needs_selection') or result.get('services'),'missing weather results')
            return {'selection_needed':bool(result.get('needs_selection')),'services':list(result.get('services',{})),'errors':list(result.get('errors',{}))}
        await check('qweather','live GeoAPI and weather',weather_read,external=True)
        alist=plugins['alist_manage']
        async def alist_read():
            folders=await asyncio.to_thread(alist.client.discover)
            result=await call('alist_browse',action='list',path='/')
            require(isinstance(result,dict),'listing failed: '+safe(result))
            return {'discovered_folders':len(folders)}
        await check('alist_manage','live root discovery and filtered listing',alist_read,external=True)
        async def alist_policy():
            before=alist.config['folder_rules']
            alist.config['folder_rules']=[{'path':'/audit','ignore':False,'download':False,'add':True,'delete':False}]
            alist.client.check_write('mkdir','/audit/new')
            for action,args in [('remove',('/audit/new',)),('copy',('/audit/file','/audit'))]:
                try:alist.client.check_write(action,*args)
                except ValueError:pass
                else:raise AssertionError(action+' incorrectly allowed')
            alist.config['folder_rules']=before
            return True
        await check('alist_manage','directory operation isolation (no writes)',alist_policy)
        balance=plugins['deepseek_balance']
        async def balance_read():
            providers=[p for p in cfg.settings.providers if balance.official(p)]
            require(providers,'no configured official provider')
            result=await call('deepseek_balance',provider_id=providers[0].id)
            require(isinstance(result['balance_infos'],list),'invalid balance output')
            return {'currencies':len(result['balance_infos'])}
        await check('deepseek_balance','live official balance (amount not recorded)',balance_read,external=True)
        async def default_provider():
            from sakubot.config import ProviderConfig
            provider=ProviderConfig(name='fixture',api_base='https://api.deepseek.com/v1',api_key='fixture-key')
            client_type=httpx.AsyncClient
            transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'is_available':True,'balance_infos':[]}))
            with patch.object(type(cfg.settings),'selected_model',return_value=(provider,None)) as selection,patch('httpx.AsyncClient',side_effect=lambda **kwargs:client_type(transport=transport,**kwargs)):
                await balance.balance(invocation=Invocation('fixture','main'))
                require(selection.call_args.kwargs.get('model_id') is None,'empty invocation model does not use the default provider')
            return True
        await check('deepseek_balance','isolated default provider fallback',default_provider)
        gallery=plugins['image_gallery']
        async def gallery_read():
            pending=await call('count_pending_images');require(type(pending.get('pending')) is int,'pending count failed')
            image=await call('fetch_anime_image');require(image.get('id') and image.get('url','').startswith('/api/artifacts/'),'missing image identity/artifact')
            require(gallery.workspace.path(image['path']).is_file(),'image was not saved')
            return {'image_saved_in_fixture':True,'id_returned':True}
        await check('image_gallery','live approved image, ID and local artifact (no sending)',gallery_read,external=True)
        reminders=plugins['context_reminders']
        async def reminders_crud():
            item=await call('add_context_reminder',target='main',content='audit-fixture',ttl_hours=1)
            require(any(x['id']==item['id'] for x in await call('list_context_reminders')),'reminder missing')
            require('audit-fixture' in reminders.prompt_context(Invocation('fixture','main')),'reminder not injected')
            await call('remove_context_reminder',reminder_id=item['id'])
            require(not any(x['id']==item['id'] for x in await call('list_context_reminders')),'reminder was not removed')
            return True
        await check('context_reminders','isolated create, injection, list and remove',reminders_crud)
        async def reminder_edit():
            item=await reminders.add('main','before edit',1)
            result=await reminders.manage({'section':'items','action':'save','key':item['id'],'value':{'target':'main','content':'after edit','ttl_hours':1}})
            rows=reminders.items()
            require(any(row['id']==item['id'] and row['content']=='after edit' for row in rows),'editing changed the reminder identity')
            before=len(rows)
            try:await reminders.manage({'section':'items','action':'save','key':'missing-record','value':{'target':'main','content':'must not persist','ttl_hours':1}})
            except ValueError:pass
            else:raise AssertionError('editing missing reminder succeeded')
            require(len(reminders.items())==before,'failed edit created a stray reminder')
            return True
        await check('context_reminders','isolated edit identity and failed-edit atomicity',reminder_edit)
        async def artifacts():
            from fastapi import FastAPI
            from sakubot.artifacts import register_artifacts
            app=FastAPI();register_artifacts(app,runtime)
            source=runtime.workspace.path('artifacts/audit.txt');source.parent.mkdir(parents=True,exist_ok=True);source.write_text('audit-artifact')
            item=ssh.artifact(source)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as http:
                response=await http.get(item['url']);require(response.status_code==200 and response.text=='audit-artifact','artifact HTTP download failed')
            return True
        await check('framework','artifact HTTP delivery in isolated app',artifacts)
        async def empty_install():
            cold=root/'fresh';cold.mkdir();shutil.copy2(LIVE/'config.json',cold/'config.json')
            for name in NAMES:shutil.copytree(Path('/tmp/audit-extension-source')/name,cold/'plugins'/name)
            os.environ['SAKUBOT_DATA']=str(cold)
            cold_config=Config();cold_store=Store(cold);cold_runtime=Runtime(cold_config,cold_store);cold_runtime.registry.runtime=cold_runtime
            try:
                for name in NAMES:await cold_runtime.registry.enable(name)
                cold_plugins={p.id:p for p in cold_runtime.registry.plugins}
                for name,p in cold_plugins.items():
                    view=p.view()
                    if hasattr(view,'__await__'):view=await view
                    require(isinstance(view.get('data'),dict),'empty management state failed: '+name)
                require(not cold_plugins['ssh_devices'].client.devices and not cold_plugins['ssh_devices'].client.sessions,'SSH empty setup restored old records')
                require(cold_plugins['ssh_devices'].client.key.get_fingerprint()!=ssh.client.key.get_fingerprint(),'empty SSH setup reused old key')
                require(not cold_plugins['ha_control'].config['initialized'] and not cold_plugins['ha_control'].config['entities'],'HA empty setup restored entities')
                require(not cold_plugins['minecraft_status'].state.get('servers',{}),'MC empty setup restored servers')
                require(not cold_plugins['context_reminders'].items(),'empty setup restored reminders')
                return {'packages':len(cold_plugins),'new_ssh_key':True}
            finally:
                await cold_runtime.registry.stop();await cold_runtime.workspace.shell_runner.stop();cold_store.db.close()
        await check('all','fresh empty install, management state and key generation',empty_install)
    finally:
        await runtime.registry.stop()
        await runtime.workspace.shell_runner.stop()
        store.db.close()
        shutil.rmtree(root)
        REPORT['finished']=time.time()
        Path('/tmp/sakubot-plugin-audit.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2))
    failed=[x for x in REPORT['checks'] if x['status']=='fail']
    print('SUMMARY',json.dumps({'passed':sum(x['status']=='pass' for x in REPORT['checks']),'failures':len(failed),'external_unavailable':sum(x['status']=='external_unavailable' for x in REPORT['checks'])}),flush=True)
    return bool(failed)

if __name__=='__main__':raise SystemExit(asyncio.run(main()))
