import hashlib
import json
import time
from pathlib import Path

from sakubot.plugin import Plugin, object_schema, text
from sakubot.store import encode
from pydantic import ValidationError
from .config import Settings
from .onebot import OneBot
from .receiver import Receiver
from .external_reply import ExternalReplies


READ_ACTIONS = ["get_login_info", "get_friend_list", "get_group_list", "get_group_info",
                "get_group_member_list", "get_group_member_info", "get_stranger_info",
                ]


class Extension(ExternalReplies, Plugin):
    name = "qq"

    def availability(self):
        settings = self.settings
        return {"available": self.client.online.is_set(), "reason": self.client.error if settings.owner_id and settings.napcat_ws else "未配置连接"}

    def setup(self):
        import asyncio
        self.config_lock = asyncio.Lock()
        self.runtime.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS people (
          id TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL NOT NULL);
        """)
        self.runtime.store.execute("UPDATE people SET data=json_remove(data,'$.is_owner') WHERE json_type(data,'$.is_owner') IS NOT NULL")
        self.config_path = self.data_dir / 'config.json'
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = Settings.model_validate(json.loads(self.config_path.read_text()) if self.config_path.exists() else {})
        self.receiver = Receiver(self)
        self.client = OneBot(self)
        self.page('manage', 'QQ', Path(__file__).parent / 'web' / 'dist', icon='connection', order=15,
            aliases=('/qq', '/connection', '/people', '/extensions/qq/connection', '/extensions/qq/people', '/extensions/external_reply/manage'))
        self.api('config', self.get_config)
        self.api('config', self.save_config, methods=('POST',))
        self.api('status', self.status)
        self.delivery_adapter('message', self.deliver, accepts=self.accepts_target, timeout=None)
        self.setup_replies()

        self.conversation_source('owner', 'QQ 主人私聊',
            handlers={kind: self.main_response for kind in ('text', 'image', 'video', 'file', 'audio')},
            availability=self.availability, timeout=None)
        self.api("people", self.people_records)
        self.tool('people_lookup', '通过 QQ ID 或昵称检索曾见过的人，返回稳定 ID、昵称和群名片。同名需区分 ID。',
            object_schema({'query': text()}, ('query',)), self.people_lookup)
        self.tool("qq_send", "向指定 QQ 私聊或群聊发消息。默认本轮来源会话；主人的固定私聊可填 owner。发给主人私聊的相同最终文本不会重复投递到 QQ；其他源仍可接收。",
                  object_schema({"target": text("owner、private:QQ号、group:群号，留空使用本轮来源"),
                                 "text": text("要发送的文字"), "segments": {"type": "array", "items": {"type": "object"}, "maxItems": 30}}, ()),
                  self.send)
        self.tool("qq_read", "查询 NapCat 中的 QQ 资料和消息。按真实 ID 识别人，不用昵称作为身份。查询接口包括好友、群、成员、消息及历史；params 使用对应 OneBot 接口参数。",
                  object_schema({"action": {"type": "string", "enum": READ_ACTIONS}, "params": {"type": "object"}}, ("action",)),
                  self.read)
        self.tool("qq_action", "操作 Agent 自己的 QQ 账号，调用 NapCat 原生接口。用于好友/群请求、群管理、撤回、账号资料和文件等写操作。action/params 必须来自已知接口或 qq_api 文档；不能凭空编造。结果未知不自动重试，普通发送优先 qq_send。",
                  object_schema({"action": text("NapCat OneBot action 名称"), "params": {"type": "object"}}, ("action",)), self.action)
        self.tool("qq_recent", "按需查询归档的 QQ 消息，可指定群聊或私聊。归档消息不会自动加入主上下文。返回人员 ID、昵称和引用等元数据。",
                  object_schema({"target": text("可选 private:QQ号 或 group:群号"),
                                 "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, ()),
                  self.recent)
        self.tool("qq_notices", "按需查询归档的 QQ 通知和好友、加群请求，可获取处理请求所需的 flag。不会自动加入主上下文。",
                  object_schema({"before": {"type": "integer", "minimum": 1},
                                 "limit": {"type": "integer", "minimum": 1, "maximum": 100}}), self.notices)
        self.tool("qq_api", "返回 QQ 原生 API 文档入口及常用参数说明。用于选择正确的账号操作接口。",
                  object_schema(), self.api_documentation)

    async def start(self):
        self.isolate_archives()
        # Retire work queued by the removed built-in group routing feature.
        self.runtime.store.execute("UPDATE events SET status='recorded' WHERE source='qq' AND status='routing'")
        self.runtime.store.execute("UPDATE events SET status='cancelled',error='内置群聊唤醒已移除' WHERE source='qq' AND kind='wake' AND status='pending' AND target LIKE 'group:%'")
        self.background(self.receiver.run())
        self.connection_job = None
        if self.settings.owner_id and self.settings.napcat_ws:
            self.connection_job = self.background(self.client.run())

    def isolate_archives(self):
        # Retain historical audit rows while removing accidental main-context entries.
        changed = self.runtime.store.execute("""UPDATE events
            SET meta=json_set(meta,'$.exclude_context',json('true'),'$.exclude_main',json('true'))
            WHERE (source='qq-notice'
              OR (source='qq' AND json_extract(meta,'$.exclude_main')=1)
              OR (source='agent' AND json_extract(meta,'$.delivery') IS NOT NULL AND target!=?))
              AND (coalesce(json_extract(meta,'$.exclude_context'),0)=0
                OR coalesce(json_extract(meta,'$.exclude_main'),0)=0)""",
            ('private:' + self.settings.owner_id,)).rowcount
        if changed:
            # Rebuild history from eligible events after the last explicit clear.
            # A previous LLM summary cannot be selectively scrubbed reliably.
            boundary = self.runtime.chat.boundary()
            self.runtime.store.kv_set('agent:main-summary', {'cutoff': boundary['cutoff'], 'text': ''})
            self.runtime.store.log('info', self.id, 'context.archives.isolated', data={'records': changed})

    def onboarding(self):
        return [{'key': self.id + '.connection', 'title': '连接 NapCat', 'icon': 'connection',
            'path': '/extensions/' + self.id + '/manage', 'completed': self.client.online.is_set()}]

    def prompt_context(self, invocation):
        return 'QQ 插件：主人 QQ=' + self.settings.owner_id + '，账号 QQ=' + self.client.self_id + '。向其他 QQ 会话发送请使用 qq_send，owner 表示主人固定私聊。'

    @staticmethod
    def accepts_target(target):
        try:
            OneBot.target_params(target)
            return True
        except ValueError:
            return False

    async def deliver(self, packet):
        return await self.send_part(packet['target'], packet)

    async def status(self, request):
        return {'online': self.client.online.is_set(), 'self_id': self.client.self_id, 'nickname': self.client.nickname,
            'error': self.client.error, 'retry_at': self.client.retry_at}

    async def get_config(self, request):
        values = self.settings.model_dump()
        values['napcat_token_configured'] = bool(values.pop('napcat_token'))
        return values

    async def save_config(self, request):
        import asyncio
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError('配置格式不正确')
        if not data.get('napcat_token'):
            data['napcat_token'] = self.settings.napcat_token
        try:
            settings = Settings.model_validate(data)
        except ValidationError as exc:
            reason = exc.errors(include_input=False)[0]['msg'].removeprefix('Value error, ')
            raise ValueError('配置无效：' + reason) from None
        # Reconfigure only this connection; do not reload the plugin or framework.
        async with self.config_lock:
            self.runtime.config.atomic(self.config_path, settings.model_dump_json(indent=2) + '\n')
            reconnect = any(getattr(settings, key) != getattr(self.settings, key) for key in ('owner_id', 'napcat_ws', 'napcat_token'))
            if reconnect and self.connection_job:
                self.connection_job.cancel()
                await asyncio.gather(self.connection_job, return_exceptions=True)
                if self.connection_job in self.jobs:
                    self.jobs.remove(self.connection_job)
            self.settings = settings
            if reconnect:
                self.connection_job = None
                if settings.owner_id and settings.napcat_ws:
                    self.connection_job = self.background(self.client.run())
            self.client.changed()
        return await self.get_config(request)

    async def main_response(self, packet):
        return await self.send_part(self.client.owner_target(), packet)

    async def send_part(self, target, packet):
        from sakubot.artifacts import media_url
        packet = {**packet, 'url': media_url(packet.get('url', ''))}
        kind = packet['type']
        if kind == 'text':
            return await self.client.send(target, packet['text'], packet['delivery_id'] + ':qq')
        if kind == 'file':
            params = OneBot.target_params(target)
            action = 'upload_group_file' if 'group_id' in params else 'upload_private_file'
            async with self.client.target_lock(target):
                return await self.client.action(action,
                    {**params, 'file': packet['url'],
                     'name': packet.get('name') or 'file'}, packet['delivery_id'] + ':qq', target)
        segment = {'type': 'record' if kind == 'audio' else kind, 'data': {'file': packet['url']}}
        return await self.client.send(target, '', packet['delivery_id'] + ':qq', [segment])

    async def people_lookup(self, inv, args):
        query = args['query'].casefold()
        return [row['data'] for row in self.runtime.store.list_records('people') if query in str(row['data']).casefold()][:50]

    async def people_records(self, request):
        return self.runtime.store.list_records("people")

    async def send(self, inv, args):
        target = args.get("target") or inv.target
        if target in ("owner", "main"):
            target = self.client.owner_target()
        segments = args.get("segments")
        content = args.get("text", "")
        if not content.strip() and not segments:
            raise ValueError("消息不能为空")
        result = await self.client.send(target, content, inv.run_id + ":" + inv.call_id, segments)
        if target == self.client.owner_target():
            inv.metadata.setdefault('sent_source_texts', {}).setdefault(self.id + '.owner', []).append(content)
        archived = inv.agent_id != 'main' or target != self.client.owner_target()
        self.runtime.store.event("context", "agent", content or "[消息附件]", target=target,
                                meta={"role": "assistant", "run_id": inv.run_id, "delivery": inv.run_id + ":" + inv.call_id, "source_label": "QQ",
                                      "exclude_context": archived, "exclude_main": archived})
        return result

    async def read(self, inv, args):
        return await self.client.call(args["action"], args.get("params", {}))

    async def action(self, inv, args):
        action = args["action"]
        if action in READ_ACTIONS:
            return await self.read(inv, args)
        if action in ("send_msg", "send_private_msg", "send_group_msg"):
            raise ValueError("发送消息请使用 qq_send，以便记录目的地和避免重复回复")
        return await self.client.action(action, args.get("params", {}), inv.run_id + ":" + inv.call_id)

    async def recent(self, inv, args):
        target = args.get("target") or inv.target
        if target in ('main', 'owner'):
            target = self.client.owner_target()
        return self.get_messages(target, args.get("limit", 30))

    async def notices(self, inv, args):
        rows = self.runtime.store.rows("""SELECT id,at,data FROM logs WHERE source='qq'
            AND event='notification.archived' AND id<? ORDER BY id DESC LIMIT ?""",
            (args.get('before') or 9223372036854775807, args.get('limit', 30)))
        return {'items': [{**row, 'data': json.loads(row['data'])} for row in rows],
                'next_before': rows[-1]['id'] if rows else None}

    async def api_documentation(self, inv, args):
        return {"docs": "https://napneko.github.io/api/", "read_actions": READ_ACTIONS,
                "examples": {"get_group_member_info": {"group_id": 123, "user_id": 456},
                             "get_msg": {"message_id": 123}, "set_group_ban": {"group_id": 123, "user_id": 456, "duration": 600},
                             "set_friend_add_request": {"flag": "来自request事件", "approve": True}}}
