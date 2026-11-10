"""Speech-model adapters; streamed responses never imply realtime input."""
import asyncio
import base64
import binascii
from dataclasses import dataclass
import json

import httpx

from .speech_audio import read_wav


MAX_AUDIO_BYTES = 48000 * 2 * 120
MAX_SSE_EVENT = 2 * 1024 * 1024
MAX_TEXT = 16000


class SpeechError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioChunk:
    pcm: bytes
    sample_rate: int


async def events(response):
    """Read bounded SSE events, including multiline data and arbitrary TCP splits."""
    buffer = bytearray()
    data = []
    size = 0
    async for chunk in response.aiter_bytes():
        buffer.extend(chunk)
        while b'\n' in buffer:
            line, _, rest = buffer.partition(b'\n')
            buffer = bytearray(rest)
            if len(line) > MAX_SSE_EVENT:
                raise SpeechError('语音流事件过大')
            line = line.rstrip(b'\r')
            if not line:
                if data:
                    raw = b'\n'.join(data)
                    if raw.strip() == b'[DONE]':
                        return
                    try:
                        value = json.loads(raw)
                    except (ValueError, UnicodeError) as exc:
                        raise SpeechError('语音流格式无效') from exc
                    if not isinstance(value, dict) or 'error' in value:
                        raise SpeechError('语音模型返回错误')
                    yield value
                data, size = [], 0
            elif line.startswith(b'data:'):
                item = bytes(line[5:]).lstrip(b' ')
                size += len(item)
                if size > MAX_SSE_EVENT:
                    raise SpeechError('语音流事件过大')
                data.append(item)
        if len(buffer) > MAX_SSE_EVENT:
            raise SpeechError('语音流事件过大')
    if buffer or data:
        raise SpeechError('语音流意外中断')


