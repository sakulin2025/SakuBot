"""Subscribe only while a script binding needs entity state changes."""
import asyncio
import json
import time
from urllib.parse import urlsplit, urlunsplit

import websockets
from sakubot.plugin import object_schema


def register(plugin):
    def options():
        items = [plugin.client.entity_metadata(item) for item in plugin.client.allowed_entities().values()]
        return {'entity_id':[{'value':row['entity_id'],'label':row['display_name']+' · '+row['entity_id']} for row in items]}

    def validate(params):
        plugin.client.entity(params['entity_id'])

    async def subscribe(params,emit):
        async def loop():
            delay=5
            logged=0
            while True:
                try:
                    plugin.client.entity(params['entity_id'])
                    base=urlsplit(plugin.client.base)
                    url=urlunsplit(('wss' if base.scheme=='https' else 'ws',base.netloc,base.path.rstrip('/')+'/api/websocket','',''))
                    async with websockets.connect(url,open_timeout=15,ping_interval=20,ping_timeout=20,max_size=2**20) as ws:
                        greeting=json.loads(await asyncio.wait_for(ws.recv(),20))
                        if greeting.get('type')!='auth_required':
                            raise RuntimeError('HA WebSocket 鉴权握手无效')
                        await ws.send(json.dumps({'type':'auth','access_token':plugin.config.get('token','')}))
                        auth=json.loads(await asyncio.wait_for(ws.recv(),20))
                        if auth.get('type')!='auth_ok':
                            raise RuntimeError('HA WebSocket 鉴权失败')
                        await ws.send(json.dumps({'id':1,'type':'subscribe_events','event_type':'state_changed'}))
                        ack=json.loads(await asyncio.wait_for(ws.recv(),20))
                        if not ack.get('success'):
                            raise RuntimeError('HA 状态订阅失败')
                        delay=5
                        async for raw in ws:
                            packet=json.loads(raw)
                            if packet.get('type')!='event':
                                continue
                            event=packet.get('event',{})
                            data=event.get('data',{})
                            if data.get('entity_id')!=params['entity_id']:
                                continue
                            plugin.client.entity(params['entity_id'])
                            if params.get('to_state') and ((data.get('new_state') or {}).get('state')!=params['to_state'] or (data.get('old_state') or {}).get('state')==(data.get('new_state') or {}).get('state')):
                                continue
                            # Event data is observation only, never a model prompt.
                            await emit({'entity_id':data['entity_id'],'old_state':data.get('old_state'),
                                'new_state':data.get('new_state'),'at':event.get('time_fired')},
                                uid=str(event.get('context',{}).get('id',''))+':'+str(event.get('time_fired')))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if time.time()-logged>=120:
                        plugin.runtime.store.log('warning',plugin.id,'ha.trigger.disconnected',data={'error':type(exc).__name__})
                        logged=time.time()
                await asyncio.sleep(delay)
                delay=min(delay*2,120)
        task=plugin.background(loop())
        async def close():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        return close

    plugin.trigger_source('entity_state_changed','实体状态变化',
        object_schema({'entity_id':{'type':'string','title':'实体'},'to_state':{'type':'string','title':'变化后的状态'}},('entity_id',)),
        object_schema({'entity_id':{'type':'string'},'old_state':{'type':['object','null']},'new_state':{'type':['object','null']},'at':{'type':['string','null']}},('entity_id',)),
        subscribe=subscribe,options=options,validate=validate)
