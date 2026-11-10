"""Resume failed main-model turns without creating or replaying a user message."""
import copy
import json
import time


class FailedRequests:
    def __init__(self,runtime):self.runtime=runtime

    def register(self,plugin):
        plugin.tool('model_retry_last',
            '重试主智能体最近一次失败的模型请求；仅当最后一次主智能体运行因模型请求失败且当前空闲时有效。'
            '建议仅在自动化脚本中调用。智能体主动调用必定失败，因为正在调用工具说明当前模型已成功返回。'
            '复用原消息和已完成工具结果，不重新执行已完成工具，不新增唤醒消息。',
            {'type':'object','properties':{},'additionalProperties':False},self.tool)

    async def tool(self,inv,args):
        if inv.origin=='agent':raise ValueError('智能体正在成功执行工具，不能重试；该工具建议仅供脚本调用')
        return self.queue()

    def latest(self):
        return self.runtime.store.one("SELECT * FROM runs WHERE coalesce(json_extract(trace,'$.agent_id'),'main')='main' AND event_id>0 ORDER BY started DESC LIMIT 1")

    def queue(self,event_id=None):
        runtime=self.runtime
        if runtime.current_run:raise ValueError('主智能体正在运行，不能重试')
        if not runtime.config.settings.ready():raise ValueError('请先启用主智能体并配置模型')
        latest=self.latest()
        if not latest or latest['status']!='failed':raise ValueError('最后一次主智能体调用没有失败，不能重试')
        row=runtime.store.one('SELECT * FROM events WHERE id=?',(latest['event_id'],))
        if not row or row['status']!='failed' or not runtime.chat.visible(row):raise ValueError('失败请求不在当前可重试的主对话中')
        if event_id is not None and event_id!=row['id']:raise ValueError('只能重试最近一次失败的主智能体请求')
        trace=json.loads(latest['trace'])
        checkpoint=trace.get('retry_checkpoint')
        if checkpoint is None:
            # Existing failure records already preserve the messages and API body.
            last=runtime.store.one("SELECT event FROM logs WHERE run_id=? AND event IN ('model.failed','model.completed') ORDER BY id DESC LIMIT 1",(latest['id'],))
            if not last or last['event']!='model.failed' or not trace.get('api_requests'):
                raise ValueError('该失败没有可恢复的模型请求，不会自动重跑工具')
        elif not checkpoint.get('failed'):
            raise ValueError('最后一次失败不是模型请求失败，不能用此功能重试')
        metadata=json.loads(row['meta'])
        for key in ('wake_submitted','wake_request_id','wake_run_id','retry_event_id','retry_of'):
            metadata.pop(key,None)
        metadata['retry_from_run']=latest['id']
        metadata['retry_count']=metadata.get('retry_count',0)+1
        changed=runtime.store.execute("UPDATE events SET status='pending',error='',expires=0,priority=max(priority,101),meta=? WHERE id=? AND status='failed'",(json.dumps(metadata,ensure_ascii=False),row['id'])).rowcount
        if not changed:raise ValueError('失败请求状态已变化')
        runtime.chat.event(runtime.store.one('SELECT * FROM events WHERE id=?',(row['id'],)))
        runtime.changed.set()
        runtime.store.log('info','model','request.retry.queued',data={'event_id':row['id'],'previous_run_id':latest['id']})
        return {'event_id':row['id'],'status':'pending','previous_run_id':latest['id']}

    def restore(self,event,inv):
        previous=json.loads(event['meta']).get('retry_from_run')
        if not previous:return None
        row=self.runtime.store.one('SELECT trace FROM runs WHERE id=?',(previous,))
        if not row:raise ValueError('原失败请求记录已不存在')
        trace=json.loads(row['trace'])
        messages=copy.deepcopy(trace.get('messages',[]))
        if not messages:raise ValueError('原失败请求没有可恢复上下文')
        checkpoint=trace.get('retry_checkpoint') or {}
        for key,value in checkpoint.get('metadata',{}).items():inv.metadata[key]=copy.deepcopy(value)
        inv.metadata['_main_event_id']=event['id']
        inv.metadata['_wake_unprepared']=[]
        inv.metadata['_resume_usage']=copy.deepcopy(trace.get('usage',[]))
        inv.metadata['resumed_from_run']=previous
        if checkpoint:
            inv.temporary_context=copy.deepcopy(checkpoint.get('temporary_context',[]))
            inv.temporary_next=copy.deepcopy(checkpoint.get('one_shot',[]))
            inv.send_result_to_source=checkpoint.get('send_result_to_source',inv.send_result_to_source)
        else:
            # Legacy records: reuse original temporary requirements, excluding
            # environment blocks which are generated for the new request.
            contexts=(trace.get('temporary_contexts') or [{}])[-1].get('messages',[])
            inv.temporary_context=[copy.deepcopy(item) for item in contexts if item.get('content') and
                item.get('_injection',{}).get('source') not in ('framework.wake_prompt','framework.reply_location')]
            inv.metadata['_wake_temporary']=[]
            inv.metadata['absorbed_events']=[item['_event_id'] for item in messages if item.get('_event_id') and item['_event_id']!=event['id'] and item.get('_wake_body')]
        for event_id in inv.metadata.get('absorbed_events',[]):
            self.runtime.store.execute("UPDATE events SET status='running',error='',meta=json_set(json_remove(meta,'$.wake_submitted','$.wake_request_id'),'$.wake_run_id',?,'$.absorbed_run_id',?) WHERE id=? AND status='failed'",(inv.run_id,inv.run_id,event_id))
            source=self.runtime.store.one('SELECT * FROM events WHERE id=?',(event_id,))
            if source:self.runtime.chat.event(source)
        if self.runtime.current_run:self.runtime.current_run['send_result_to_source']=inv.send_result_to_source
        return messages
