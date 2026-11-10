"""Feedback-biased random polling with quiet hours and a durable delivery outbox."""
import asyncio
from datetime import datetime,timedelta
from fnmatch import fnmatchcase
import random
import time
import uuid
from zoneinfo import ZoneInfo
from .client import GalleryClient


class GalleryPolling:
    def setup_polling(self):
        self.poll_changed=asyncio.Event()
        self.poll_deadline=None
        self.poll_running=False
        self.poll_advance_requested=False
        self.poll_ignore_quiet=False
        self.function(self.push_now,name="gallery_push_now")
        self.trigger_source('push_received','收到图库推送',
            event_schema={'description':'已从图库领取并本地持久保存的图片ID批次，不代表图片已经发送给用户。',
                'properties':{'batch_id':{'type':'string','description':'持久批次ID，用于去重'},
                    'target':{'type':'string','description':'独立推送目标标识'},
                    'image_ids':{'type':'array','items':{'type':'string'},'description':'按领取顺序去重的图片ID，不包含图片本体'},
                    'replay':{'type':'boolean','description':'是否来自上游重发队列'},
                    'fetched_at':{'type':'string','description':'领取时间，含时区ISO8601'}},
                'examples':[{'batch_id':'example','target':'sakubot_gallery','image_ids':['example-1','example-2'],'replay':False,'fetched_at':'2026-11-07T10:00:00+08:00'}]},
            id_description='固定具名事件image_gallery.push_received，只能绑定一个动作。')

    def listening(self):
        return any(row.get('enabled') and row.get('eligible') and fnmatchcase(self.id+'.push_received',row['source'])
                   for row in self.runtime.scripts.trigger_consumers())

    def quiet_delay(self):
        if not self.config['quiet_enabled']:return 0
        now=datetime.now(ZoneInfo(self.config['timezone']))
        start=datetime.strptime(self.config['quiet_start'],'%H:%M').time()
        end=datetime.strptime(self.config['quiet_end'],'%H:%M').time()
        inside=start<=now.time().replace(tzinfo=None)<end if start<end else now.time().replace(tzinfo=None)>=start or now.time().replace(tzinfo=None)<end
        if not inside:return 0
        finish=datetime.combine(now.date(),end,tzinfo=now.tzinfo)
        if finish<=now:finish+=timedelta(days=1)
        return max(1,finish.timestamp()-now.timestamp())

    def interval(self):
        low=self.config['interval_min_minutes']
        high=self.config['interval_max_minutes']
        previous=self.state.get('poll_feedback',{})
        same_target=(previous.get('base_url')==self.config['base_url'].rstrip('/') and
                     previous.get('target')==self.config['push_target'])
        if same_target and previous.get('requested_count',0)>0:
            # Mirrored beta distributions retain randomness across the full range.
            # Full batch: mean 25% into the range; short batch: mean 75%.
            full=previous['received_count']>=previous['requested_count']
            fraction=random.betavariate(1,3) if full else random.betavariate(3,1)
        else:
            fraction=random.random()
        return (low+(high-low)*fraction)*60

    def record_poll_result(self,config,requested,received,replay):
        self.state.set('poll_feedback',{
            'base_url':config['base_url'].rstrip('/'),'target':config['push_target'],
            'requested_count':requested,'received_count':received,'replay':replay,
            'at':time.time()})

    def poll_status(self,**values):
        self.state.set('poll_status',{**self.state.get('poll_status',{}),**values})

    async def start(self):
        self.background(self.poll_loop())

    def schedule_poll(self,deadline):
        self.poll_deadline=deadline
        self.poll_status(next_at=deadline)

    async def push_now(self,ignore_quiet: bool=False):
        """将下一次图库推送检查提前执行，而不是单独领取图片。超过10秒则提前，10秒以内保持时间不变；正在检查时不重复执行。默认遵守免打扰，ignore_quiet=true仅让下一次检查跳过免打扰，不修改长期配置。仍须启用轮询、配置认证并绑定事件动作。只返回调度状态，图片ID通过image_gallery.push_received事件提供。

        Args:
            ignore_quiet(boolean): 无视免打扰状态，默认false；true仅对本次请求对应的下一次检查有效。
        """
        now=time.time()
        def result(status,reason):
            return {'status':status,'reason':reason,'next_at':self.poll_deadline,
                    'remaining_seconds':max(0,self.poll_deadline-now) if self.poll_deadline is not None else None,
                    'ignore_quiet':self.poll_ignore_quiet}
        if not self.config['poll_enabled']:return result('disabled','推送获取未启用')
        if not self.config.get('password') or not self.config.get('base_url'):
            return result('unconfigured','图库地址或管理密码未配置')
        if self.poll_running:return result('running','已有检查正在执行')
        if self.poll_advance_requested:
            self.poll_ignore_quiet=self.poll_ignore_quiet or ignore_quiet
            return result('scheduled','已有提前执行请求')
        if self.poll_deadline is None:return result('starting','轮询正在启动，请稍后查看调度')
        if not ignore_quiet and not self.poll_ignore_quiet and self.quiet_delay():
            return result('quiet','免打扰期间保持原计划')
        if not self.listening():return result('unbound','推送事件未绑定启用的动作，保持原计划')
        self.poll_ignore_quiet=self.poll_ignore_quiet or ignore_quiet
        if self.poll_deadline-now<=10:return result('scheduled','下次检查在10秒内，保持原计划')
        # No await between checking and signalling: concurrent calls share one request.
        self.poll_advance_requested=True
        self.schedule_poll(now)
        self.poll_changed.set()
        return result('advanced','已请求提前执行，下次仍按自适应随机间隔调度')

    async def poll_loop(self):
        deadline=max(time.time(),self.state.get('poll_status',{}).get('next_at',0))
        if deadline<=time.time():deadline=time.time()+self.interval()
        self.schedule_poll(deadline)
        while True:
            self.poll_changed.clear()
            try:
                await asyncio.wait_for(self.poll_changed.wait(),max(0,self.poll_deadline-time.time()))
                advance=self.poll_advance_requested
                self.poll_advance_requested=False
                self.schedule_poll(time.time() if advance else time.time()+self.interval())
                continue
            except asyncio.TimeoutError:pass
            # An advance may arrive as the timer expires. This check consumes it too.
            self.poll_advance_requested=False
            ignore_quiet=self.poll_ignore_quiet
            self.poll_ignore_quiet=False
            self.poll_running=True
            try:
                if not self.config['poll_enabled'] or not self.config.get('password') or not self.config.get('base_url'):
                    self.poll_status(phase='disabled')
                elif not ignore_quiet and (delay:=self.quiet_delay()):
                    self.poll_status(phase='quiet')
                    self.schedule_poll(time.time()+delay+self.interval())
                    continue
                elif not self.listening():
                    self.poll_status(phase='unbound')
                else:
                    self.poll_status(phase='polling')
                    await self.drain()
                    if not self.state.get('outbox',[]):
                        await self.fetch_batch()
                        await self.drain()
                    self.poll_status(phase='waiting',error='',last_at=time.time())
            except asyncio.CancelledError:raise
            except Exception as exc:
                self.poll_status(phase='failed',error=str(exc)[:200],last_at=time.time())
                self.runtime.store.log('warning',self.id,'gallery.poll.failed',data={'error':type(exc).__name__})
            finally:
                self.poll_running=False
            self.schedule_poll(time.time()+self.interval())

    async def fetch_batch(self):
        config=dict(self.config)
        client=GalleryClient(config)
        try:
            await self.claim(client,config)
        finally:await client.close()

    async def claim(self,client,config):
        target=config['push_target']
        count=random.randint(config['count_min'],config['count_max'])
        rows=await client.json('GET','/api/plugins/napcat/replay/next',query={'target':target,'count':count},admin=True)
        if not isinstance(rows,list):raise RuntimeError('图库重发队列格式无效')
        replay=bool(rows)
        if not replay:
            rows=await client.json('GET','/api/updates',query={'target':target,'count':count,'mode':config['push_mode'],
                'image_source':config['image_source'],'include_restricted':str(config['include_restricted']).lower(),'delay':config['delay_minutes']},admin=True)
        if rows is None:rows=[]
        if not isinstance(rows,list):raise RuntimeError('图库推送列表格式无效')
        ids=list(dict.fromkeys(row['id'] for row in rows if isinstance(row,dict) and isinstance(row.get('id'),str) and row['id']))
        if not ids:
            self.record_poll_result(config,count,0,replay)
            return
        batch={'batch_id':uuid.uuid4().hex,'base_url':config['base_url'].rstrip('/'),'target':target,
               'image_ids':ids,'requested_count':count,'received_count':len(ids),'replay':replay,'fetched_at':datetime.now(ZoneInfo(config['timezone'])).isoformat(),
               'emitted':False,'acknowledged':[]}
        self.state.set('outbox',[batch])
        self.state.set('batches',([batch]+self.state.get('batches',[]))[:100])
        self.record_poll_result(config,count,len(ids),replay)

    async def drain(self):
        pending=self.state.get('outbox',[])
        while pending and self.listening():
            batch=pending[0]
            if batch['base_url']!=self.config['base_url'].rstrip('/'):
                raise RuntimeError('待处理批次属于旧图库，请恢复原地址处理后再切换')
            if not batch['emitted']:
                result=await self.emit_trigger('push_received',{k:batch[k] for k in ('batch_id','target','image_ids','replay','fetched_at')},uid='gallery:'+batch['batch_id'])
                if not result:return
                if any(row.get('status') in ('failed','disabled') for row in result):raise RuntimeError('事件动作未成功登记，批次保留')
                batch['emitted']=True
                self.state.set('outbox',pending)
            if batch['replay']:
                for image_id in batch['image_ids']:
                    if image_id in batch['acknowledged']:continue
                    connection=GalleryClient({**dict(self.config),'base_url':batch['base_url']})
                    try:
                        await connection.json('POST','/api/plugins/napcat/replay/ack',body={'target':batch['target'],'image_id':image_id},admin=True)
                    finally:await connection.close()
                    batch['acknowledged'].append(image_id)
                    self.state.set('outbox',pending)
            batch['completed_at']=time.time()
            history=self.state.get('batches',[])
            self.state.set('batches',[batch if row['batch_id']==batch['batch_id'] else row for row in history])
            pending.pop(0)
            self.state.set('outbox',pending)
