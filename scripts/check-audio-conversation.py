"""Isolated speech bridge/main-conversation integration; no model or physical device."""
import asyncio
import base64
from collections import deque
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from sakubot.config import Config
from sakubot.runtime import Runtime
from sakubot.store import Store
from server.app import create_app, HUB
from server.interactions import INTERACTIONS, wav
from server.training import TrainingStore
from server.tts_proxy import TTS

spec = importlib.util.spec_from_file_location('voice_plugin_check', '/plugin/__init__.py',
                                            submodule_search_locations=['/plugin'])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


async def until(condition, timeout=3):
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(.01)


class Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        with patch.dict(os.environ, {'SAKUBOT_DATA': str(root / 'saku')}):
            config = Config()
        self.runtime = Runtime(config, Store(config.root))
        self.app = create_app('device-secret', 'api-secret', TrainingStore(root / 'training'))
        self.manager = self.app[INTERACTIONS]
        self.manager.cue = AsyncMock(return_value=True)
        self.manager.ready = AsyncMock(return_value=True)
        self.audio = wav(bytes(1600))
        self.tts_started = asyncio.Event()
        self.tts_gate = asyncio.Event()
        self.tts_gate.set()
        self.tts_texts = []
        async def call(method, action, data=None):
            if action == 'status':
                return web.json_response({'max_chars': 600, 'request_timeout_seconds': 735})
            if action == 'synthesize':
                self.tts_started.set()
                await self.tts_gate.wait()
                self.tts_texts.append(json.loads(data)['text'])
                return web.Response(body=self.audio, content_type='audio/wav')
            raise ValueError(action)
        self.app[TTS].call = call
        manager = self.manager
        class Device:
            id = 'board-test'
            def __init__(self):
                self.events = []
                self.played = []
                self.command = AsyncMock(return_value={'ok': True})
                self.play_lock = asyncio.Lock()
                self.playback = None
                self.active_playback_stream = None
                self.received = []
                self.pcm_started = asyncio.Event()
                self.complete_gate = asyncio.Event()
                self.complete_gate.set()
            async def cancel_playback(self):
                task, self.playback = self.playback, None
                if task:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            async def play_pcm(self, chunks):
                stream = self.active_playback_stream = len(self.played) + 100
                self.played.append('stream')
                async def consume():
                    async for chunk in chunks:
                        self.received.append(chunk)
                        self.pcm_started.set()
                    await self.complete_gate.wait()
                    manager.event(self, {'event':'playback.completed','data':{'playback_id':stream}})
                self.playback = asyncio.create_task(consume())
                return {'ok':True,'playback_id':stream}
            def event(self, event, **data):
                self.events.append((event, data))
            async def play_wav(self, pcm):
                self.played.append(pcm)
                stream = len(self.played)
                asyncio.get_running_loop().call_later(.03, manager.event, self,
                    {'event': 'playback.completed', 'data': {'playback_id': stream}})
                return {'ok': True, 'playback_id': stream}
        self.device = Device()
        self.app[HUB].devices[self.device.id] = self.device
        self.http = TestClient(TestServer(self.app))
        await self.http.start_server()
        self.p = module.Extension(self.runtime)
        self.p.config = {'base_url': str(self.http.make_url('/')).rstrip('/'),
                         'token': 'api-secret', 'conversation_enabled': True}
        self.p.client = module.Client(self.p.config)
        self.p.connected = True
        self.p.devices_cache = {self.device.id: {'online': True}}
        self.p.stopping = False
        self.p.voice_ready = lambda: True
        self.p.setup_voice()
        self.p.sync_voice_sources()
        self.loop = asyncio.create_task(self.p.voice_loop())
        await until(lambda: self.p.voice_bound)

    async def asyncTearDown(self):
        self.tts_gate.set()
        await self.device.cancel_playback()
        self.p.stopping = True
        await self.p.stop_voice()
        self.loop.cancel()
        await asyncio.gather(self.loop, return_exceptions=True)
        await self.runtime.conversation.stop()
        await self.p.client.close()
        self.app[HUB].devices.clear()
        await self.http.close()
        self.runtime.store.db.close()
        self.tmp.cleanup()

    async def input(self):
        await self.manager.begin(self.device, 'conversation', 'keyword')
        session = self.manager.sessions[self.device.id]
        session.waiting, session.turn = True, uuid4().hex
        await until(lambda: session.id in self.p.voice_sessions)
        self.manager.offer(self.manager.provider, {'type': 'input', 'device_id': self.device.id,
            'session_id': session.id, 'turn_id': session.turn, 'text': '你好，请介绍一下自己。'})
        await until(lambda: self.p.voice_sessions[session.id]['turn'] is not None)
        turn = self.p.voice_sessions[session.id]['turn']
        await until(lambda: bool(turn.event_id))
        return session, turn

    def run_context(self, turn):
        row = self.runtime.store.one('SELECT * FROM events WHERE id=?', (turn.event_id,))
        metadata = json.loads(row['meta'])
        key = metadata['conversation_source']
        run = uuid4().hex
        self.runtime.store.execute("INSERT INTO runs(id,event_id,started,status,trace,error) VALUES (?,?,?,'running','{}','')",
                                   (run, turn.event_id, time.time()))
        self.runtime.store.execute("UPDATE events SET status='running' WHERE id=?", (turn.event_id,))
        self.runtime.conversation.select(key)
        self.runtime.current_run = {'id': run, '_reply_location': {'source_id': key, 'context': metadata['reply_context']}}
        return run, metadata['reply_context']

    async def test_input_is_direct_main_source_and_trigger_is_not_input(self):
        await self.p.voice_packet({'type': 'event', 'event': 'interaction.triggered', 'device_id': self.device.id})
        self.assertEqual(self.runtime.store.one("SELECT COUNT(*) AS n FROM events WHERE kind='wake'")['n'], 0)
        _, turn = await self.input()
        row = self.runtime.store.one('SELECT * FROM events WHERE id=?', (turn.event_id,))
        self.assertEqual(row['target'], 'main')
        self.assertEqual(row['source'], 'audio_terminal')
        self.assertEqual(json.loads(row['meta'])['reply_context']['turn_id'], turn.turn_id)

    async def test_text_is_spoken_in_chunks_then_main_completion_reopens_listening(self):
        session, turn = await self.input()
        run, _ = self.run_context(turn)
        await self.runtime.conversation.respond('这是音箱的主会话回答。' * 25, run_id=run)
        key = self.runtime.store.kv_get('conversation.current', '')
        await asyncio.wait_for(self.runtime.conversation.sources[key]['queue'].join(), 3)
        self.assertGreater(len(self.device.played), 1)
        self.assertTrue(session.waiting)
        self.runtime.conversation.process('run.completed', run_id=run, agent_id='main')
        await until(lambda: not session.waiting)
        await until(lambda: self.p.voice_sessions[session.id]['turn'] is None)
        self.assertTrue(all(len(text) <= 180 for text in self.tts_texts))

    async def test_parameterless_end_is_idempotent_and_ignores_selected_device(self):
        session, turn = await self.input()
        self.assertEqual(await self.p.end_conversation(), {'ok': True})
        self.assertNotIn(self.device.id, self.manager.sessions)
        self.assertTrue(turn.closed.is_set())
        self.assertEqual(await self.p.end_conversation(), {'ok': True})

    async def test_explicit_stop_http_failure_closes_provider_as_fallback(self):
        session, turn = await self.input()
        self.p.client.request = AsyncMock(side_effect=ValueError('HTTP unavailable'))
        with self.assertRaises(ValueError):
            await self.p.end_conversation()
        await until(lambda: self.device.id not in self.manager.sessions)
        self.assertFalse(self.p.voice_bound)
        self.assertTrue(turn.closed.is_set())

    async def test_tool_error_is_not_run_failure(self):
        session, turn = await self.input()
        await self.p.voice_lifecycle(self.device.id, {'event':'tool.failed'})
        self.assertIn(self.device.id, self.manager.sessions)
        run, _ = self.run_context(turn)
        self.runtime.conversation.process('run.failed', run_id=run, agent_id='main')
        await until(lambda: self.device.id not in self.manager.sessions)

    async def test_empty_agent_result_finishes_without_fabricated_speech(self):
        session, turn = await self.input()
        run, _ = self.run_context(turn)
        self.runtime.conversation.process('run.completed', run_id=run, agent_id='main')
        await until(lambda: not session.waiting)
        self.assertEqual(self.device.played, [])

    async def test_ended_session_cancels_unclaimed_main_input_and_rejects_late_output(self):
        session, turn = await self.input()
        context = {'session_id': session.id, 'turn_id': turn.turn_id,
                   'connection': turn.connection, 'device_id': turn.device}
        await self.manager.end(session, sound=False)
        await until(lambda: session.id not in self.p.voice_sessions)
        row = self.runtime.store.one('SELECT status FROM events WHERE id=?', (turn.event_id,))
        self.assertEqual(row['status'], 'cancelled')
        with self.assertRaises(ValueError):
            await self.p.voice_text(self.device.id, {'text': '迟到回答', 'reply_context': context})
        self.assertEqual(self.device.played, [])

    async def test_disconnect_during_tts_never_starts_late_playback(self):
        session, turn = await self.input()
        run, _ = self.run_context(turn)
        self.tts_gate.clear()
        await self.runtime.conversation.respond('不能在断线后再播放。', run_id=run)
        await asyncio.wait_for(self.tts_started.wait(), 2)
        await self.manager.provider['ws'].close()
        await until(lambda: not self.p.voice_sessions)
        self.tts_gate.set()
        key = self.runtime.store.kv_get('conversation.current', '')
        await asyncio.wait_for(self.runtime.conversation.sources[key]['queue'].join(), 2)
        self.assertEqual(self.device.played, [])

    async def test_cleared_reply_context_does_not_turn_old_voice_answer_into_proactive_audio(self):
        _, turn = await self.input()
        run, _ = self.run_context(turn)
        with self.assertRaises(ValueError):
            await self.p.voice_text(self.device.id, {'text': '旧回答', 'run_id': run, 'reply_context': {}})
        self.assertEqual(self.device.played, [])

    async def test_other_provider_cannot_replace_the_bound_plugin(self):
        ws = await self.http.ws_connect('/v1/agent', headers={'Authorization': 'Bearer api-secret'})
        await ws.send_json({'type': 'declare', 'source_id': 'other', 'conversation': True,
                            'input': 'text', 'requires_asr': True})
        value = await ws.receive_json(timeout=2)
        self.assertEqual(value['error'], 'provider_already_bound')
        self.assertTrue(self.p.voice_bound)
        await ws.close()

    async def test_default_context_repeats_tool_reminder_at_each_model_step(self):
        from types import SimpleNamespace
        from sakubot.reply_location import describe
        _, turn = await self.input()
        run, context = self.run_context(turn)
        self.runtime.registry.plugins.append(self.p)
        invocation = SimpleNamespace(run_id=run, metadata={'_reply_location': self.runtime.current_run['_reply_location']})
        for _ in range(2):
            reminder = describe(self.runtime, invocation)
            self.assertIn('简短', reminder)
            self.assertIn('audio_terminal_end_conversation', reminder)
            self.assertIn(self.device.id, reminder)
        metadata = json.loads(self.runtime.store.one('SELECT meta FROM events WHERE id=?', (turn.event_id,))['meta'])
        self.assertEqual(metadata['temporary_context'], context['voice_context'])
        self.runtime.conversation.declare('other', 'channel', '其他来源', {})
        self.runtime.conversation.select('other.channel')
        self.assertEqual(describe(self.runtime, invocation), '')

    async def test_editing_context_keeps_connection_and_applies_to_next_turn(self):
        self.p.config['temporary_context'] = '旧要求：只回答一句。'
        session, turn = await self.input()
        _, context = self.run_context(turn)
        ws = self.p.voice_ws
        self.p.config['temporary_context'] = '新要求：先给结论，再用一句解释。'
        await self.p.settings_saved()
        self.assertIs(self.p.voice_ws, ws)
        self.assertTrue(self.p.voice_bound)
        self.assertIn('旧要求', self.p.reply_context_prompt(context))
        self.assertNotIn('新要求', self.p.reply_context_prompt(context))
        await self.manager.end(session, sound=False)
        await until(lambda: session.id not in self.p.voice_sessions)
        self.assertIn('已结束', self.p.reply_context_prompt(context))
        _, next_turn = await self.input()
        metadata = json.loads(self.runtime.store.one('SELECT meta FROM events WHERE id=?', (next_turn.event_id,))['meta'])
        self.assertIn('新要求', metadata['temporary_context'])
        self.assertNotIn('旧要求', metadata['temporary_context'])

    async def test_settings_persist_custom_context_and_reject_invalid_values(self):
        from sakubot.plugin_support import PluginConfig
        from sakubot.plugin_settings import public, save
        root = self.runtime.config.root / 'plugins/audio_terminal'
        root.mkdir(parents=True)
        (root / '__init__.py').write_text('')
        manifest = json.loads(Path('/plugin/plugin.json').read_text())
        (root / 'plugin.json').write_text(json.dumps(manifest))
        configuration = PluginConfig(self.p, defaults={f['key']: f['default'] for f in manifest['settings']['fields']}, secrets=('token',))
        configuration.update(self.p.config)
        self.p.config = self.p._configuration = configuration
        self.p._voice_transport_settings = self.p.voice_transport_settings()
        self.p.settings_form(manifest['settings']['fields'], on_saved=self.p.settings_saved)
        self.runtime.registry.plugins.append(self.p)
        original = self.p.voice_ws
        with patch('sakubot.plugin_settings.probe', new=AsyncMock()):
            await save(self.runtime, self.p.id, {'temporary_context': '自定义：简短回答，告别时调用结束工具。'})
            stored = json.loads(configuration.path.read_text())
            self.assertEqual(stored['temporary_context'], '自定义：简短回答，告别时调用结束工具。')
            self.assertEqual(stored['token'], 'api-secret')
            self.assertIs(self.p.voice_ws, original)
            for value in (123, 'x' * 8001):
                with self.assertRaises(ValueError):
                    await save(self.runtime, self.p.id, {'temporary_context': value})
        visible = public(self.runtime, self.p.id)
        self.assertEqual(visible['values']['token'], '')
        self.assertEqual(visible['values']['temporary_context'], stored['temporary_context'])


