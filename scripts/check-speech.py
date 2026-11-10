"""Isolated speech contract checks. No external network or credentials."""
import asyncio
import array
import base64
import contextlib
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sakubot.catalog import speech_profile
from sakubot.config import Capabilities, ModelConfig, Settings
from sakubot.speech import Speech, SpeechError, events
from sakubot.speech_audio import PCMResampler, read_wav, wav_bytes


def settings(kind='asr', streaming=True, api='mimo'):
    return Settings(providers=[{'id': 'p', 'name': 'mock', 'api_base': 'https://speech.invalid/v1',
                               'api_key': 'test-secret'}],
        models=[{'id': 's', 'provider_id': 'p', 'model_id': 'mimo-v2.5-' + kind,
                 'speech_api': api, 'capabilities': {**speech_profile('mimo-v2.5-' + kind),
                                                   'streaming_output': streaming}}])


def sse(delta=None, finish=None):
    return ('data: ' + json.dumps({'choices': [{'delta': delta or {}, 'finish_reason': finish}]}) + '\n\n').encode()


class Stream(httpx.AsyncByteStream):
    def __init__(self, parts, gate=None):
        self.parts, self.gate, self.closed = parts, gate, False

    async def __aiter__(self):
        for index, part in enumerate(self.parts):
            if index and self.gate:
                await self.gate.wait()
            yield part

    async def aclose(self):
        self.closed = True


class AudioTests(unittest.TestCase):
    def test_resampling_is_chunk_boundary_independent(self):
        source = array.array('h', (round(10000 * math.sin(2 * math.pi * 440 * i / 24000))
                                   for i in range(24000))).tobytes()
        whole = PCMResampler(24000)
        expected = whole.feed(source) + whole.finish()
        chunks = PCMResampler(24000)
        actual = b''.join(chunks.feed(source[i:i+317]) for i in range(0, len(source), 317)) + chunks.finish()
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 32000)
        self.assertLessEqual(len(chunks.samples), 40)
        self.assertEqual(chunks.finish(), b'')

    def test_equal_rate_preserves_pcm_and_partial_samples(self):
        source = array.array('h', range(-100, 100)).tobytes()
        converter = PCMResampler(16000)
        result = b''.join(converter.feed(source[i:i+7]) for i in range(0, len(source), 7)) + converter.finish()
        self.assertEqual(result, source)
        with self.assertRaises(ValueError):
            PCMResampler(24000).feed(b'x')  # No error until finish.
            # Reached below only when feed correctly keeps the partial sample.
            converter = PCMResampler(24000)
            converter.feed(b'x')
            converter.finish()

    def test_downsampling_rejects_alias_band(self):
        def rms(frequency):
            source = array.array('h', (round(10000 * math.sin(2 * math.pi * frequency * i / 24000))
                                       for i in range(4800))).tobytes()
            converter = PCMResampler(24000)
            pcm = array.array('h')
            pcm.frombytes(converter.feed(source) + converter.finish())
            return math.sqrt(sum(x*x for x in pcm[128:-128]) / len(pcm[128:-128]))
        self.assertLess(rms(10000), rms(1000) * .05)

    def test_wav_validation_and_roundtrip(self):
        data = array.array('h', range(320)).tobytes()
        self.assertEqual(read_wav(wav_bytes(data)), (data, 16000))
        with self.assertRaises(ValueError):
            read_wav(wav_bytes(data)[:-1])

    def test_model_flags_are_independent_and_old_configs_load(self):
        self.assertFalse(Capabilities().asr)
        model = ModelConfig(provider_id='p', model_id='old')
        self.assertFalse(model.capabilities.realtime)
        self.assertTrue(speech_profile('mimo-v2.5-asr')['streaming_output'])
        self.assertFalse(Capabilities(**speech_profile('mimo-v2.5-asr')).streaming_input)
        self.assertFalse(Capabilities(**speech_profile('mimo-v2.5-asr')).realtime)
        self.assertFalse(speech_profile('mimo-v2.5-tts-voiceclone')['streaming_output'])
        with self.assertRaises(ValueError):
            settings().selected_speech_model('s', 'tts')


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_asr_stream_preserves_unicode_and_complete_audio_contract(self):
        captured = []
        async def handler(request):
            captured.append(json.loads(request.content))
            raw = sse({'content': '你好'}) + sse({'content': '世界'}, 'stop') + b'data: [DONE]\n\n'
            return httpx.Response(200, stream=Stream([raw[:11], raw[11:35], raw[35:]]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            speech = Speech(settings(), client)
            wav = wav_bytes(b'\0' * 640)
            text = ''.join([part async for part in speech.transcribe('s', wav)])
        self.assertEqual(text, '你好世界')
        self.assertTrue(captured[0]['stream'])
        audio = captured[0]['messages'][0]['content'][0]['input_audio']['data']
        self.assertEqual(base64.b64decode(audio.split(',', 1)[1]), wav)

    async def test_first_tts_chunk_arrives_before_response_finishes(self):
        gate = asyncio.Event()
        stream = Stream([sse({'audio': {'data': base64.b64encode(b'\1\0' * 80).decode()}}),
                         sse(finish='stop') + b'data: [DONE]\n\n'], gate)
        async def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload['audio']['format'], 'pcm16')
            self.assertEqual(payload['messages'][-1], {'role': 'assistant', 'content': '你好。'})
            return httpx.Response(200, stream=stream)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            async with contextlib.aclosing(Speech(settings('tts'), client).synthesize('s', '你好。')) as generator:
                first = await asyncio.wait_for(anext(generator), .5)
                self.assertEqual(first.sample_rate, 24000)
                self.assertEqual(len(first.pcm), 160)
                self.assertFalse(gate.is_set())
                gate.set()
                self.assertEqual([part async for part in generator], [])
        self.assertTrue(stream.closed)

    async def test_cancel_closes_http_response_without_retrying_audio(self):
        gate = asyncio.Event()
        stream = Stream([sse({'audio': {'data': base64.b64encode(b'\1\0' * 80).decode()}}),
                         sse(finish='stop')], gate)
        requests = 0
        async def handler(request):
            nonlocal requests
            requests += 1
            return httpx.Response(200, stream=stream)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = Speech(settings('tts'), client).synthesize('s', '取消。')
            await anext(generator)
            waiting = asyncio.create_task(anext(generator))
            await asyncio.sleep(0)
            waiting.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiting
            await generator.aclose()
        self.assertTrue(stream.closed)
        self.assertEqual(requests, 1)

    async def test_provider_error_does_not_echo_secrets_or_audio(self):
        async def handler(request):
            return httpx.Response(401, text='test-secret audio-private-data')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(SpeechError) as raised:
                _ = [p async for p in Speech(settings(), client).transcribe('s', wav_bytes(b'\0' * 640))]
            self.assertNotIn('test-secret', str(raised.exception))

    async def test_truncated_stream_rejected_after_partial_output(self):
        async def handler(request):
            return httpx.Response(200, stream=Stream([sse({'content': '部分文字'})]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            generator = Speech(settings(), client).transcribe('s', wav_bytes(b'\0' * 640))
            self.assertEqual(await anext(generator), '部分文字')
            with self.assertRaises(SpeechError):
                await anext(generator)


if __name__ == '__main__':
    unittest.main(verbosity=2)
