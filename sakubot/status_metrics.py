"""Small dashboard projections; polling never reads full model request traces."""
import json


class StatusMetrics:
    def __init__(self,runtime):
        self.runtime=runtime
        self.record=runtime.store.kv_get('status:context_usage')

    def seed(self):
        if self.record:return
        # One-time backfill for installations created before the projection.
        cutoff=self.runtime.chat.boundary()['cutoff']
        latest=self.runtime.store.one('SELECT id,event_id FROM runs WHERE event_id>? ORDER BY started DESC LIMIT 1',(cutoff,))
        if not latest:return
        row=self.runtime.store.one('SELECT trace FROM runs WHERE id=?',(latest['id'],))
        try:
            trace=json.loads(row['trace'])
            _,model=self.runtime.config.settings.selected_model()
            if not model or trace.get('model_id')!=model.id:return
            if trace.get('manual_compression') and trace.get('context_after') is not None:
                used,estimated=trace['context_after'],True
            else:
                usage=(trace.get('usage') or [{}])[-1]
                requests=trace.get('api_requests') or []
                used=usage.get('prompt_tokens')
                estimated=not isinstance(used,(int,float)) or isinstance(used,bool) or used<0
                if estimated:
                    if not requests:return
                    body=requests[-1]['body']
                    used=self.runtime.compression.tokens(body.get('messages',[]),body.get('tools'),model.id)
            self.put(model.id,latest['event_id'],used,estimated)
        except (ValueError,TypeError,KeyError,IndexError,AttributeError):return

    def put(self,model_id,event_id,tokens,estimated):
        self.record={'model_id':model_id,'event_id':event_id,'tokens':tokens,'estimated':estimated,'context_revision':self.runtime.chat.boundary()['revision']}
        self.runtime.store.kv_set('status:context_usage',self.record)

    def request(self,inv,body):
        if inv.agent_id!='main':return
        used=self.runtime.compression.tokens(body.get('messages',[]),body.get('tools'),inv.model_id)
        self.put(inv.model_id,inv.metadata.get('_main_event_id',0),used,True)

    def completed(self,inv,usage):
        if inv.agent_id!='main':return
        used=usage.get('prompt_tokens') if isinstance(usage,dict) else None
        if isinstance(used,(int,float)) and not isinstance(used,bool) and used>=0:
            self.put(inv.model_id,inv.metadata.get('_main_event_id',0),used,False)

    def compacted(self,inv,tokens):
        if inv.agent_id!='main':return
        event_id=self.runtime.store.one('SELECT max(id) id FROM events')['id'] or 0
        self.put(inv.model_id,event_id,tokens,True)

    def context_usage(self):
        _,model=self.runtime.config.settings.selected_model()
        record=self.record
        if not record or not model or not model.effective_window() or record['model_id']!=model.id:return None
        boundary=self.runtime.chat.boundary()
        if record.get('context_revision')!=boundary['revision'] or record['event_id']<=boundary['cutoff']:return None
        return {'percent':round(record['tokens']*100/model.effective_window(),1),'estimated':record['estimated']}
