"""Explicit-destination notifications delivered through plugin-owned adapters."""
import asyncio
import json
import inspect
import re
import time

from .store import encode


class Deliveries:
    def __init__(self, runtime):
        self.runtime = runtime
        self.adapters = {}

    def declare(self, owner, identifier, handler, accepts, availability, timeout=30):
        key = owner + '.' + identifier
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,40}', identifier) or key in self.adapters:
            raise ValueError('投递适配器 ID 无效或重复')
        self.adapters[key] = {'owner': owner, 'handler': handler, 'accepts': accepts, 'availability': availability, 'timeout': timeout}
        return key

    def remove_owner(self, owner):
        self.adapters = {key: value for key, value in self.adapters.items() if value['owner'] != owner}

    def resolve(self, target):
        matched = []
        for key, value in self.adapters.items():
            try:
                if value['accepts'](target):
                    matched.append(key)
            except Exception:
                continue
        if len(matched) != 1:
            raise ValueError('目标没有可用的投递适配器或存在重复声明')
        return matched[0]

    def enqueue(self, target, text, uid):
        return self.enqueue_part(target, {'type': 'text', 'text': text}, uid)

    def enqueue_part(self, target, part, uid):
        try:
            adapter = self.resolve(target)
        except ValueError:
            adapter = 'auto'
        packet = {**part, 'target': target, 'delivery_id': uid}
        text = packet.get('text', '')
        self.runtime.store.execute("INSERT OR IGNORE INTO deliveries(id,target,text,action,params,status,at) VALUES (?,?,?,?,?,'pending',?)",
            (uid, target, text, 'adapter:' + adapter, encode(packet), time.time()))
        return uid

    @staticmethod
    def available(adapter):
        try:
            return adapter['availability']().get('available', True)
        except Exception:
            return False

    @staticmethod
    async def invoke(adapter, packet):
        result = adapter['handler'](packet)
        return await result if inspect.isawaitable(result) else result

    async def worker(self):
        store = self.runtime.store
        while True:
            # Query each registered adapter independently so an offline destination cannot starve others.
            for row in store.rows("SELECT * FROM deliveries WHERE status='pending' AND action='adapter:auto'"):
                try:
                    key = self.resolve(row['target'])
                except ValueError:
                    continue
                store.execute('UPDATE deliveries SET action=? WHERE id=?', ('adapter:' + key, row['id']))
            rows = []
            for key, adapter in list(self.adapters.items()):
                if self.available(adapter):
                    rows.extend(store.rows("SELECT * FROM deliveries WHERE status='pending' AND action=? ORDER BY at LIMIT 10", ('adapter:' + key,)))
            for row in rows:
                adapter = self.adapters.get(row['action'][8:])
                if not adapter or not self.available(adapter):
                    continue
                store.execute("UPDATE deliveries SET status='sending' WHERE id=?", (row['id'],))
                task = asyncio.create_task(self.invoke(adapter, json.loads(row['params'])))
                owned = self.runtime.registry.inflight.setdefault(adapter['owner'], set())
                owned.add(task)
                try:
                    result = await asyncio.wait_for(task, adapter['timeout'])
                    store.execute("UPDATE deliveries SET status='sent',result=? WHERE id=?", (encode(result), row['id']))
                except BaseException as exc:
                    store.execute("UPDATE deliveries SET status='uncertain',error=? WHERE id=?", (type(exc).__name__, row['id']))
                    if isinstance(exc, asyncio.CancelledError) and asyncio.current_task().cancelling():
                        raise
                finally:
                    owned.discard(task)
            await asyncio.sleep(1)
