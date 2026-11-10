"""Model-owned ASR and low-latency TTS for opt-in PCM conversations."""
import asyncio
import base64
import contextlib
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from uuid import uuid4

from sakubot.speech_audio import PCMResampler, wav_bytes
from .client import device_id
from .conversation import Turn


@dataclass
class ModelTurn(Turn):
    phase: str = 'recording'
    pcm: bytearray = field(default_factory=bytearray)
    input_sequence: int = 0
    asr_task: object = None
    speech_task: object = None
    speech_queue: object = field(default_factory=lambda: asyncio.Queue(12))
    requests: dict = field(default_factory=dict)
    output_id: str = field(default_factory=lambda: uuid4().hex)
    output_sequence: int = 0
    audio_open: bool = False
    audio_bytes: int = 0
    enqueued_chars: int = 0


class AudioModels:
    def validate_speech_settings(self, value):
        if value.get('speech_backend') == 'models':
            for kind in ('asr', 'tts'):
                model = self.runtime.config.settings.selected_speech_model(value.get(kind + '_model_id'), kind)
                if model.capabilities.streaming_input or model.capabilities.realtime:
                    raise ValueError('当前音箱插件使用分段音频输入，请选择非实时 ASR/TTS 模型')
        return True

    def model_audio_enabled(self):
        return self.config.get('speech_backend', 'bridge') == 'models'

    def voice_transport_settings(self):
        return super().voice_transport_settings() + tuple(self.config.get(key) for key in
            ('speech_backend', 'asr_model_id', 'tts_model_id', 'auto_interrupt'))

    def voice_ready(self):
        if not super().voice_ready():
            return False
        if self.model_audio_enabled():
            if not getattr(self.runtime, 'speech', None):
                return False
            try:
                self.runtime.config.settings.selected_speech_model(self.config.get('asr_model_id'), 'asr')
                self.runtime.config.settings.selected_speech_model(self.config.get('tts_model_id'), 'tts')
            except ValueError:
                return False
        return True

    def speech_settings_fields(self):
        fields = json.loads((Path(__file__).parent / 'plugin.json').read_text())['settings']['fields']
        for item in fields:
            kind = {'asr_model_id': 'asr', 'tts_model_id': 'tts'}.get(item['key'])
            if kind:
                item['options'] = [{'value': '', 'label': '未选择'}] + [
                    {'value': model.id, 'label': (model.name or model.model_id) + ('' if model.enabled else ' · 已停用')}
                    for model in self.runtime.config.settings.models if getattr(model.capabilities, kind)]
        return fields

    def voice_declaration(self):
        value = super().voice_declaration()
        if self.model_audio_enabled():
            value.update(input='audio', requires_asr=False, input_stream=True,
                         barge_in=bool(self.config.get('auto_interrupt', True)))
        return value

    def voice_required_capabilities(self):
        result = super().voice_required_capabilities()
        return result | {'input.stream', 'response.audio.stream', 'session.interrupt'} if self.model_audio_enabled() else result

    def voice_state(self):
        result = super().voice_state()
        result.update(speech_backend=self.config.get('speech_backend', 'bridge'),
                      auto_interrupt=bool(self.config.get('auto_interrupt', True)))
        for row in result['sessions']:
            turn = self.voice_sessions[row['session_id']]['turn']
            row['phase'] = getattr(turn, 'phase', 'listening') if turn else 'listening'
        return result

    def clear_model_turn(self, session_id, *, cancel_agent=False):
        session = self.voice_sessions.get(session_id)
        turn = session['turn'] if session else None
        if not isinstance(turn, ModelTurn):
            return
        session['turn'] = None
        turn.closed.set()
        for job in (turn.asr_task, turn.speech_task):
            if job and job is not asyncio.current_task() and not job.done():
                job.cancel()
        if turn.event_id:
            self.runtime.cancel_wake(turn.event_id)
        if cancel_agent:
            self.background(self.cancel_voice_run(turn))

    async def cancel_voice_run(self, turn):
        run_id = turn.run_id
        if not run_id and turn.event_id:
            row = self.runtime.store.one('SELECT meta FROM events WHERE id=?', (turn.event_id,))
            if row:
                run_id = json.loads(row['meta']).get('wake_run_id', '')
        current = self.runtime.current_run
        if run_id and current and current['id'] == run_id:
            await self.runtime.stop_main_run(run_id)

    def drop_voice_session(self, session_id):
        self.clear_model_turn(session_id)
        return super().drop_voice_session(session_id)

    async def voice_packet(self, value):
        kind = value.get('type') if isinstance(value, dict) else None
        if kind == 'audio.ack':
            future = self.voice_acks.get(value.get('id'))
            if future and not future.done():
                future.set_result(value)
            return
        if kind == 'turn.interrupted':
            session = self.voice_sessions.get(value.get('session_id'))
            turn = session['turn'] if session else None
            if turn and turn.turn_id == value.get('turn_id'):
                self.clear_model_turn(value['session_id'], cancel_agent=True)
            return
        if kind not in ('input.start', 'input.audio', 'input.end'):
            return await super().voice_packet(value)
        if not self.model_audio_enabled():
            raise ValueError('音箱发送了未声明的PCM音频')
        session = self.voice_sessions.get(value.get('session_id'))
        if session is None:
            raise ValueError('音频会话已失效')
        if kind == 'input.start':
            if (value.get('format') != 'pcm16' or value.get('sample_rate') != 16000 or
                    value.get('channels') != 1 or value.get('device_id') != session['device'] or
                    not isinstance(value.get('turn_id'), str) or not 1 <= len(value['turn_id']) <= 80):
                raise ValueError('输入PCM参数或轮次无效')
            self.sync_voice_sources()
            if session['device'] not in self.voice_sources:
                raise ValueError('语音设备尚未发现')
            previous = session['turn']
            if previous and not previous.closed.is_set():
                raise ValueError('上一轮语音尚未中止')
            session['turn'] = ModelTurn(value['session_id'], value['turn_id'],
                                        device_id(session['device']), self.voice_connection)
            return
        turn = session['turn']
        if not isinstance(turn, ModelTurn) or turn.turn_id != value.get('turn_id') or turn.phase != 'recording':
            raise ValueError('输入音频轮次已过期')
        if kind == 'input.audio':
            if value.get('sequence') != turn.input_sequence or type(value.get('sequence')) is not int:
                raise ValueError('输入音频序号不连续')
            audio = value.get('audio')
            if not isinstance(audio, str) or len(audio) > 90000:
                raise ValueError('输入音频块过大')
            pcm = base64.b64decode(audio, validate=True)
            if not pcm or len(pcm) % 2 or len(turn.pcm) + len(pcm) > 16000 * 2 * 16:
                raise ValueError('输入音频长度无效')
            turn.pcm.extend(pcm)
            turn.input_sequence += 1
            return
        if value.get('integrity') != 'complete' or value.get('samples') != len(turn.pcm) // 2 or not turn.pcm:
            raise ValueError('输入音频不完整')
        turn.phase = 'recognizing'
        turn.asr_task = self.background(self.transcribe_turn(turn))

    async def transcribe_turn(self, turn):
        try:
            # MiMo supports full-audio input and SSE text output. Continuous PCM is
            # delivered before end, but never mislabeled as realtime MiMo inference.
            audio = wav_bytes(bytes(turn.pcm))
            turn.pcm.clear()
            text = []
            async with contextlib.aclosing(self.runtime.speech.transcribe(
                    self.config.get('asr_model_id'), audio)) as transcription:
                async for part in transcription:
                    text.append(part)
                    self.voice_last_input = ''.join(text)[:500]
            if turn.closed.is_set():
                return
            utterance = ''.join(text).strip()
            if not utterance:
                raise ValueError('ASR没有识别到文字')
            context = {'session_id': turn.session_id, 'turn_id': turn.turn_id,
                       'device_id': turn.device, 'connection': turn.connection,
                       'voice_context': self.voice_temporary_context(turn.device)}
            row = await self.receive_main(self.voice_sources[turn.device], utterance,
                actor='device:' + turn.device, label='音箱 · ' + turn.device,
                uid=turn.session_id + ':' + turn.turn_id,
                meta={'reply_context': context, 'source_label': '音箱',
                      'temporary_context': context['voice_context']})
            turn.event_id = row['id']
            turn.phase = 'thinking'
            self.voice_error = ''
            await self.voice_activity(turn, 'thinking')
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.fail_model_turn(turn, '模型语音识别失败，会话已结束')

    async def fail_model_turn(self, turn, message):
        session = self.voice_sessions.get(turn.session_id)
        if session and session['turn'] is turn and not turn.closed.is_set():
            self.voice_error = message
            await self.end_voice_session(turn.session_id)

    async def audio_request(self, turn, kind, **data):
        if turn.closed.is_set() or turn.connection != self.voice_connection:
            raise ValueError('原语音轮次已中止')
        identifier = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.voice_acks[identifier] = future
        try:
            await self.voice_send({'type': kind, 'id': identifier, 'session_id': turn.session_id,
                'turn_id': turn.turn_id, 'response_id': turn.output_id, **data})
            await asyncio.wait_for(future, 135 if kind.endswith('.end') else 10)
        finally:
            self.voice_acks.pop(identifier, None)
            if not future.done():
                future.cancel()

    async def send_pcm(self, turn, pcm):
        remaining = 16000 * 2 * 120 - turn.audio_bytes
        if len(pcm) > remaining:
            pcm = pcm[:remaining]
            turn.truncated = True
        if not pcm:
            return
        if not turn.audio_open:
            await self.audio_request(turn, 'response.audio.start', sample_rate=16000, channels=1, format='pcm16')
            turn.audio_open = True
        for start in range(0, len(pcm), 6400):
            chunk = pcm[start:start + 6400]
            await self.audio_request(turn, 'response.audio.chunk', sequence=turn.output_sequence,
                                     audio=base64.b64encode(chunk).decode('ascii'))
            turn.output_sequence += 1
            turn.audio_bytes += len(chunk)

    async def speech_worker(self, turn):
        try:
            while True:
                text = await turn.speech_queue.get()
                try:
                    if text is None:
                        if turn.audio_open:
                            await self.audio_request(turn, 'response.audio.end')
                        return
                    if turn.truncated or turn.closed.is_set():
                        continue
                    turn.phase = 'speaking'
                    converter = None
                    async with contextlib.aclosing(self.runtime.speech.synthesize(
                            self.config.get('tts_model_id'), text,
                            voice=self.config.get('tts_voice', ''),
                            instruction=self.config.get('tts_instruction', ''))) as synthesis:
                        async for part in synthesis:
                            if converter is None:
                                converter = PCMResampler(part.sample_rate)
                            elif converter.source_rate != part.sample_rate:
                                raise ValueError('TTS流采样率发生变化')
                            await self.send_pcm(turn, converter.feed(part.pcm))
                            if turn.truncated:
                                break
                    if converter and not turn.truncated:
                        await self.send_pcm(turn, converter.finish())
                finally:
                    turn.speech_queue.task_done()
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.fail_model_turn(turn, '模型语音合成或播放失败，会话已结束')

    async def flush_request(self, turn, request_id, *, final=False):
        record = turn.requests.setdefault(request_id, {'text': '', 'offset': 0})
        tail = record['text'][record['offset']:]
        while tail and not turn.truncated:
            end = re.search(r'[。！？!?；;\n]|\.(?=\s)', tail)
            if end:
                cut = end.end()
            elif len(tail) >= 180:
                cut = 180
            elif final:
                cut = len(tail)
            else:
                break
            text, tail = tail[:cut].strip(), tail[cut:]
            record['offset'] += cut
            if text:
                if turn.speech_task is None:
                    turn.speech_task = self.background(self.speech_worker(turn))
                await self.voice_work(turn, turn.speech_queue.put(text))

    async def voice_stream(self, identity, packet):
        if not self.model_audio_enabled():
            return
        try:
            turn = self.voice_turn(identity, packet)
        except ValueError:
            return
        if not isinstance(turn, ModelTurn):
            return
        if packet.get('event') == 'model.failed':
            await self.fail_model_turn(turn, '主 Agent 模型响应失败，会话已结束')
            return
        turn.run_id = packet.get('run_id') or turn.run_id
        request_id = packet.get('request_id') or packet.get('response_id')
        if not isinstance(request_id, str):
            return
        record = turn.requests.setdefault(request_id, {'text': '', 'offset': 0})
        if packet.get('event') == 'model.delta':
            text = packet.get('text')
            if not isinstance(text, str):
                return
            turn.enqueued_chars += len(text)
            if turn.enqueued_chars > 32000:
                await self.fail_model_turn(turn, '语音回答超出长度限制')
                return
            record['text'] += text
            await self.flush_request(turn, request_id)
        elif packet.get('event') == 'model.completed':
            await self.flush_request(turn, request_id, final=True)

    async def voice_text(self, identity, packet):
        if not self.model_audio_enabled():
            return await super().voice_text(identity, packet)
        turn = self.voice_turn(identity, packet)
        text = str(packet.get('text', ''))
        if not isinstance(turn, ModelTurn):
            # Proactive output has no active microphone turn. It still uses the
            # selected model, sentence by sentence; ordinary playback remains bounded.
            from .conversation import speech_parts
            parts = speech_parts(text)
            if len(parts) > 30:
                raise ValueError('主动播报过长，请缩短内容')
            connection = self.voice_connection
            for part in parts:
                data, converter = [], None
                async with contextlib.aclosing(self.runtime.speech.synthesize(
                        self.config.get('tts_model_id'), part, voice=self.config.get('tts_voice', ''),
                        instruction=self.config.get('tts_instruction', ''))) as synthesis:
                    async for chunk in synthesis:
                        converter = converter or PCMResampler(chunk.sample_rate)
                        data.append(converter.feed(chunk.pcm))
                if converter:
                    data.append(converter.finish())
                    if connection != self.voice_connection or not self.voice_available(identity)['available']:
                        raise ValueError('原语音连接已失效，已取消迟到播报')
                    await self.proactive_playback(identity, wav_bytes(b''.join(data)))
            self.voice_last_output = text[:500]
            return
        turn.run_id = packet.get('run_id') or turn.run_id
        request_id = packet.get('response_id') or uuid4().hex
        record = turn.requests.setdefault(request_id, {'text': '', 'offset': 0})
        if text.startswith(record['text']):
            record['text'] = text
        elif record['text'] != text:
            # A durable explicit message can differ from streamed model content.
            request_id = request_id + ':message'
            turn.requests[request_id] = {'text': text, 'offset': 0}
        await self.flush_request(turn, request_id, final=True)
        self.voice_last_output = text[:500]

    async def finish_voice_turn(self, turn):
        if not isinstance(turn, ModelTurn):
            return await super().finish_voice_turn(turn)
        if turn.finishing or turn.closed.is_set():
            return
        turn.finishing = True
        async def finish():
            for identifier in list(turn.requests):
                await self.flush_request(turn, identifier, final=True)
            if turn.speech_task:
                await turn.speech_queue.put(None)
                await turn.speech_task
            await self.voice_response(turn, final=True)
        try:
            await self.voice_work(turn, finish())
            session = self.voice_sessions.get(turn.session_id)
            if session and session['turn'] is turn:
                session['turn'] = None
            turn.closed.set()
        except asyncio.CancelledError:
            if not turn.closed.is_set():
                raise
        except Exception:
            await self.fail_model_turn(turn, '语音回答收尾失败，会话已结束')

    async def voice_lifecycle(self, identity, packet):
        try:
            self.voice_turn(identity, packet)
        except ValueError:
            return
        return await super().voice_lifecycle(identity, packet)

    async def api_interrupt_conversation(self, request):
        identities = set()
        for session_id, session in list(self.voice_sessions.items()):
            identities.add(session['device'])
            self.clear_model_turn(session_id, cancel_agent=True)
        status = await self.client.request('GET', '/v1/interactions')
        identities.update(row['device_id'] for row in status.get('sessions', []))
        for identity in identities:
            await self.client.request('POST', self.client.path(identity, '/session/interrupt'), json={})
        return {'ok': True}
