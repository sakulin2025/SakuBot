from .tool_arguments import ARGUMENTS
from .tool_types import R_message_select_source, R_message_send, R_message_set_source_trust, R_message_sources
from .tool_types import RESULTS
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from sakubot.plugin import Plugin, object_schema, text
from .types import SendResult


class Extension(Plugin):
    tool_result_types = RESULTS
    tool_argument_types = ARGUMENTS
    name = 'messaging'

    def setup(self):
        self.tool('message_sources', '查看框架声明的主对话源、可用状态、支持的消息类型和当前响应路由。网页始终同步；插件对话源在唤醒实际处理时切换，后续输出跟随当前源，不假定对话源的类型。', None, self.sources)
        self.tool('message_select_source', '运行中主动切换主会话响应源。先用 message_sources 获取准确 source_id。切换立即生效并持久保存，后续输出跟随新源；不会开启或关闭本轮投递，不撤回已发消息。可选离线源，但其外部投递可能失败，网页仍可见。请确认接收者与保密边界。',
            None, self.select_source, audience='main')
        self.tool('message_set_source_trust', '设置主会话源是否可信。只有实际由可信来源唤醒、且本轮未吸收不可信输入时才允许；主动切换到可信响应源不能获得该权限。网页管理端认证会话可操作。先用 message_sources 获取 source_id。',
            None, self.set_source_trust, audience='main')
        part = object_schema({'type': {'type': 'string', 'enum': ['text', 'image', 'video', 'audio', 'file']},
            'text': text('text 类型正文'), 'url': text('媒体 HTTP/HTTPS 地址或框架附件 URL'),
            'path': text('共享工作空间中的本地文件相对路径；与 url 二选一'), 'name': text('可选文件名')}, ('type',))
        self.tool('message_send', '向当前主对话发送一组文字、图片、视频、音频或文件，使用框架响应路由，网页始终同步。主 Agent 和脚本可调用，协作 Agent 把产物交回主 Agent。媒体传 url 或共享工作空间 path，文件会发布为框架附件。返回 submitted 表示已提交，不代表所有对话源送达；不支持的消息类型不影响其他源。普通最终文字直接回答即可，调用此工具后不要重复发送同一内容。',
            None, self.send, result_type=SendResult)

    async def sources(self, invocation, args) -> R_message_sources:
        conversation = self.runtime.conversation
        return {**conversation.catalog(), 'mode': self.runtime.config.settings.conversation.mode,
            'targets': conversation.targets(), 'web_synced': True}

    async def set_source_trust(self, invocation, args) -> R_message_set_source_trust:
        from sakubot.source_trust import may_manage
        if not may_manage(self.runtime, invocation):
            raise ValueError('本轮并非由可信主会话源唤醒，或已吸收不可信输入，不能修改信任状态；切换响应源不能提升权限')
        self.runtime.conversation.set_trust(args['source_id'], args['trusted'], requester='agent', run_id=invocation.run_id)
        return await self.sources(invocation, {})

    async def select_source(self, invocation, args) -> R_message_select_source:
        if invocation.agent_id != 'main':
            raise ValueError('只能由主智能体切换主会话源')
        from sakubot.wake_routing import change_source
        changed, notice = change_source(self.runtime, args['source_id'], invocation)
        if notice:
            invocation.metadata.setdefault('_pending_source_notices', []).append(notice)
        return {**await self.sources(invocation, {}), 'changed': changed,
            'send_result_to_source': invocation.send_result_to_source, 'explicit_target': invocation.metadata.get('reply_target', '')}

    async def send(self, invocation, args) -> R_message_send:
        if invocation.agent_id != 'main' and invocation.origin != 'script':
            raise ValueError('仅主 Agent 可发送主对话消息，请把产物交回主 Agent')
        prepared = []
        for item in args['parts']:
            kind = item['type']
            if kind == 'text':
                if not item.get('text', '').strip() or item.get('url') or item.get('path'):
                    raise ValueError('文字消息需要正文，不接受媒体路径')
                if len(item['text']) > 20000:
                    raise ValueError('单条文字不能超过20000字符')
                prepared.append({'type': kind, 'text': item['text']})
                continue
            if bool(item.get('path')) == bool(item.get('url')):
                raise ValueError('媒体需要提供 path 或 url，二选一')
            if item.get('path'):
                path = self.workspace.path(item['path'], allow_root=False)
                if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                    raise ValueError('文件不存在或超过20 MiB')
                prepared.append({'type': kind, '_path': path, 'name': Path(item.get('name') or path.name).name})
            else:
                url = item['url']
                if urlsplit(url).scheme not in ('http', 'https') and not re.fullmatch('/api/artifacts/[a-f0-9]{64}', url):
                    raise ValueError('媒体 URL 需要为 HTTP/HTTPS 地址或框架附件 URL')
                if len(url) > 4000:
                    raise ValueError('媒体 URL 过长')
                prepared.append({'type': kind, 'url': url, 'name': Path(item.get('name') or 'attachment').name})
        # Validate all parts before publishing files or submitting any response.
        for item in prepared:
            if '_path' in item:
                item.update(self.artifact(item.pop('_path'), item['name']))
        response_id = uuid.uuid4().hex
        await self.respond_main(prepared, invocation=invocation, response_id=response_id)
        return {'submitted': True, 'response_id': response_id, 'parts': len(prepared)}