class Speech:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(90, connect=15, read=45), trust_env=False, follow_redirects=False)
        self.owns_client = client is None

    async def close(self):
        if self.owns_client:
            await self.client.aclose()

    def selected(self, identifier, capability):
        settings = self.settings() if callable(self.settings) else self.settings
        return settings.selected_speech_model(identifier, capability)

    @staticmethod
    def headers(provider):
        return {'Authorization': 'Bearer ' + provider.api_key} if provider.api_key else {}

    @staticmethod
    def check(response):
        # Provider errors may include request audio, prompts or credentials. Do not echo.
        if response.status_code != 200:
            raise SpeechError('语音模型请求失败（HTTP ' + str(response.status_code) + '）')

    async def json(self, provider, path, **kwargs):
        try:
            async with asyncio.timeout(100):
                async with self.client.stream('POST', provider.api_base + path,
                        headers=self.headers(provider), **kwargs) as response:
                    self.check(response)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 18 * 1024 * 1024:
                            raise SpeechError('语音模型响应过大')
                    return json.loads(body)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            raise SpeechError('语音模型连接中断或超时') from exc
        except (ValueError, UnicodeError) as exc:
            raise SpeechError('语音模型响应格式无效') from exc

    async def transcribe(self, identifier, wav, *, language='auto'):
        provider, model = self.selected(identifier, 'asr')
        read_wav(wav)
        if len(wav) > 7500000 or language not in ('auto', 'zh', 'en'):
            raise ValueError('ASR音频或语种参数无效')
        if model.speech_api != 'mimo':
            body = await self.json(provider, '/audio/transcriptions',
                files={'file': ('utterance.wav', wav, 'audio/wav')},
                data={'model': model.model_id, **({} if language == 'auto' else {'language': language})})
            text = body.get('text')
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                raise SpeechError('ASR返回的文字无效')
            yield text
            return
        payload = {**model.extra_body, 'model': model.model_id,
            'messages': [{'role': 'user', 'content': [{'type': 'input_audio', 'input_audio': {
                'data': 'data:audio/wav;base64,' + base64.b64encode(wav).decode('ascii')}}]}],
            'asr_options': {'language': language}, 'stream': model.capabilities.streaming_output}
        if not payload['stream']:
            body = await self.json(provider, '/chat/completions', json=payload)
            try:
                text = body['choices'][0]['message']['content']
                if not isinstance(text, str) or len(text) > MAX_TEXT:
                    raise ValueError()
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise SpeechError('ASR返回的文字无效') from exc
            yield text
            return
        total = 0
        finished = False
        try:
            async with asyncio.timeout(100):
                async with self.client.stream('POST', provider.api_base + '/chat/completions',
                        headers=self.headers(provider), json=payload) as response:
                    self.check(response)
                    async for packet in events(response):
                        for choice in packet.get('choices', []):
                            text = choice.get('delta', {}).get('content') or ''
                            if not isinstance(text, str):
                                raise SpeechError('ASR流文字无效')
                            total += len(text)
                            if total > MAX_TEXT:
                                raise SpeechError('ASR文字超出限制')
                            if text:
                                yield text
                            if choice.get('finish_reason') is not None:
                                if choice['finish_reason'] != 'stop':
                                    raise SpeechError('ASR输出未完整结束')
                                finished = True
            if not finished:
                raise SpeechError('ASR流没有正常结束')
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            raise SpeechError('ASR连接中断或超时') from exc

    async def synthesize(self, identifier, text, *, voice='', instruction=''):
        provider, model = self.selected(identifier, 'tts')
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 8000:
            raise ValueError('TTS文本长度无效')
        if not isinstance(voice, str) or len(voice) > 200 or len(instruction) > 2000:
            raise ValueError('TTS音色或风格参数无效')
        if model.speech_api != 'mimo':
            payload = {**model.extra_body, 'model': model.model_id, 'input': text,
                       'voice': voice or 'alloy', 'response_format': 'pcm'}
            try:
                async with asyncio.timeout(100):
                    async with self.client.stream('POST', provider.api_base + '/audio/speech',
                            headers=self.headers(provider), json=payload) as response:
                        self.check(response)
                        total = 0
                        async for chunk in response.aiter_bytes(8192):
                            total += len(chunk)
                            if total > MAX_AUDIO_BYTES:
                                raise SpeechError('TTS音频超出限制')
                            if chunk:
                                yield AudioChunk(chunk, model.speech_sample_rate)
                        if not total or total % 2:
                            raise SpeechError('TTS PCM音频不完整')
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                raise SpeechError('TTS连接中断或超时') from exc
            return
        streaming = model.capabilities.streaming_output
        options = dict(model.extra_body.get('audio', {}))
        options.update(format='pcm16' if streaming else 'wav')
        if voice:
            options['voice'] = voice
        elif model.model_id == 'mimo-v2.5-tts':
            options.setdefault('voice', 'mimo_default')
        messages = ([{'role': 'user', 'content': instruction}] if instruction else [])
        messages.append({'role': 'assistant', 'content': text})
        payload = {**model.extra_body, 'model': model.model_id, 'messages': messages,
                   'audio': options, 'stream': streaming}
        if not streaming:
            body = await self.json(provider, '/chat/completions', json=payload)
            try:
                raw = base64.b64decode(body['choices'][0]['message']['audio']['data'], validate=True)
                pcm, rate = read_wav(raw)
            except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as exc:
                raise SpeechError('TTS音频响应无效') from exc
            yield AudioChunk(pcm, rate)
            return
        total = 0
        finished = False
        try:
            async with asyncio.timeout(100):
                async with self.client.stream('POST', provider.api_base + '/chat/completions',
                        headers=self.headers(provider), json=payload) as response:
                    self.check(response)
                    async for packet in events(response):
                        for choice in packet.get('choices', []):
                            audio = choice.get('delta', {}).get('audio')
                            if audio and audio.get('data'):
                                try:
                                    raw = base64.b64decode(audio['data'], validate=True)
                                except (ValueError, TypeError, binascii.Error) as exc:
                                    raise SpeechError('TTS流音频无效') from exc
                                total += len(raw)
                                if total > MAX_AUDIO_BYTES:
                                    raise SpeechError('TTS音频超出限制')
                                if raw:
                                    yield AudioChunk(raw, model.speech_sample_rate)
                            if choice.get('finish_reason') is not None:
                                if choice['finish_reason'] != 'stop':
                                    raise SpeechError('TTS输出未完整结束')
                                finished = True
            if not finished or not total or total % 2:
                raise SpeechError('TTS流没有完整结束')
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            raise SpeechError('TTS连接中断或超时') from exc
