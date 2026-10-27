import asyncio
import hashlib
import json
import time
from sakubot.messages import session_id
from sakubot.store import encode


class Receiver:
    def __init__(self, plugin):
        self.plugin, self.runtime = plugin, plugin.runtime
        self.queue = asyncio.Queue(maxsize=1000)

    async def ingest(self, packet):
        await self.queue.put(packet)

    async def run(self):
        while True:
            packet = await self.queue.get()
            try:
                await self.process(packet)
            except Exception as exc:
                self.runtime.store.log('error', self.plugin.id, 'message.processing.failed', data={'error': type(exc).__name__})
            finally:
                self.queue.task_done()

    async def process(self, packet):
        if packet.get("post_type") != "message":
            if packet.get("post_type") in ("notice", "request"):
                info = {key: packet[key] for key in ("post_type", "notice_type", "request_type", "sub_type", "user_id", "group_id", "flag") if key in packet}
                self.runtime.store.log("info", self.plugin.id, "notification.archived", data=info)
            return
        actor = str(packet.get("user_id", ""))
        if not actor.isdigit() or actor == str(packet.get("self_id", "")):
            return
        group = str(packet.get("group_id", ""))
        session = session_id(("Group:" + group) if group else ("Private:" + actor))
        mid = packet.get("message_id")
        uid = f"qq:{packet.get('self_id')}:{mid}" if mid is not None else "qq:" + hashlib.sha256(encode(packet).encode()).hexdigest()
        if self.runtime.store.one("SELECT id FROM processed_messages WHERE uid=?", (uid,)):
            return
        sender = packet.get("sender") or {}
        label = str(sender.get("card") or sender.get("nickname") or actor)
        previous = self.runtime.store.one("SELECT data FROM people WHERE id=?", (actor,))
        person = json.loads(previous["data"]) if previous else {"id": actor, "aliases": [], "groups": {}}
        person["nickname"] = str(sender.get("nickname") or person.get("nickname") or label)
        person["aliases"] = list(dict.fromkeys([*person.get("aliases", []), label]))[-30:]
        if group:
            person["groups"][group] = label
        self.runtime.store.execute("INSERT OR REPLACE INTO people VALUES (?,?,?)", (actor, encode(person), time.time()))
        segments = packet.get("message", [])
        if not isinstance(segments, list):
            segments = [{"type": "text", "data": {"text": str(segments)}}]
        parts, mentions, reply_to = [], [], ""
        for segment in segments:
            kind, data = segment.get("type"), segment.get("data") or {}
            if kind == "text":
                parts.append({"type": "text", "text": str(data.get("text", ""))})
            elif kind == "at":
                identifier = str(data.get("qq", ""))
                if identifier == "all" or identifier.isdigit():
                    mentions.append(identifier)
                    parts.append({"type": "mention", "text": "@" + identifier, "id": identifier})
            elif kind == "image":
                text, status = await self.runtime.messages.describe_image(data)
                parts.append({"type": "image", "text": text, "status": status})
            elif kind in ("record", "input_audio"):
                parts.append({"type": "audio", "text": "[语音未识别]", "status": "unimplemented"})
            elif kind == "reply":
                reply_to = str(data.get("id", ""))
                parts.append({"type": "reply", "text": "[回复消息 " + reply_to + "]", "id": reply_to})
            else:
                parts.append({"type": "attachment", "text": "[" + str(kind)[:40] + "]"})
        record = {"uid": uid, "at": time.time(), "session_id": session, "message_id": str(mid or ""),
            "sender_id": actor, "sender_name": label, "text": "".join(row["text"] for row in parts)[:100000],
            "mentions": mentions, "reply_to": reply_to, "parts": parts, "is_self": False}
        direct = not group and actor == self.plugin.settings.owner_id
        record.update(source=self.plugin.id, is_owner=direct or actor == self.plugin.settings.owner_id,
            is_main_source=direct, mentions_self=self.plugin.client.self_id in mentions,
            identity={'self_id': self.plugin.client.self_id, 'owner_id': self.plugin.settings.owner_id})
        if direct:
            await self.plugin.receive_main('owner', record['text'] or '[消息附件]',
                actor=actor, label=label, uid=uid, meta={'message': record, 'source_label': 'QQ'})
        await self.plugin.publish_message(record)

    def record_sent(self, target, text, delivery_id):
        if self.runtime.store.one("SELECT id FROM processed_messages WHERE uid=?", (delivery_id,)):
            return
        self.runtime.messages.persist({"uid": delivery_id, "at": time.time(), "session_id": session_id(target), "message_id": "",
            "source": self.plugin.id, "sender_id": self.plugin.client.self_id, "sender_name": self.plugin.client.nickname, "text": text,
            "mentions": [], "reply_to": "", "parts": [{"type": "text", "text": text}], "is_self": True})