class ModelIntegration(unittest.IsolatedAsyncioTestCase):
    asyncTearDown = Integration.asyncTearDown
    run_context = Integration.run_context

    async def asyncSetUp(self):
        await Integration.asyncSetUp(self)
        await self.p.stop_voice()
        self.loop.cancel()
        await asyncio.gather(self.loop, return_exceptions=True)
        await until(lambda: self.manager.provider is None)
        self.p.config.update(speech_backend='models', asr_model_id='asr', tts_model_id='tts', auto_interrupt=True)
        self.speech_gate = asyncio.Event()
        self.speech_gate.set()
        self.asr_gate = asyncio.Event()
        self.asr_gate.set()
        self.asr_calls, self.tts_calls = [], []
        self.asr_fail = self.tts_fail = False
        owner = self
        from types import SimpleNamespace
        from sakubot.speech import AudioChunk
        class Speech:
            async def transcribe(self, model, audio):
                owner.asr_calls.append(audio)
                await owner.asr_gate.wait()
                if owner.asr_fail: raise ValueError('ASR failed')
                yield '你好。'
            async def synthesize(self, model, text, **kwargs):
                owner.tts_calls.append(text)
                if owner.tts_fail: raise ValueError('TTS failed')
                yield AudioChunk(b'\1\0' * 4800, 24000)
                await owner.speech_gate.wait()
                yield AudioChunk(b'\2\0' * 4800, 24000)
        self.runtime.speech = Speech()
        self.loop = asyncio.create_task(self.p.voice_loop())
        await until(lambda: self.p.voice_bound)
        self.assertTrue(self.manager.provider['input_stream'])

    async def input(self):
        from server.wire import Frame, PCM
        await self.manager.begin(self.device, 'conversation', 'keyword')
        session = self.manager.sessions[self.device.id]
        await until(lambda: session.id in self.p.voice_sessions)
        session.guard = 0
        self.manager.vad_states[self.device] = True
        for seq in range(10):
            pcm = b'\1\0' * 320
            self.manager.audio(self.device, Frame(PCM, 0, seq, seq * 20, pcm), pcm)
        await until(lambda: isinstance(self.p.voice_sessions[session.id]['turn'], module.model_audio.ModelTurn))
        turn = self.p.voice_sessions[session.id]['turn']
        self.assertEqual(self.asr_calls, [])
        self.manager.vad_states[self.device] = False
        session.tail = time.monotonic() - 1
        await until(lambda: bool(turn.event_id))
        return session, turn

    async def test_first_sentence_plays_before_final_and_is_not_repeated(self):
        session, turn = await self.input()
        run, context = self.run_context(turn)
        self.speech_gate.clear()
        self.runtime.conversation.process('model.delta', run_id=run, agent_id='main', request_id='r1', text='第一句。第二句')
        await asyncio.wait_for(self.device.pcm_started.wait(), 2)
        self.assertEqual(self.tts_calls, ['第一句。'])
        self.assertTrue(session.waiting)
        self.speech_gate.set()
        self.runtime.conversation.process('model.completed', run_id=run, agent_id='main', request_id='r1')
        await self.runtime.conversation.respond('第一句。第二句', run_id=run, response_id='r1')
        self.runtime.conversation.process('run.completed', run_id=run, agent_id='main')
        await until(lambda: not session.waiting)
        self.assertEqual(self.tts_calls, ['第一句。','第二句'])
        self.assertEqual(len(self.device.played), 1)
        self.assertEqual(len(self.asr_calls), 1)
        self.assertIsNone(self.p.voice_sessions[session.id]['turn'])

    async def test_interrupt_cancels_tts_and_rejects_late_output(self):
        session, turn = await self.input()
        run, context = self.run_context(turn)
        self.speech_gate.clear()
        self.runtime.conversation.process('model.delta', run_id=run, agent_id='main', request_id='r1', text='旧回答。')
        await asyncio.wait_for(self.device.pcm_started.wait(), 2)
        await self.manager.interrupt(session)
        await until(lambda: turn.closed.is_set())
        await until(lambda: turn.speech_task.done())
        count = len(self.device.received)
        self.speech_gate.set()
        await asyncio.sleep(.05)
        self.assertEqual(len(self.device.received), count)
        self.assertIs(self.manager.sessions[self.device.id], session)
        self.assertFalse(session.waiting)
        with self.assertRaises(ValueError):
            await self.p.voice_text(self.device.id, {'reply_context':context,'run_id':run,'text':'迟到'})
        self.assertIsNone(self.p.voice_sessions[session.id]['turn'])

    async def test_tts_failure_ends_session(self):
        session, turn = await self.input()
        run, _ = self.run_context(turn)
        self.tts_fail = True
        self.runtime.conversation.process('model.delta', run_id=run, agent_id='main', request_id='r1', text='失败。')
        await until(lambda: self.device.id not in self.manager.sessions)
        self.assertTrue(turn.closed.is_set())

    async def test_asr_failure_ends_session_without_agent_input(self):
        self.asr_fail = True
        with self.assertRaises(TimeoutError):
            await self.input()
        self.assertNotIn(self.device.id, self.manager.sessions)
        self.assertFalse(self.p.voice_sessions)
        self.assertEqual(self.runtime.store.one("SELECT COUNT(*) AS n FROM events WHERE kind='wake'")['n'], 0)

    async def test_interrupt_cancels_recognition_and_allows_next_turn(self):
        from server.wire import Frame, PCM
        self.asr_gate.clear()
        starting = asyncio.create_task(self.input())
        await until(lambda: bool(self.asr_calls))
        session = self.manager.sessions[self.device.id]
        old = self.p.voice_sessions[session.id]['turn']
        await self.manager.interrupt(session)
        await until(lambda: old.closed.is_set())
        await until(lambda: old.asr_task.done())
        starting.cancel()
        await asyncio.gather(starting, return_exceptions=True)
        self.asr_gate.set()
        session.guard = 0
        self.manager.vad_states[self.device] = True
        for seq in range(100,110):
            pcm = b'\1\0' * 320
            self.manager.audio(self.device, Frame(PCM,0,seq,seq*20,pcm), pcm)
        await until(lambda: self.p.voice_sessions[session.id]['turn'] is not None)
        new = self.p.voice_sessions[session.id]['turn']
        session.tail = time.monotonic()-1
        self.manager.vad_states[self.device] = False
        await until(lambda: bool(new.event_id))
        self.assertNotEqual(new.turn_id, old.turn_id)
        self.assertEqual(len(self.asr_calls), 2)

    async def test_dynamic_model_options_refresh_without_plugin_restart(self):
        from types import SimpleNamespace
        from sakubot.plugin_settings import declaration
        self.p.settings_form(self.p.speech_settings_fields)
        self.runtime.registry.plugins.append(self.p)
        self.p._settings_manifest_cache = {'settings': {'fields': []}}
        def options():
            return next(row['options'] for row in declaration(self.runtime,self.p.id)['fields'] if row['key']=='asr_model_id')
        self.assertEqual(len(options()), 1)
        self.runtime.config.settings.models.append(__import__('sakubot.config',fromlist=['ModelConfig']).ModelConfig(
            id='fresh-asr', provider_id='test', model_id='mimo-v2.5-asr',name='新增ASR',capabilities={'asr':True}))
        self.assertEqual(options()[-1]['value'], 'fresh-asr')

    async def test_model_settings_validate_actual_provider_model_pair(self):
        from sakubot.config import ModelConfig, ProviderConfig
        settings = self.runtime.config.settings
        settings.providers.append(ProviderConfig(id='speech-provider', name='MiMo', api_base='https://api.example.com/v1'))
        for kind in ('asr','tts'):
            settings.models.append(ModelConfig(id=kind, name=kind,provider_id='speech-provider',
                model_id='mimo-v2.5-'+kind, capabilities={kind:True,'text':False}))
        self.assertTrue(self.p.validate_speech_settings(self.p.config))
        settings.models[-1].enabled = False
        with self.assertRaises(ValueError):
            self.p.validate_speech_settings(self.p.config)

    async def test_agent_failure_ends_session_but_tool_error_does_not(self):
        session, turn = await self.input()
        run, _ = self.run_context(turn)
        await self.p.voice_lifecycle(self.device.id, {'event':'agent.tool_completed','run_id':run,
            'reply_context':self.runtime.current_run['_reply_location']['context'],'error':'工具参数错误'})
        self.assertIn(self.device.id, self.manager.sessions)
        self.runtime.conversation.process('run.failed', run_id=run, agent_id='main')
        await until(lambda: self.device.id not in self.manager.sessions)

    async def test_empty_response_finishes_and_parameterless_end_releases_lock(self):
        session, turn = await self.input()
        run, _ = self.run_context(turn)
        self.runtime.conversation.process('run.completed', run_id=run, agent_id='main')
        await until(lambda: not session.waiting)
        self.assertEqual(self.device.played, [])
        self.assertEqual(await self.p.end_conversation(), {'ok':True})
        self.assertNotIn(self.device.id, self.manager.sessions)


if __name__ == '__main__':
    unittest.main(verbosity=2)
