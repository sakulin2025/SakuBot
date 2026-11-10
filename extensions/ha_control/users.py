"""Best-effort user metadata on the existing HA event WebSocket."""
import time


class UserDirectory:
    def __init__(self):
        self.names={}
        self.current={}
        self.pending={}
        self.next_id=100
        self.refresh_at=0
        self.admin=None

    async def refresh(self,ws):
        import json
        self.refresh_at=time.monotonic()+900
        self.pending.clear()
        commands=['auth/current_user']
        if self.admin is not False:commands.append('config/auth/list')
        for kind in commands:
            self.next_id+=1
            self.pending[self.next_id]=kind
            await ws.send(json.dumps({'id':self.next_id,'type':kind}))

    def handle(self,packet):
        if packet.get('type')!='result':return False
        kind=self.pending.pop(packet.get('id'),None)
        if not kind:return False
        result=packet.get('result')
        if kind=='auth/current_user':
            if packet.get('success') and isinstance(result,dict):
                self.admin=result.get('is_admin') is True or result.get('is_owner') is True
                self.current={result['id']:{'user_name':result.get('name'),'username':None}} if isinstance(result.get('id'),str) else {}
            else:self.current={}
        elif packet.get('success') and isinstance(result,list):
            self.names={row['id']:{'user_name':row.get('name'),'username':row.get('username')}
                for row in result if isinstance(row,dict) and isinstance(row.get('id'),str)}
        else:
            # A denied/unsupported list does not disconnect the state watcher.
            self.names={}
        return True

    def resolve(self,user_id):
        result=self.names.get(user_id) or self.current.get(user_id) or {}
        return {key:value if isinstance(value,str) and value else None
                for key,value in ((key,result.get(key)) for key in ('user_name','username'))}
