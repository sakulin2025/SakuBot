"""Bridge-owned speech turns connected to Sakubot's existing main conversation."""
import asyncio
import base64
from dataclasses import dataclass, field
from functools import partial
import hashlib
import json
import re
import time
from uuid import uuid4

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .client import device_id, validate_wav

REQUIRED = {'device_mode', 'turn.processing', 'response.completed', 'response.empty_final'}
DEFAULT_TEMPORARY_CONTEXT = """你正在通过音箱与用户对话，回答会自动合成语音播放。
请简短、直接、口语化地回答，通常控制在1到3句话；除非用户明确要求详细说明，不要长篇解释或输出大段列表。
用户明确要求结束本次对话，或说“再见”“不用聊了”等告别语时，必须调用 audio_terminal_end_conversation，无需填写任何参数。不能只口头答应，也不要让用户等待会话自动超时。
仅要求停止播放不等于结束对话；用户仍希望继续交流时不要擅自结束会话。"""


def speech_parts(text, limit=180):
    """Keep TTS chunks below its text limit while preferring sentence boundaries."""
    result = []
    for sentence in re.findall(r'[^。！？!?；;\n]+[。！？!?；;]?', text):
        sentence = sentence.strip()
        while sentence:
            cut = min(len(sentence), limit)
            if len(sentence) > limit:
                boundary = max(sentence.rfind(mark, 0, limit) for mark in ('，', ',', ' ', '：'))
                if boundary >= limit // 3:
                    cut = boundary + 1
            value, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if value:
                result.append(value)
    return result


@dataclass
class Turn:
    session_id: str
    turn_id: str
    device: str
    connection: str
    event_id: int = 0
    run_id: str = ''
    responses: int = 0
    busy: bool = False
    finishing: bool = False
    truncated: bool = False
    closed: asyncio.Event = field(default_factory=asyncio.Event)


