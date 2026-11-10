"""Expiring event watches which enqueue wakes through the automation queue."""
import hashlib
import re
import time
import uuid
from fnmatch import fnmatchcase

from . import wake


class Listeners:
    def __init__(self,service):
        self.service=service
        self.store=service.runtime.store

    def records(self):
        return self.store.kv_get('automation:listeners',{})

    @staticmethod
    def binding_id(row):
        return 'listener_'+row['id']+'_'+row['generation']

    def active(self,row):
        if not row['enabled'] or row['expires_at']<=time.time():return False
        # Recover a once-only claim after a crash between queue and state writes.
        return not row['once'] or not self.store.one('SELECT id FROM automation_runs WHERE binding_id=? LIMIT 1',(self.binding_id(row),))

    def public(self,row):
        active=self.active(row)
        status='active' if active else 'expired' if row['expires_at']<=time.time() else 'triggered' if row.get('triggered_at') or (row['once'] and self.store.one('SELECT id FROM automation_runs WHERE binding_id=? LIMIT 1',(self.binding_id(row),))) else 'disabled'
        return {**row,'active':active,'status':status}

    def register(self,plugin):
        plugin.tool('event_listen',
            '临时监听事件并唤醒主智能体。create/list/get/update/delete；source支持具体ID和*通配，允许尚未声明的来源；'
            'once=true默认命中一次后失效，false持续到期。expires_in默认3600秒。source_params使用来源文档的筛选/订阅参数。'
            'block_scripts=true仅阻止匹配事件启动自动化脚本，不阻止其他wake绑定、其他监听或已经运行的脚本。'
            '命中后排队唤醒主智能体，事件数据只进临时上下文，不切换主会话源；无需建立永久绑定。',
            {'type':'object','properties':{
                'action':{'type':'string','enum':['create','list','get','update','delete']},
                'id':{'type':'string','description':'本工具返回的监听ID；get/update/delete必填'},
                'name':{'type':'string','maxLength':100,'description':'可选名称'},
                'source':{'type':'string','maxLength':512,'description':'事件ID或通配模式，create必填；先查script_binding sources'},
                'source_params':{'type':'object','additionalProperties':True,'description':'来源文档规定的订阅和筛选参数；默认{}'},
                'prompt':{'type':'string','minLength':1,'maxLength':50000,'description':'触发后给主智能体的要求，create必填'},
                'once':{'type':'boolean','default':True,'description':'仅命中一次；false持续监听直到过期'},
                'expires_in':{'type':'integer','minimum':1,'maximum':2592000,'description':'从保存时起的有效秒数，默认3600，最长30天'},
                'block_scripts':{'type':'boolean','description':'匹配时阻止自动化脚本触发，默认false'},
                'send_result_to_source':{'type':'boolean','description':'本次唤醒是否向当前主会话源报告；默认继承创建时的本轮设置'},
                'enabled':{'type':'boolean','description':'是否启用，默认true'}},
             'required':['action'],'additionalProperties':False},self.manage,audience='main')

    async def manage(self,inv,args):
        records=self.records()
        action=args['action']
        if action=='list':return {'items':[self.public(row) for row in records.values()]}
        if action=='create':
            records={key:value for key,value in records.items() if value['expires_at']>time.time()-604800}
            if len(records)>=2000:raise ValueError('监听记录已达2000条，请删除旧记录')
            if sum(self.active(row) for row in records.values())>=100:raise ValueError('临时监听已达100个，请删除或停用不再需要的监听')
            if not args.get('source') or not args.get('prompt'):raise ValueError('请提供source和prompt')
            now=time.time()
            row={'id':uuid.uuid4().hex,'name':args.get('name') or '临时事件监听','source':args['source'],
                'source_params':{},'prompt':args['prompt'],'once':True,'enabled':True,'block_scripts':False,
                'send_result_to_source':bool(inv.send_result_to_source),'created_at':now,'expires_at':now+3600}
        else:
            row=records.get(args.get('id',''))
            if not row:raise ValueError('临时监听不存在')
        if action=='get':return self.public(row)
        if action=='delete':
            del records[row['id']]
            self.store.kv_set('automation:listeners',records)
            self.service.spawn(self.service.sources.reconcile())
            return {'deleted':row['id']}
        if action not in ('create','update'):raise ValueError('操作无效')
        for key in ('name','source','source_params','prompt','once','enabled','block_scripts','send_result_to_source'):
            if key in args:row[key]=args[key]
        if not re.fullmatch(r'[A-Za-z0-9_.*:-]{1,512}',row['source']):raise ValueError('事件ID无效')
        wake.validate(row)
        if len(str(row['source_params']))>50000:raise ValueError('订阅参数过大')
        source=self.service.sources.resolve(row['source'])
        if source and source.get('validate'):source['validate'](row['source_params'])
        row['expires_at']=time.time()+args.get('expires_in',3600) if action=='create' or 'expires_in' in args else row['expires_at']
        # New generations separate edited watches from already queued event claims.
        row['generation']=uuid.uuid4().hex[:12]
        row['triggered_at']=None
        records[row['id']]=row
        if sum(self.active(value) for value in records.values())>100:raise ValueError('临时监听已达100个')
        self.store.kv_set('automation:listeners',records)
        self.service.spawn(self.service.sources.reconcile())
        return self.public(row)

    def consumers(self):
        return [{**row,'id':self.binding_id(row),'target_kind':'listener','enabled':True,'eligible':True,'available':True}
                for row in self.records().values() if self.active(row)]

    def dispatch(self,source,payload,uid,subscription):
        results=[]
        blocked=False
        records=self.records()
        changed=False
        for row in records.values():
            if not fnmatchcase(source,row['source']):continue
            params=row['source_params']
            if not self.service.sources.matches(row['source'],payload,params,subscription=subscription if params==subscription else None):continue
            execution_uid='listener:'+row['id']+':'+row['generation']+':'+hashlib.sha256((source+'\0'+str(uid)).encode()).hexdigest()
            previous=self.store.one('SELECT id,status FROM automation_runs WHERE uid=?',(execution_uid,))
            if previous:
                results.append({**previous,'duplicate':True,'listener_id':row['id']})
                blocked=blocked or row['block_scripts']
                continue
            if not self.active(row):continue
            event={'id':uid,'source':source,'at':time.time(),'data':payload}
            binding={**row,'id':self.binding_id(row),'target_kind':'wake','temporary_listener':True}
            result=wake.enqueue(self.service,binding,event,execution_uid)
            results.append({**result,'listener_id':row['id']})
            blocked=blocked or row['block_scripts']
            if row['once']:
                row['triggered_at']=time.time()
                row['enabled']=False
                changed=True
            self.store.log('info','scripts','listener.triggered',data={'listener_id':row['id'],'source':source,'blocked_scripts':row['block_scripts']})
        if changed:self.store.kv_set('automation:listeners',records)
        return results,blocked
