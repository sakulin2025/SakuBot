"""Mattermost Slash command ingress with service token verification."""
import json
import re
import uuid
import time
from urllib.parse import parse_qs

from fastapi import HTTPException
from sakubot.plugin import object_schema


def register(plugin):
    rejection_times = {}

    def record_rejection(reason, data):
        # Unauthenticated input is bounded and never includes credentials or message bodies.
        key = (reason, str(data.get('command', ''))[:65])
        now = time.monotonic()
        if now - rejection_times.get(key, -120) < 60:
            return
        if len(rejection_times) >= 100:
            rejection_times.clear()
        rejection_times[key] = now
        plugin.runtime.store.log('warning', plugin.id, 'mattermost.slash.rejected',
            data={'reason': reason, 'command': key[1]})
    plugin.trigger_source('slash.*','Slash 指令',object_schema({
        'team_id':{'type':'string','title':'团队 ID · 留空不限'},
        'user_id':{'type':'string','title':'发送者 ID · 留空不限'},
        'channel_id':{'type':'string','title':'频道 ID · 留空不限'}}),
        {'type':'object','properties':{'command':{'type':'string'},'text':{'type':'string'},'user_id':{'type':'string'},'channel_id':{'type':'string'}},'required':['command']},
        match=lambda event,params:all(not params.get(key) or params[key]==event.get(key) for key in ('team_id','user_id','channel_id')))

    async def slash(request):
        if not plugin.config.get('slash_enabled',False):
            raise HTTPException(404,'Slash 未启用')
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>65536:
                raise HTTPException(413,'Slash 参数过大')
        try:
            if 'application/json' in request.headers.get('content-type',''):
                data=json.loads(body)
            else:
                data={key:value[-1] for key,value in parse_qs(body.decode(),keep_blank_values=True).items()}
        except (UnicodeError,ValueError):
            raise HTTPException(400,'Slash 参数无效') from None
        if not isinstance(data,dict) or not isinstance(data.get('token'),str):
            record_rejection('missing_token', data if isinstance(data,dict) else {})
            raise HTTPException(403,'Slash 认证失败')
        token=data.pop('token')
        reason=plugin.commands.authentication_error(token,data)
        if reason:
            record_rejection(reason, data)
            raise HTTPException(403,'Slash 认证失败')
        command=str(data.get('command','')).lstrip('/')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',command):
            raise HTTPException(400,'Slash 指令名称无效')
        allowed=('command','text','user_id','user_name','channel_id','channel_name','team_id','team_domain','response_url','trigger_id')
        event={key:data[key] for key in allowed if isinstance(data.get(key),str)}
        event['command']='/'+command
        # Never store the Slash verification token in events or execution logs.
        queued=await plugin.emit_trigger('slash.'+command,event,uid='slash:'+str(data.get('trigger_id') or uuid.uuid4().hex))
        plugin.runtime.store.log('info',plugin.id,'mattermost.slash.received',data={'command':command,'user_id':event.get('user_id'),'matched':len(queued)})
        return {'response_type':'ephemeral','text':'已接收' if queued else '未匹配到启用的动作'}

    plugin.webhook('slash',slash)
