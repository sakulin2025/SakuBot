"""Plugin-owned trigger declarations and shared, disposable subscriptions."""
import asyncio
import inspect
import re
from fnmatch import fnmatchcase
import time
import uuid

import jsonschema
from .repository import schema, identifier
from sakubot.store import encode


class Sources:
    def __init__(self, scripts):
        self.scripts = scripts
        self.sources = {}
        self.active = {}
        self.stopping = False
        self.retry = {}
        self.lock = asyncio.Lock()

    def declare(self, owner, key, name, parameters, event_schema, *, id_description="", subscribe=None, options=None, match=None, validate=None, legacy_ids=()):
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.*:-]{1,128}',key):
            raise ValueError('触发源名称无效')
        full = owner + '.' + key
        if full in self.sources:
            raise ValueError('触发源 ID 已存在')
        parameters, event_schema = parameters or {}, event_schema or {}
        self.sources[full] = {'id':full,'plugin_id':owner,'name':name,'parameters':parameters,
            'event_schema':event_schema,'id_description':id_description,'subscribe':subscribe,'options':options,'match':match,'validate':validate,'generation':uuid.uuid4().hex}
        # A declaration upgrade preserves binding IDs, actions and parameter filters.
        for binding in self.scripts.repo.list('bindings'):
            if binding['source'] in {owner + '.' + value for value in legacy_ids}:
                try:
                    self.scripts.save_binding({**binding, 'source': full})
                except (ValueError, jsonschema.ValidationError) as exc:
                    self.scripts.runtime.store.log('warning', owner, 'trigger.binding.migration_failed',
                        data={'binding_id': binding['id'], 'error': str(exc)[:300]})
        return full

    def resolve(self, key):
        if not isinstance(key,str):
            return None
        exact = self.sources.get(key)
        if exact:
            return exact
        candidates = [source for pattern,source in self.sources.items() if '*' in pattern and fnmatchcase(key,pattern)]
        return max(candidates,key=lambda item:len(item['id'].replace('*','')),default=None)

    def manifest(self):
        return [{**{k:v for k,v in row.items() if k not in ('subscribe','options','match','validate','generation')},
                 'available':self.scripts.runtime.registry.availability(row['plugin_id'])['available']}
                for row in self.sources.values()]

    async def options(self, key):
        source = self.resolve(key)
        if not source:
            return {}
        callback = source.get('options')
        if not callback:
            return {}
        result = callback()
        return await result if inspect.isawaitable(result) else result

    def remove_owner(self, owner):
        self.retry = {key:value for key,value in self.retry.items() if not key.startswith(owner+'.')}
        for key in [key for key, row in self.sources.items() if row['plugin_id'] == owner]:
            del self.sources[key]
        for key, item in list(self.active.items()):
            if item['owner'] == owner:
                self._detach(key)

    def _detach(self, key):
        item = self.active.pop(key, None)
        if not item:
            return
        async def close():
            task = item.get('task')
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            cleanup = item.get('cleanup')
            if cleanup:
                result = cleanup()
                if inspect.isawaitable(result):
                    await result
        self.scripts.spawn(close())

    async def reconcile(self):
        async with self.lock:
            await self._reconcile()

    async def _reconcile(self):
        desired = {}
        for binding in self.scripts.trigger_consumers():
            if not binding.get('enabled') or not binding.get('eligible'):continue
            sources=[row for key,row in self.sources.items()
                if fnmatchcase(binding['source'],key) or fnmatchcase(key,binding['source'])]
            for source in sources:
                if not self.scripts.runtime.registry.availability(source['plugin_id'])['available']:continue
                key = source['id'] + ':' + encode(binding['source_params'])
                desired[key] = (source, binding['source_params'])
        for key in list(self.active):
            wanted = desired.get(key)
            if not wanted or self.active[key]['generation'] != wanted[0]['generation']:
                self._detach(key)
        for key, (source, params) in desired.items():
            if key in self.active or not source.get('subscribe') or self.retry.get(key,{}).get('at',0)>time.time():
                continue
            item = {'owner':source['plugin_id'], 'generation':source['generation']}
            self.active[key] = item
            async def start(source=source, params=params, key=key, item=item):
                async def emit(payload, uid=None, topic=None):
                    if self.sources.get(source['id'], {}).get('generation') != source['generation']:
                        return []
                    return await self.emit(source['plugin_id'], topic or source['id'].split('.',1)[1], payload, uid=uid, subscription=params)
                try:
                    result = source['subscribe'](params, emit)
                    cleanup = await result if inspect.isawaitable(result) else result
                    item['cleanup'] = cleanup
                    self.retry.pop(key,None)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.active.pop(key, None)
                    previous=self.retry.get(key,{})
                    delay=min(120,previous.get('delay',2.5)*2)
                    self.retry[key]={'at':time.time()+delay,'delay':delay}
                    self.scripts.runtime.store.log('error','scripts','trigger.subscribe.failed',data={'source':source['id'],'error':str(exc)[:300]})
            item['task'] = self.scripts.spawn(start())

    def matches(self,pattern,payload,params,*,subscription=None):
        definition=self.resolve(pattern)
        matcher=definition.get('match') if definition else None
        if matcher:return matcher(payload,params)
        if subscription is not None:return True
        return all(value in ('',None,[]) or payload.get(field)==value for field,value in params.items())

    async def emit(self, owner, key, payload, *, uid=None, subscription=None):
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,512}',key):
            raise ValueError('实际事件名称无效，不能带通配符')
        full = owner + '.' + key
        source = self.resolve(full)
        if self.scripts.stopping or not self.scripts.runtime.registry.loaded(owner):
            return []
        if not isinstance(payload,dict) or len(encode(payload).encode()) > 262144:
            raise ValueError('触发数据须为不超过 256 KiB 的对象')
        uid = uid or uuid.uuid4().hex
        queued,block_scripts=self.scripts.listeners.dispatch(full,payload,uid,subscription)
        for binding in self.scripts.bindings():
            if not binding.get('enabled') or not binding.get('eligible') or not fnmatchcase(full,binding['source']):
                continue
            if block_scripts and binding.get('target_kind','script')=='script':continue
            params = binding['source_params']
            if subscription is not None and params != subscription:
                continue
            event = {'id':uid,'source':full,'at':time.time(),'data':payload}
            execution_uid = binding['id'] + ':' + str(uid)
            try:
                if not self.matches(binding['source'],payload,params,subscription=subscription):continue
                queued.append(self.scripts.enqueue_binding(binding, event, execution_uid))
            except Exception as exc:
                error = str(exc)[:300] if isinstance(exc,(ValueError,RuntimeError)) else type(exc).__name__
                self.scripts.trigger_failure(binding,event,execution_uid,error)
        return queued

    async def stop(self):
        self.sources.clear()
        for key in list(self.active):
            self._detach(key)
