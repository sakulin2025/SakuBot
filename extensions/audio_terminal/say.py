"""Explicit speech tools work independently of the selected main reply source."""
import asyncio
import contextlib
from uuid import uuid4

from sakubot.speech_audio import PCMResampler, wav_bytes
from .conversation import speech_parts


class SayTools:
    async def stop_playback(self, device: str):
        """停止设备播放，同时取消尚未开始播放的主动说话。"""
        identity = self.resolve(device)
        epochs = getattr(self, 'say_epochs', None)
        if epochs is None:
            self.say_epochs = epochs = {}
        epochs[identity] = epochs.get(identity, 0) + 1
        return await super().stop_playback(identity)

    def speech_device(self, requested=''):
        if requested:
            return self.resolve(requested)
        sessions = {row['device'] for row in self.voice_sessions.values()}
        if len(sessions) == 1:
            return self.resolve(next(iter(sessions)))
        default = self.config.get('default_device', '')
        if default:
            return self.resolve(default)
        online = [key for key, row in self.devices_cache.items() if row['online'] is True]
        if len(online) != 1:
            raise ValueError('请指定设备，或在插件设置中选择默认设备')
        return self.resolve(online[0])

    async def say(self, text: str, device: str = '', invocation=None):
        """主动让音箱说话，无需唤醒或切换主会话来源。默认选择活动音箱、配置的默认设备或唯一在线设备。
        等待独立播报实际完成；本轮音箱会话内的说话加入该轮播放队列。请勿再把同一内容作为自动语音回答重复输出。
        用户正在说话或其他会话正在占用时返回忙，不抢占收音或其他Agent的回答。停止使用audio_terminal_stop。

        Args:
            text: 要说的文字，1至1200字符。
            device: 可选设备ID；目标不明确时必须指定。
        """
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1200:
            raise ValueError('说话内容必须为1至1200字符')
        identity = self.speech_device(device)
        text = text.strip()
        turn = next((row['turn'] for row in self.voice_sessions.values()
                     if row['device'] == identity and row['turn']), None)
        if turn:
            run_id = getattr(invocation, 'run_id', '')
            current = self.runtime.current_run
            owned = bool(run_id and (turn.run_id == run_id or current and
                current['id'] == run_id and current.get('event_id') == turn.event_id))
            if not owned or getattr(turn, 'phase', '') in ('recording', 'recognizing'):
                raise ValueError('音箱正在收音或处理其他回答，请稍后再说')
            await self.voice_text(identity, {'text': text, 'run_id': run_id, 'response_id': uuid4().hex,
                'reply_context': {'session_id': turn.session_id, 'turn_id': turn.turn_id,
                                  'connection': turn.connection, 'device_id': identity}})
            return {'ok': True, 'status': 'queued', 'device_id': identity, 'turn_id': turn.turn_id}
        locks = getattr(self, 'say_locks', None)
        if locks is None:
            self.say_locks = locks = {}
        lock = locks.setdefault(identity, asyncio.Lock())
        if lock.locked():
            raise ValueError('音箱正在主动播报，请稍后再试')
        async with lock:
            plugin_epoch = getattr(self, 'epoch', 0)
            epochs = getattr(self, 'say_epochs', None)
            if epochs is None:
                self.say_epochs = epochs = {}
            epoch = epochs.get(identity, 0)
            for part in speech_parts(text):
                if any(row['device'] == identity and row['turn'] for row in self.voice_sessions.values()):
                    raise ValueError('用户已开始新的语音轮次，取消主动播报')
                if self.model_audio_enabled():
                    converter, chunks = None, []
                    async with contextlib.aclosing(self.runtime.speech.synthesize(
                            self.config.get('tts_model_id'), part,
                            voice=self.config.get('tts_voice', ''),
                            instruction=self.config.get('tts_instruction', ''))) as synthesis:
                        async for chunk in synthesis:
                            converter = converter or PCMResampler(chunk.sample_rate)
                            if converter.source_rate != chunk.sample_rate:
                                raise ValueError('TTS采样率发生变化')
                            chunks.append(converter.feed(chunk.pcm))
                    if converter is None:
                        raise ValueError('TTS没有返回音频')
                    chunks.append(converter.finish())
                    audio = wav_bytes(b''.join(chunks))
                else:
                    audio = await self.client.synthesize(part)
                if epochs.get(identity, 0) != epoch or self.stopping or getattr(self, 'epoch', 0) != plugin_epoch:
                    return {'ok': True, 'status': 'cancelled', 'device_id': identity}
                await self.proactive_playback(identity, audio)
            self.voice_last_output = text[:500]
            return {'ok': True, 'status': 'completed', 'device_id': identity}
