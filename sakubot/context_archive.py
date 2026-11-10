"""Immutable, independently summarized context blocks and original message records."""
import hashlib
import copy
import json
import time
from .store import encode


class ContextArchive:
    def __init__(self, store):
        self.store = store
        store.db.executescript('''CREATE TABLE IF NOT EXISTS context_archives (
            id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, model_id TEXT NOT NULL,
            created REAL NOT NULL, first_event INTEGER NOT NULL, last_event INTEGER NOT NULL,
            messages TEXT NOT NULL, summary TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS context_archive_agent ON context_archives(agent_id,created);''')

    def key(self, agent_id, messages):
        return hashlib.sha256(encode(['archive-v2',agent_id,messages]).encode()).hexdigest()

    def get(self, key, agent_id):
        return self.store.one('SELECT * FROM context_archives WHERE id=? AND agent_id=?',(key,agent_id))

    def save(self, key, inv, messages, summary):
        ids = [row.get('_event_id') for row in messages if row.get('_event_id')]
        self.store.execute('INSERT OR IGNORE INTO context_archives VALUES (?,?,?,?,?,?,?,?)',
            (key,inv.agent_id,inv.model_id,time.time(),min(ids,default=0),max(ids,default=0),encode(messages),summary))

    def query(self, agent_id, action='list', identifier='', query='', offset=0, limit=10):
        offset, limit = max(0,int(offset)), max(1,min(50,int(limit)))
        if action == 'read':
            row = self.get(identifier,agent_id)
            if not row:
                raise ValueError('归档不存在或不属于当前智能体')
            messages = json.loads(row.pop('messages'))
            return {**row,'messages':messages[offset:offset+limit],'total':len(messages),
                    'next_offset':offset+limit if offset+limit<len(messages) else None}
        if action not in ('list','search'):
            raise ValueError('action 仅支持list/search/read')
        pattern = '%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        rows = self.store.rows('''SELECT id,created,first_event,last_event,summary FROM context_archives
            WHERE agent_id=? AND (?='' OR summary LIKE ? ESCAPE '\\' OR messages LIKE ? ESCAPE '\\')
            ORDER BY created DESC LIMIT ? OFFSET ?''',(agent_id,query,pattern,pattern,limit+1,offset))
        more = len(rows)>limit
        return {'items':rows[:limit],'next_offset':offset+limit if more else None}


def units(messages):
    """Keep each persisted event and each untagged assistant tool batch indivisible."""
    result=[]
    pending=set()
    for row in messages:
        event=row.get('_event_id')
        if not result or (not pending and (event != result[-1][0].get('_event_id') or not event)):
            result.append([])
        result[-1].append(row)
        pending.update(call['id'] for call in row.get('tool_calls',[]) if call.get('id'))
        if row.get('role')=='tool':pending.discard(row.get('tool_call_id'))
    # An unfinished call batch cannot be archived.
    if pending:result.pop()
    return result


def projection(messages):
    """Bound bulky tool payloads while retaining valid complete message envelopes."""
    result=[]
    for row in messages:
        prepared={key:copy.deepcopy(value) for key,value in row.items() if key in ('role','content','tool_calls','tool_call_id','name','_event_id')}
        content=prepared.get('content')
        if isinstance(content,str) and len(content)>8000:
            prepared['content']=content[:5000]+'\n[长内容省略，完整原文保存在该归档；需要细节用context_archive读取]\n'+content[-2000:]
        elif isinstance(content,list):
            prepared['content']=[{'type':'text','text':'[图片原文保留在归档]'} if isinstance(p,dict) and p.get('type')=='image_url' else p for p in content]
        for call in prepared.get('tool_calls',[]):
            function=call.get('function',{})
            args=function.get('arguments','')
            if isinstance(args,str) and len(args)>4000:
                function['arguments']='[长参数省略；完整值见归档原文] '+args[:3000]
        result.append(prepared)
    return result
