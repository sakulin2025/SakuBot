import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    name = 'messaging'

    def setup(self):
        self.tool('message_sources', '查看框架声明的主对话源、可用状态、支持的消息类型和当前响应路由。网页始终同步；插件对话源按运行设置中的广播或智能模式投递，不假定目标一定是 QQ。', object_schema(), self.sources)
        part = object_schema({'type': {'type': 'string', 'enum': ['text', 'image', 'video', 'audio', 'file']},
            'text': text('text 类型正文'), 'url': text('媒体 HTTP/HTTPS 地址或框架附件 URL'),
            'path': text('共享工作空间中的本地文件相对路径；与 url 二选一'), 'name': text('可选文件名')}, ('type',))
        self.tool('message_send', '向当前主对话发送一组文字、图片、视频、音频或文件，使用框架响应路由，网页会同步，QQ 离线也能使用。仅主 Agent 可调用，协作 Agent 把产物交回主 Agent。媒体传 url 或共享工作空间 path，文件会发布为框架附件。返回 submitted 表示已提交，不代表所有对话源送达；不支持的消息类型不影响其他源。普通最终文字直接回答即可，调用此工具后不要重复发送同一内容。',
            object_schema({'parts': {'type': 'array', 'items': part, 'minItems': 1, 'maxItems': 10}}, ('parts',)), self.send)

    async def sources(self, invocation, args):
        conversation = self.runtime.conversation
        return {**conversation.catalog(), 'mode': self.runtime.config.settings.conversation.mode,
            'targets': conversation.targets(), 'web_synced': True}

    async def send(self, invocation, args):
        if invocation.agent_id != 'main':
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