class VoiceConversation:
    def setup_voice(self):
        self._voice_transport_settings = self.voice_transport_settings()
        self.voice_ws = None
        self.voice_connection = ''
        self.voice_bound = False
        self.voice_error = ''
        self.voice_sessions = {}
        self.voice_sources = {}
        self.voice_acks = {}
        self.voice_send_lock = asyncio.Lock()
        self.voice_last_input = self.voice_last_output = ''

    def voice_transport_settings(self):
        return tuple(self.config.get(key) for key in
                     ('base_url', 'token', 'subscribe_events', 'conversation_enabled'))

    def voice_temporary_context(self, identity):
        value = self.config.get('temporary_context', DEFAULT_TEMPORARY_CONTEXT)
        if not isinstance(value, str) or len(value) > 8000:
            raise ValueError('音箱临时上下文必须是最多8000字符的文本')
        return '当前音箱设备 ID：' + device_id(identity) + '。\n' + value.strip()

    def reply_context_prompt(self, context):
        current = self.runtime.store.kv_get('conversation.current', '')
        identity = next((identity for identity, identifier in self.voice_sources.items()
                         if current == self.id + '.' + identifier), None)
        if identity is None:
            return ''
        # Snapshot user instructions for a microphone turn. Editing settings only affects
        # subsequent turns; the framework reinjects this reminder before every model step.
        prompt = context.get('voice_context') if isinstance(context, dict) else None
        if not isinstance(prompt, str):
            prompt = self.voice_temporary_context(identity)
        session = self.voice_sessions.get(context.get('session_id')) if isinstance(context, dict) else None
        state = ('当前音箱会话已结束，不要重复调用结束会话工具。'
                 if isinstance(context, dict) and context.get('session_id') and session is None
                 else '当前音箱会话标识：' + str(context['session_id'])
                 if isinstance(context, dict) and context.get('session_id')
                 else '当前输出源为该音箱，没有关联的语音轮次。')
        return prompt + '\n' + state

    @staticmethod
    def voice_identifier(identity):
        return 'device_' + hashlib.sha256(identity.encode()).hexdigest()[:16]

    def voice_ready(self):
        return self.config.get('conversation_enabled', True) and self.runtime.config.settings.ready()

    def voice_available(self, identity):
        online = self.connected and self.devices_cache.get(identity, {}).get('online') is True
        return {'available': bool(self.voice_ready() and self.voice_bound and online),
                'reason': '' if self.voice_ready() and self.voice_bound and online
                else self.voice_error or '音箱离线、对话提供者未连接或主 Agent 未启用'}

    def sync_voice_sources(self):
        for identity, row in self.devices_cache.items():
            if row['online'] is not True or identity in self.voice_sources:
                continue
            identifier = self.voice_identifier(identity)
            self.conversation_source(identifier, '音箱 · ' + identity,
                handlers={'text': partial(self.voice_text, identity),
                          'stream': partial(self.voice_stream, identity),
                          'lifecycle': partial(self.voice_lifecycle, identity)},
                availability=partial(self.voice_available, identity), timeout=None)
            self.voice_sources[identity] = identifier
        for identity in set(self.voice_sources) - set(self.devices_cache):
            self.remove_conversation_source(self.voice_sources.pop(identity))

    def voice_state(self):
        return {'enabled': bool(self.config.get('conversation_enabled', True)), 'bound': self.voice_bound,
                'error': self.voice_error, 'sources': {identity: self.id + '.' + source
                    for identity, source in self.voice_sources.items()},
                'sessions': [{'session_id': key, 'device_id': value['device'],
                    'waiting': value['turn'] is not None} for key, value in self.voice_sessions.items()],
                'last_input': self.voice_last_input, 'last_output': self.voice_last_output}

    async def voice_send(self, value):
        async with self.voice_send_lock:
            if self.voice_ws is None:
                raise ValueError('音箱对话连接已断开')
            await asyncio.wait_for(self.voice_ws.send(json.dumps(value, ensure_ascii=False)), 5)

    async def voice_activity(self, turn, state):
        if not self.config.get('activity_cues', False) or getattr(turn, 'audio_open', False):
            return
        # Activity cues are best-effort; a reconnect must not fail the voice turn.
        try:
            await self.voice_send({'type': 'turn.state', 'session_id': turn.session_id,
                                   'turn_id': turn.turn_id, 'state': state})
        except (ValueError, OSError, WebSocketException, asyncio.TimeoutError):
            pass

    def drop_voice_session(self, identity):
        session = self.voice_sessions.pop(identity, None)
        if not session or session['turn'] is None:
            return
        turn = session['turn']
        turn.closed.set()
        if turn.event_id:
            self.runtime.cancel_wake(turn.event_id)

    async def stop_voice(self):
        self.voice_bound = False
        ws = self.voice_ws
        if ws is not None:
            await ws.close()
        self.voice_ws = None
        for key in list(self.voice_sessions):
            self.drop_voice_session(key)
        for future in list(self.voice_acks.values()):
            if not future.done():
                future.set_exception(ValueError('音箱对话连接已断开，播放结果可能未知'))

    async def voice_loop(self):
        delay = 1
        while not self.stopping:
            if not self.voice_ready() or not self.availability()['available']:
                self.voice_error = '主 Agent 未启用、模型未配置或对话功能已关闭'
                await asyncio.sleep(3)
                continue
            try:
                async with connect(self.client.agent_url(), additional_headers=self.client.headers(),
                        proxy=None, open_timeout=8, close_timeout=2, max_size=6 * 1024 * 1024,
                        max_queue=32, ping_interval=15, ping_timeout=15) as ws:
                    self.voice_ws = ws
                    await self.voice_send(self.voice_declaration())
                    reply = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    if not isinstance(reply, dict):
                        raise ValueError('对话服务声明响应格式错误')
                    if reply.get('type') != 'declared':
                        raise ValueError('已有其他对话提供者绑定，等待释放' if
                            reply.get('error') == 'provider_already_bound' else '对话能力声明被拒绝')
                    if not self.voice_required_capabilities() <= set(reply.get('capabilities', [])):
                        raise ValueError('请先更新音频服务的对话保活和播放回执接口')
                    self.voice_connection = uuid4().hex
                    self.voice_bound, self.voice_error, delay = True, '', 1
                    async for raw in ws:
                        if isinstance(raw, str):
                            await self.voice_packet(json.loads(raw))
            except (ValueError, OSError, WebSocketException, asyncio.TimeoutError) as exc:
                self.voice_error = str(exc)[:180] if isinstance(exc, ValueError) else '对话连接断开，正在重连'
            finally:
                await self.stop_voice()
            if not self.stopping:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15)

    def voice_declaration(self):
        return {'type': 'declare', 'source_id': 'sakubot-audio-terminal',
                'conversation': True, 'input': 'text', 'requires_asr': True, 'device_mode': 'single'}

    def voice_required_capabilities(self):
        return REQUIRED

    async def voice_stream(self, identity, packet):
        pass

    async def voice_packet(self, value):
        if not isinstance(value, dict):
            raise ValueError('对话服务消息格式错误')
        kind = value.get('type')
        if kind in ('response.completed', 'error') and value.get('id') in self.voice_acks:
            future = self.voice_acks[value['id']]
            if not future.done():
                if kind == 'error':
                    future.set_exception(ValueError('音箱拒绝回答：' + str(value.get('error', ''))[:100]))
                else:
                    future.set_result(value)
            return
        if kind == 'error':
            self.voice_error = '对话服务错误：' + str(value.get('error', ''))[:100]
        elif kind == 'session.started':
            identity = device_id(value.get('device_id'))
            session_id = value.get('session_id')
            if not isinstance(session_id, str) or not 1 <= len(session_id) <= 80:
                raise ValueError('对话会话标识错误')
            for key, session in list(self.voice_sessions.items()):
                if session['device'] == identity:
                    self.drop_voice_session(key)
            if len(self.voice_sessions) >= 8:
                raise ValueError('对话会话数量超过上限')
            self.voice_sessions[session_id] = {'device': identity, 'turn': None}
        elif kind == 'session.ended':
            self.drop_voice_session(value.get('session_id'))
        elif kind == 'input':
            session = self.voice_sessions.get(value.get('session_id'))
            text, turn_id = value.get('text'), value.get('turn_id')
            if (session is None or session['device'] != value.get('device_id') or
                    not isinstance(text, str) or not 1 <= len(text.strip()) <= 16000 or
                    not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 80):
                raise ValueError('语音输入标识或内容错误')
            previous = session['turn']
            if previous and previous.turn_id == turn_id:
                return
            if previous and not previous.closed.is_set():
                raise ValueError('上一轮语音尚未结束')
            self.sync_voice_sources()
            identity = session['device']
            if identity not in self.voice_sources:
                raise ValueError('语音设备尚未发现')
            turn = Turn(value['session_id'], turn_id, identity, self.voice_connection)
            session['turn'] = turn
            context = {'session_id': turn.session_id, 'turn_id': turn.turn_id,
                       'device_id': identity, 'connection': turn.connection,
                       'voice_context': self.voice_temporary_context(identity)}
            row = await self.receive_main(self.voice_sources[identity], text.strip(), actor='device:' + identity,
                label='音箱 · ' + identity, uid=turn.session_id + ':' + turn.turn_id,
                meta={'reply_context': context, 'source_label': '音箱',
                    'temporary_context': context['voice_context']})
            turn.event_id = row['id']
            await self.voice_activity(turn, 'thinking')
            self.voice_last_input = text.strip()[:500]
            self.voice_error = ''
        # Double-knock event notifications deliberately do not create main conversation inputs.

    def voice_turn(self, identity, packet):
        context = packet.get('reply_context') or {}
        if not isinstance(context, dict):
            raise ValueError('语音回答上下文无效')
        if context:
            session = self.voice_sessions.get(context.get('session_id'))
            turn = session['turn'] if session else None
            if (turn is None or turn.closed.is_set() or turn.device != identity or
                    turn.turn_id != context.get('turn_id') or turn.connection != context.get('connection')):
                raise ValueError('语音会话已结束，已丢弃迟到回答')
            return turn
        if packet.get('run_id'):
            row = self.runtime.store.one('SELECT events.meta FROM runs JOIN events ON events.id=runs.event_id WHERE runs.id=?',
                                         (packet['run_id'],))
            if row and str(json.loads(row['meta']).get('conversation_source', '')).startswith(self.id + '.'):
                raise ValueError('原语音回答位置已失效，不转为无关联播报')
        return None

    async def voice_parts(self, text):
        state = await self.client.request('GET', '/v1/tts/status')
        limit = state.get('max_chars', 600)
        if type(limit) is not int or not 20 <= limit <= 2000:
            raise ValueError('TTS 文本限制无效')
        return speech_parts(text, min(limit, 180))

    async def proactive_playback(self, identity, audio):
        if any(s['device'] == identity and s['turn'] for s in self.voice_sessions.values()):
            raise ValueError('音箱开始了新的语音轮次，已取消无关联播报')
        # Subscribe before playback acceptance, including when ordinary event monitoring is off.
        async with connect(self.client.events_url(identity), additional_headers=self.client.headers(),
                proxy=None, open_timeout=8, close_timeout=2, max_size=16384,
                max_queue=32, ping_interval=20, ping_timeout=20) as ws:
            if any(s['device'] == identity and s['turn'] for s in self.voice_sessions.values()):
                raise ValueError('音箱开始了新的语音轮次，已取消无关联播报')
            result = await self.play_data(identity, audio)
            deadline = asyncio.get_running_loop().time() + validate_wav(audio) + 5
            while True:
                raw = await asyncio.wait_for(ws.recv(), max(.01, deadline - asyncio.get_running_loop().time()))
                value = json.loads(raw)
                if (value.get('data') or {}).get('playback_id') != result['playback_id']:
                    continue
                if value.get('event') == 'playback.completed':
                    return
                if value.get('event') in ('playback.stopped', 'bridge.playback_failed'):
                    raise ValueError('音箱播报被中断，未重试')

    async def voice_work(self, turn, coroutine):
        job = asyncio.create_task(coroutine)
        closed = asyncio.create_task(turn.closed.wait())
        try:
            done, _ = await asyncio.wait((job, closed), return_when=asyncio.FIRST_COMPLETED)
            if closed in done or turn.closed.is_set():
                raise ValueError('语音会话已结束，已取消未完成的回答')
            return await job
        finally:
            for task in (job, closed):
                if not task.done():
                    task.cancel()
            await asyncio.gather(job, closed, return_exceptions=True)

    async def voice_response(self, turn, *, audio=None, text=None, final=False):
        if turn.closed.is_set() or turn.connection != self.voice_connection:
            raise ValueError('语音轮次已过期')
        request_id = uuid4().hex
        packet = {'type': 'response', 'response_id': request_id,
                  'session_id': turn.session_id, 'turn_id': turn.turn_id, 'final': final}
        timeout = 10
        if audio is not None:
            timeout += validate_wav(audio)
            packet['audio'] = base64.b64encode(audio).decode()
        if text:
            packet['text'] = text
        future = asyncio.get_running_loop().create_future()
        self.voice_acks[request_id] = future
        try:
            await self.voice_send(packet)
            await asyncio.wait_for(future, timeout)
            turn.responses += 1
        finally:
            self.voice_acks.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def voice_text(self, identity, packet):
        text = packet.get('text', '').strip()
        if not text:
            return
        turn = self.voice_turn(identity, packet)
        if turn is None:
            # Explicitly selected main sources can also receive proactive replies. Never use
            # unrelated output to answer a currently pending microphone turn.
            if any(s['device'] == identity and s['turn'] for s in self.voice_sessions.values()):
                raise ValueError('该设备有待回应的语音轮次，拒绝无关联播报')
            parts = await self.voice_parts(text)
            connection = self.voice_connection
            if len(parts) > 30:
                raise ValueError('主动播报过长，请缩短内容')
            for part in parts:
                if not self.voice_available(identity)['available']:
                    raise ValueError('音箱当前不可用')
                audio = await self.client.synthesize(part)
                if connection != self.voice_connection or not self.voice_available(identity)['available']:
                    raise ValueError('原对话连接已失效，已取消迟到播报')
                await self.proactive_playback(identity, audio)
            self.voice_last_output = text[:500]
            return
        turn.run_id = packet.get('run_id', '')
        turn.busy = True
        async def speak():
            for part in await self.voice_parts(text):
                if turn.truncated:
                    break
                if turn.responses >= 29:
                    part = '回答较长，完整内容请查看主会话。'
                    turn.truncated = True
                audio = await self.client.synthesize(part)
                await self.voice_response(turn, audio=audio, text=part)
        try:
            await self.voice_work(turn, speak())
            self.voice_last_output = text[:500]
        except Exception as exc:
            self.voice_error = str(exc)[:180] if isinstance(exc, ValueError) else '语音回答失败，会话已结束'
            session = self.voice_sessions.get(turn.session_id)
            if not turn.closed.is_set() and session and session['turn'] is turn:
                await self.end_voice_session(turn.session_id)
            raise
        finally:
            turn.busy = False

    async def voice_lifecycle(self, identity, packet):
        event = packet.get('event')
        if event in ('agent.tool_started', 'agent.tool_completed'):
            try:
                turn = self.voice_turn(identity, packet)
            except ValueError:
                return
            if turn is not None:
                await self.voice_activity(turn, 'tool' if event == 'agent.tool_started' else 'thinking')
            return
        if event not in ('run.completed', 'run.failed'):
            return
        turn = self.voice_turn(identity, packet)
        if turn is None:
            return
        if packet['event'] == 'run.failed':
            self.voice_error = '主 Agent 处理失败，会话已结束'
            await self.end_voice_session(turn.session_id)
        else:
            await self.finish_voice_turn(turn)

    async def finish_voice_turn(self, turn):
        if turn.finishing or turn.closed.is_set():
            return
        turn.finishing = True
        try:
            await self.voice_work(turn, self.voice_response(turn, final=True))
            session = self.voice_sessions.get(turn.session_id)
            if session and session['turn'] is turn:
                session['turn'] = None
            turn.closed.set()
        except Exception:
            session = self.voice_sessions.get(turn.session_id)
            if not turn.closed.is_set() and session and session['turn'] is turn:
                await self.end_voice_session(turn.session_id)
            raise

    async def end_voice_session(self, session_id):
        if session_id not in self.voice_sessions:
            return
        self.drop_voice_session(session_id)
        if self.voice_bound:
            await self.voice_send({'type': 'session.end', 'session_id': session_id})

    async def voice_watchdog(self):
        while not self.stopping:
            await asyncio.sleep(5)
            if self.voice_bound and not self.voice_ready():
                await self.stop_voice()
                continue
            for session in list(self.voice_sessions.values()):
                turn = session['turn']
                if turn is None or turn.closed.is_set() or getattr(turn, 'phase', '') == 'recording':
                    continue
                try:
                    await self.voice_send({'type': 'turn.processing', 'session_id': turn.session_id,
                                           'turn_id': turn.turn_id})
                    row = self.runtime.store.one('SELECT status,meta FROM events WHERE id=?', (turn.event_id,))
                    if not row:
                        continue
                    turn.run_id = json.loads(row['meta']).get('wake_run_id') or turn.run_id
                    if row['status'] in ('failed', 'interrupted', 'cancelled'):
                        await self.end_voice_session(turn.session_id)
                    elif row['status'] == 'done' and not turn.busy:
                        key = self.id + '.' + self.voice_sources[turn.device]
                        source = self.runtime.conversation.sources.get(key)
                        if self.runtime.store.kv_get('conversation.current', '') != key:
                            await self.end_voice_session(turn.session_id)
                        elif source and source['queue'].empty():
                            await self.finish_voice_turn(turn)
                except (ValueError, OSError, WebSocketException, asyncio.TimeoutError):
                    self.voice_error = '语音轮次已结束或连接中断'
                    await self.stop_voice()
                    break
