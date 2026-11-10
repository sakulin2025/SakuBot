"""Shared ordered delivery for automatic replies and Agent sends."""
import asyncio
import random

from .config import Settings
from .reply_split import split_reply


class Sender:
    def __init__(self, plugin):
        self.plugin = plugin
        self.channels = {}

    async def send(self, channel, message, *, root_id='', file_ids=()):
        # Keep one complete split reply together, including calls from other Agents.
        entry = self.channels.setdefault(channel, [asyncio.Lock(), 0])
        entry[1] += 1
        try:
            async with entry[0]:
                settings = Settings.model_validate(dict(self.plugin.config))
                parts = [part for piece in split_reply(message, settings)
                         for offset in range(0, len(piece), 12000)
                         if (part := piece[offset:offset + 12000]).strip()]
                if not parts:
                    if file_ids:
                        parts = ['']
                    elif message.strip():
                        raise ValueError('分段和移除规则处理后消息为空，未发送')
                    else:
                        return []
                selected_root = root_id() if callable(root_id) else root_id
                posts = []
                for index, part in enumerate(parts):
                    try:
                        if index:
                            await asyncio.sleep(random.uniform(settings.reply_interval_min, settings.reply_interval_max))
                        if not self.plugin.online or not self.plugin.http:
                            raise RuntimeError('Mattermost 已断线')
                        body = {'channel_id': channel, 'message': part}
                        if selected_root:
                            body['root_id'] = selected_root
                        if index == 0 and file_ids:
                            body['file_ids'] = list(file_ids)
                        result = await self.plugin.request_json('POST', 'api/v4/posts', body=body, truncate=False)
                        if not isinstance(result, dict) or not isinstance(result.get('id'), str) or not result['id']:
                            raise RuntimeError('远端未返回消息 ID，本段发送结果未知')
                        posts.append(result)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        ids = ', '.join(post['id'] for post in posts[:10]) or '无'
                        reason = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
                        raise RuntimeError(f'已确认发送 {len(posts)}/{len(parts)} 段，消息 ID：{ids}。'
                                           f'第 {index + 1} 段失败或结果未知，剩余分段未重试；请先查询消息再处理。{reason}') from None
                return posts
        finally:
            entry[1] -= 1
            if not entry[1]:
                self.channels.pop(channel, None)
