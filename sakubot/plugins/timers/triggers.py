"""Reusable persisted schedules for script bindings, independent of Agent wakes."""
import asyncio
import hashlib
import time
from datetime import datetime
from sakubot.plugin import object_schema
from sakubot.store import encode


def register(plugin):
    parameters = object_schema({
        'timing': {'type':'string','title':'触发方式','enum':['interval','daily','once'],'default':'interval'},
        'interval_seconds': {'type':'integer','title':'间隔 · 秒','minimum':30,'maximum':31536000,'default':300},
        'daily_time': {'type':'string','title':'每日时间','format':'time','default':'09:00'},
        'timezone': {'type':'string','title':'时区','default':'Asia/Shanghai'},
        'at': {'type':'string','title':'一次性时间 · ISO 8601'}}, ('timing',))

    def calculate(params, after):
        timing=params['timing']
        if timing=='interval':
            interval=params.get('interval_seconds',300)
            if type(interval) is not int or not 30<=interval<=31536000:
                raise ValueError('间隔须为 30～31536000 秒')
            return after+interval
        if timing=='daily':
            return plugin.next_daily(params.get('daily_time','09:00'),params.get('timezone','Asia/Shanghai'),after)
        try:
            value=datetime.fromisoformat(params.get('at','').replace('Z','+00:00'))
            if value.tzinfo is None:
                raise ValueError()
            return value.timestamp()
        except (ValueError,AttributeError):
            raise ValueError('一次性时间须为带时区的 ISO 8601 时间') from None

    async def subscribe(params,emit):
        state_key='automation:timer:'+hashlib.sha256(encode(params).encode()).hexdigest()
        async def loop():
            state=plugin.runtime.store.kv_get(state_key,{})
            if state.get('done'):
                await asyncio.Event().wait()
            due=state.get('next_at') or calculate(params,time.time())
            plugin.runtime.store.kv_set(state_key,{'next_at':due})
            while True:
                await asyncio.sleep(max(0,due-time.time()))
                await emit({'scheduled_at':due,'observed_at':time.time()},uid=state_key+':'+str(due),topic='schedule.'+params['timing'])
                if params['timing']=='once':
                    plugin.runtime.store.kv_set(state_key,{'done':True})
                    await asyncio.Event().wait()
                due=calculate(params,time.time())
                plugin.runtime.store.kv_set(state_key,{'next_at':due})
        task=plugin.background(loop())
        async def close():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        return close

    plugin.trigger_source('schedule.*','定时触发',parameters,
        object_schema({'scheduled_at':{'type':'number'},'observed_at':{'type':'number'}},('scheduled_at','observed_at')),
        subscribe=subscribe,validate=lambda params:calculate(params,time.time()),legacy_ids=('schedule',))
