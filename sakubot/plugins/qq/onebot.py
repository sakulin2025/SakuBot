import asyncio
import json
import random
import time
import uuid

from websockets.asyncio.client import connect


class OneBot:
    def __init__(self, plugin):
        self.plugin, self.runtime = plugin, plugin.runtime
        self.ws = None
        self.pending = {}
        self.self_id = ""
        self.nickname = ""
        self.error = "尚未连接"
        self.retry_at = 0
        self.send_lock = asyncio.Lock()
        self.target_locks = {}
        self.online = asyncio.Event()

    async def call(self, action, params=None):
        if not self.online.is_set():
            raise RuntimeError("QQ 插件不可用：NapCat 未连接")
        params = params or {}
        if action in ("get_group_msg_history", "get_friend_msg_history"):
            target = "Group:" + str(params.get("group_id", "")) if action == "get_group_msg_history" else "Private:" + str(params.get("user_id", ""))
            return {"messages": self.runtime.messages.list(target, min(500, int(params.get("count", 20))))}
        if action == "get_msg":
            return self.runtime.messages.by_message_id(params.get("message_id", ""))
        if action == "get_forward_msg":
            return {"messages": []}
        return await self._call(action, params)

    async def _call(self, action, params=None):
        if not self.ws:
            raise RuntimeError("NapCat 尚未连接")
        echo = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[echo] = future
        try:
            async with self.send_lock:
                await self.ws.send(json.dumps({"action": action, "params": params or {}, "echo": echo}))
            packet = await asyncio.wait_for(future, 30)
            if packet.get("status") != "ok" or packet.get("retcode", 0) != 0:
                raise RuntimeError(f"NapCat 操作失败（retcode={packet.get('retcode')}）")
            return packet.get("data")
        finally:
            self.pending.pop(echo, None)

    async def reader(self):
        async for raw in self.ws:
            packet = json.loads(raw)
            if not isinstance(packet, dict):
                continue
            echo = packet.get("echo")
            if echo is not None:
                future = self.pending.get(str(echo))
                if future and not future.done():
                    future.set_result(packet)
            elif packet.get("post_type"):
                # Raw packets remain inside this plugin; interpretation runs on its receiver queue.
                await self.plugin.receiver.ingest(packet)

    def changed(self):
        self.runtime.registry.revision = uuid.uuid4().hex
        self.runtime.live.publish('plugin.state', plugin_id='qq', online=self.online.is_set(), error=self.error, retry_at=self.retry_at)

    async def run(self):
        failures, last_log = 0, 0.0
        while True:
            connected_at = None
            was_online = False
            try:
                settings = self.plugin.settings
                headers = {"Authorization": "Bearer " + settings.napcat_token} if settings.napcat_token else {}
                async with connect(settings.napcat_ws, additional_headers=headers, proxy=None,
                                   open_timeout=15, max_size=8 * 1024 * 1024) as ws:
                    self.ws = ws
                    reader = asyncio.create_task(self.reader())
                    try:
                        login = await self._call("get_login_info")
                        self.self_id = str(login["user_id"])
                        self.nickname = str(login.get("nickname", ""))
                        if self.self_id == settings.owner_id:
                            raise RuntimeError("Agent QQ 不能与主人 QQ 相同")
                        self.error, self.retry_at = "", 0
                        self.online.set()
                        was_online = True
                        connected_at = time.monotonic()
                        self.changed()
                        self.runtime.store.log("info", "qq", "qq.connected", data={"self_id": self.self_id})
                        await reader
                        raise RuntimeError('NapCat 连接已关闭')
                    finally:
                        reader.cancel()
                        await asyncio.gather(reader, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if connected_at is not None and time.monotonic() - connected_at >= 60:
                    failures = 0
                failures += 1
                delay = min(300, 5 * 2 ** min(failures - 1, 6))
                self.error = 'NapCat 未连接（' + type(exc).__name__ + '）'
                self.retry_at = time.time() + delay
                now = time.monotonic()
                if was_online or failures == 1 or now - last_log >= 60:
                    event = 'qq.disconnected' if was_online else 'qq.connect.failed' if failures == 1 else 'qq.reconnect.failed'
                    self.runtime.store.log('warning', 'qq', event, data={'error': type(exc).__name__, 'retry_seconds': delay, 'attempt': failures})
                    last_log = now
            finally:
                self.online.clear()
                self.ws = None
                for future in list(self.pending.values()):
                    if not future.done():
                        future.set_exception(RuntimeError("NapCat 连接中断；远端操作结果可能未知"))
                self.changed()
            await asyncio.sleep(delay)

    def owner_target(self):
        owner = self.plugin.settings.owner_id
        if not owner:
            raise ValueError("尚未绑定主人的私聊")
        return "private:" + owner

    @staticmethod
    def target_params(target):
        kind, _, identifier = target.partition(":")
        if kind not in ("private", "group") or not identifier.isdigit() or int(identifier) <= 0:
            raise ValueError("消息目的地应为 private:QQ号 或 group:群号")
        return {"user_id" if kind == "private" else "group_id": int(identifier)}

    def target_lock(self, target):
        return self.target_locks.setdefault(target, asyncio.Lock())

    async def send(self, target, content, delivery_id, segments=None):
        from .reply_split import batches
        settings = self.plugin.settings
        plan = batches(content, segments, settings)
        results = []
        async with self.target_lock(target):
            for index, message in enumerate(plan):
                if index:
                    await asyncio.sleep(random.uniform(settings.reply_interval_min, settings.reply_interval_max))
                # A disconnect terminates the rest of this response; never replay a partial send.
                if not self.online.is_set():
                    raise RuntimeError('QQ 已断线，剩余分段未发送；已发送内容不自动重放')
                identifier = delivery_id if len(plan) == 1 else delivery_id + ':part:' + str(index)
                text = ''.join(str(segment.get('data', {}).get('text', '')) for segment in message if segment.get('type') == 'text')
                params = {**self.target_params(target), 'message': message}
                results.append(await self.action('send_msg', params, identifier, target, text))
        if len(results) == 1:
            return results[0]
        return {'parts': len(results), 'results': results, 'skipped': not results}

    async def action(self, action, params, delivery_id, target="", text=""):
        store = self.runtime.store
        old = store.one("SELECT * FROM deliveries WHERE id=?", (delivery_id,))
        if old:
            if old["status"] == "sent":
                return json.loads(old["result"])
            if old["status"] != "pending":
                raise RuntimeError("该操作已有记录且结果不确定或失败，不自动重试，请检查执行记录")
            store.execute("UPDATE deliveries SET status='sending' WHERE id=?", (delivery_id,))
        else:
            store.execute("""INSERT INTO deliveries (id,target,text,action,params,status,at)
              VALUES (?,?,?,?,?,'sending',?)""", (delivery_id, target, text, action, json.dumps(params, ensure_ascii=False), time.time()))
        try:
            result = await self.call(action, params)
            store.execute("UPDATE deliveries SET status='sent', result=? WHERE id=?",
                          (json.dumps(result, ensure_ascii=False), delivery_id))
            if action == "send_msg" and target:
                self.plugin.receiver.record_sent(target, text or "[消息附件]", delivery_id)
            store.log("info", "qq", "qq.action.completed", data={"delivery_id": delivery_id, "action": action, "target": target})
            return result
        except BaseException:
            store.execute("UPDATE deliveries SET status='uncertain', error='操作失败或连接中断，远端结果可能未知；不自动重试' WHERE id=?", (delivery_id,))
            store.log("warning", "qq", "qq.action.uncertain", data={"delivery_id": delivery_id, "action": action})
            raise
