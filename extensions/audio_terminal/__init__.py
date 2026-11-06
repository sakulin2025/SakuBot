"""Audio Terminal device control, event feed and script trigger sources."""
from .tool_arguments import ARGUMENTS
from .tool_types import R_audio_terminal_control, R_audio_terminal_devices, R_audio_terminal_events, R_audio_terminal_play, R_audio_terminal_status, R_audio_terminal_stop
from .tool_types import RESULTS
from .event_docs import PARAMETERS, EVENT, ID_DESCRIPTION
import asyncio
from collections import deque
import contextlib
import json
import time
from pathlib import Path
from uuid import uuid4

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException
from sakubot.plugin import Plugin, object_schema, text

from .client import Client, MAX_WAV, base_url, control_params, device_id


class Extension(Plugin):
    tool_result_types = RESULTS
    tool_argument_types = ARGUMENTS
    name = 'audio_terminal'

    def setup(self):
        self.config = self.configure({'base_url': 'http://esp32-audio-terminal:8765', 'token': '',
                                      'subscribe_events': True}, secrets=('token',))
        fields = json.loads((Path(__file__).parent / 'plugin.json').read_text())['settings']['fields']
        self.settings_form(fields, on_saved=self.settings_saved)
        self.client = Client(self.config)
        saved = self.state.get('events', [])
        if not isinstance(saved, list):
            raise ValueError('音频终端插件存储格式错误，请检查已有数据')
        self.history = deque(saved[-200:], maxlen=400)
        self.devices_cache = {}
        self.streams = {}
        self.connected = False
        self.error = ''
        self.observed_at = 0
        self.dirty = False
        self.stopping = False
        self.epoch = 0
        self.refresh_lock = asyncio.Lock()
        self.command_locks = {}
        for name, handler in [('audio_terminal_devices', self.devices), ('audio_terminal_status', self.status),
                ('audio_terminal_control', self.control), ('audio_terminal_stop', self.stop_playback),
                ('audio_terminal_play', self.play_file), ('audio_terminal_events', self.events)]:
            self.function(handler, name=name)
        self.page('manage', '音频终端', Path(__file__).parent / 'web' / 'dist', group_id='network', icon='connection')
        self.api('state', self.api_state)
        self.api('refresh', self.api_refresh, methods=('POST',))
        self.api('control', self.api_control, methods=('POST',))
        self.api('play/{device}', self.api_play, methods=('PUT',))
        self.skill('control', Path(__file__).parent / 'skills' / 'control')
        for family, label in [('wake', '设备唤醒'), ('button', '设备按键'),
                              ('playback', '播放事件'), ('connection', '设备连接状态')]:
            self.trigger_source(family + '.*', label, PARAMETERS, EVENT, id_description=ID_DESCRIPTION, options=self.trigger_options,
                                match=lambda event, values: not values.get('device_id') or values['device_id'] == event['device_id'])

    def availability(self):
        try:
            base_url(self.config.get('base_url', ''))
            self.client.headers()
            return {'available': True, 'reason': ''}
        except ValueError as exc:
            return {'available': False, 'reason': str(exc)}

    def prompt_context(self, invocation):
        return ('音频终端通过 audio_terminal_devices/status 查询，control 调节音量、唤醒模块、上传策略，'
                'play 播放工作空间中的 16kHz 单声道 PCM16 WAV，stop 停播。设备 ID 从列表取得。'
                '本插件尚未识别或合成语音；唤醒事件不包含用户说话内容。播放请求成功不代表播放完成，'
                '完成以 playback.completed 事件为准。超时结果未知，不自动重复命令。')

    async def start(self):
        self.stopping = False
        self.background(self.discovery_loop())
        self.background(self.flush_loop())

    async def stop(self):
        self.stopping = True
        self.epoch += 1
        await super().stop()
        self.streams.clear()
        self.flush()
        await self.client.close()

    async def settings_saved(self):
        await self.stop()
        self.client = Client(self.config)
        self.connected = False
        self.error = ''
        for row in self.devices_cache.values():
            row['online'] = None
            row['events_connected'] = False
        await self.start()

    def flush(self):
        if self.dirty:
            self.state.set('events', list(self.history)[-200:])
            self.dirty = False

    async def flush_loop(self):
        while True:
            await asyncio.sleep(2)
            self.flush()

    def display_name(self, identity):
        return identity

    def trigger_options(self):
        return {'device_id': [{'value': key, 'label': self.display_name(key)} for key in self.devices_cache]}

    async def record(self, identity, name, data=None, timestamp=None, uid=None, publish=True):
        row = {'id': uid or uuid4().hex, 'device_id': identity, 'event': name,
               'received_at': time.time() * 1000, 'timestamp_ms': timestamp,
               'data': data if isinstance(data, dict) else {}}
        # The feed is bounded; no microphone audio is opened or stored by this plugin.
        self.history.append(row)
        self.dirty = True
        family = ('wake' if name == 'wake.detected' else 'button' if name == 'input.button' else
                  'playback' if name.startswith(('playback.', 'bridge.playback_')) else
                  'connection' if name.startswith('device.') else None)
        if family and publish:
            try:
                await self.emit_trigger(family + '.' + identity, row, uid=row['id'])
            except Exception:
                self.runtime.store.log('warning', self.id, 'trigger.failed', data={'device_id': identity})
        return row

    async def discovery_loop(self):
        while True:
            await self.refresh()
            await asyncio.sleep(5)

    async def refresh(self):
        async with self.refresh_lock:
            epoch = self.epoch
            if not self.availability()['available']:
                self.connected = False
                self.error = self.availability()['reason']
                return
            try:
                rows = await self.client.devices()
                if epoch != self.epoch or self.stopping:
                    return
                self.connected, self.error, self.observed_at = True, '', time.time() * 1000
                online = {row['device_id']: row for row in rows}
                # Keep the monitor bounded even if a bridge returns many identities over time.
                for identity in list(self.devices_cache):
                    if identity not in online and self.devices_cache[identity]['online'] is not False:
                        self.devices_cache[identity]['online'] = False
                        await self.record(identity, 'device.offline')
                for identity, info in list(online.items())[:32]:
                    if identity not in self.devices_cache:
                        if len(self.devices_cache) >= 64:
                            victim = next((key for key, value in self.devices_cache.items() if value['online'] is False), None)
                            if victim is None:
                                continue
                            self.devices_cache.pop(victim)
                            self.command_locks.pop(victim, None)
                        self.devices_cache[identity] = {'device_id': identity, 'online': False,
                            'status': None, 'status_at': 0, 'error': '', 'events_connected': False}
                    row = self.devices_cache[identity]
                    was_offline = row['online'] is False
                    row.update(online=True, hello=info['hello'])
                    if was_offline:
                        await self.record(identity, 'device.online')
                await self.sync_streams()
                targets = [key for key, row in self.devices_cache.items()
                           if row['online'] is True and time.time() * 1000 - row['status_at'] > 10000]
                semaphore = asyncio.Semaphore(4)
                async def update(identity):
                    async with semaphore:
                        with contextlib.suppress(ValueError):
                            await self.read_status(identity)
                await asyncio.gather(*(update(identity) for identity in targets))
            except ValueError as exc:
                if epoch == self.epoch:
                    self.connected, self.error = False, str(exc)
                    for row in self.devices_cache.values():
                        row['online'] = None
                    await self.sync_streams()

    async def sync_streams(self):
        wanted = {key for key, row in self.devices_cache.items() if row['online'] is True
                  and self.connected and self.config.get('subscribe_events')}
        for identity in set(self.streams) - wanted:
            task = self.streams.pop(identity)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        for identity in wanted:
            if identity not in self.streams or self.streams[identity].done():
                self.streams[identity] = self.background(self.event_loop(identity))

    async def event_loop(self, identity):
        delay = 1
        row = self.devices_cache[identity]
        while not self.stopping:
            try:
                async with connect(self.client.events_url(identity), additional_headers=self.client.headers(),
                                   proxy=None, open_timeout=8, close_timeout=2, max_size=16384,
                                   max_queue=32, ping_interval=20, ping_timeout=20) as ws:
                    row['events_connected'], row['events_error'] = True, ''
                    delay = 1
                    epoch = uuid4().hex
                    sequence = 0
                    async for packet in ws:
                        if not isinstance(packet, str):
                            continue
                        event = json.loads(packet)
                        if not isinstance(event, dict) or event.get('type') != 'event':
                            continue
                        name = event.get('event')
                        data = event.get('data')
                        timestamp = event.get('timestamp_ms')
                        if not isinstance(name, str) or len(name) > 80 or not isinstance(data, dict):
                            continue
                        if type(timestamp) not in (int, float) or not 0 <= timestamp <= 1e15:
                            timestamp = None
                        # Reject non-finite numbers before persisting/forwarding device data.
                        json.dumps(data, allow_nan=False)
                        sequence += 1
                        await self.record(identity, name, data, timestamp,
                                          uid=epoch + ':' + str(sequence))
            except (ValueError, OSError, WebSocketException):
                row['events_error'] = '事件连接断开，正在重连；断线期间事件不会补传'
            finally:
                row['events_connected'] = False
            await asyncio.sleep(delay)
            delay = min(delay * 2, 15)

    def resolve(self, identity):
        identity = device_id(identity)
        if identity not in self.devices_cache:
            raise ValueError('设备尚未发现，请刷新设备列表')
        if self.devices_cache[identity]['online'] is not True or not self.connected:
            raise ValueError('设备当前离线或状态未知')
        return identity

    async def read_status(self, identity):
        identity = self.resolve(identity)
        epoch = self.epoch
        try:
            value = await self.client.command(identity, 'device.status')
            if epoch == self.epoch:
                self.devices_cache[identity].update(status=value, status_at=time.time() * 1000, error='')
            return value
        except ValueError as exc:
            if epoch == self.epoch:
                self.devices_cache[identity]['error'] = str(exc)
            raise

    async def devices(self, refresh: bool=False) -> R_audio_terminal_devices:
        """查询音频终端设备、名称、在线状态、固件与事件连接。状态带观察时间；服务不可达时在线状态为未知。

        Args:
            refresh(bool): true 立即刷新；默认使用后台最多约五秒的设备列表缓存。
        """
        if refresh:
            await self.refresh()
        return {'connected': self.connected, 'error': self.error, 'observed_at': self.observed_at,
                'items': [{**row, 'name': self.display_name(key)}
                          for key, row in self.devices_cache.items()]}

    async def status(self, device: str) -> R_audio_terminal_status:
        """查询指定音频终端的实时状态。device 使用 audio_terminal_devices 返回的完整设备 ID。"""
        return {'device_id': device, 'status': await self.read_status(device)}

    async def control(self, device: str, action: str, parameters: dict=None) -> R_audio_terminal_control:
        """调节音频终端；多次调用按设备串行，超时不自动重试。音量由固件自身保存，其他设置显式调用 save 保存。

        Args:
            device(string): 设备列表中的完整 device_id。
            action(string): volume/wake/upload/knock/save。
            parameters(object): volume 用 {volume:0到100}；wake 用 {module:knock/keyword/disabled}；upload 用 {mode:vad/continuous/session/off,session_open:布尔可选}；knock 可填 min_peak、noise_ratio、min_interval_ms、max_interval_ms、cooldown_ms；save 传空对象。
        """
        identity = self.resolve(device)
        async with self.command_locks.setdefault(identity, asyncio.Lock()):
            method, params = control_params(action, {} if parameters is None else parameters,
                                           (self.devices_cache[identity].get('status') or {}).get('knock'))
            result = await self.client.command(identity, method, params)
            await self.record(identity, 'control.applied', {'action': action, 'parameters': params}, publish=False)
            # Read failure after a successful command must not turn success into an unknown retry.
            with contextlib.suppress(ValueError):
                await self.read_status(identity)
            return {'ok': True, 'device_id': identity, 'result': result}

    async def stop_playback(self, device: str) -> R_audio_terminal_stop:
        """停止设备当前播放。查询实时 playback_id 后停止；不自动重试结果未知的请求。"""
        identity = self.resolve(device)
        async with self.command_locks.setdefault(identity, asyncio.Lock()):
            status = await self.read_status(identity)
            if not status.get('playing') or not status.get('playback_id'):
                return {'ok': True, 'already_stopped': True}
            result = await self.client.command(identity, 'playback.stop', {'playback_id': status['playback_id']})
            with contextlib.suppress(ValueError):
                await self.read_status(identity)
            return {'ok': True, 'result': result}

    async def play_file(self, device: str, path: str) -> R_audio_terminal_play:
        """播放共享工作空间中的 16kHz、单声道 PCM16 WAV，最长120秒。会替换设备原有播放；返回接受不代表播放完成，完成事件见 audio_terminal_events。

        Args:
            device(string): 设备列表中的完整 device_id。
            path(string): 工作空间相对文件路径，不接受 URL。
        """
        self.resolve(device)
        target = self.workspace.path(path, allow_root=False)
        def read():
            with target.open('rb') as source:
                return source.read(MAX_WAV + 1)
        try:
            data = await asyncio.to_thread(read)
        except OSError:
            raise ValueError('无法读取工作空间中的音频文件') from None
        return await self.play_data(device, data)

    async def play_data(self, identity, data):
        identity = self.resolve(identity)
        async with self.command_locks.setdefault(identity, asyncio.Lock()):
            result = await self.client.play(identity, data)
            await self.record(identity, 'control.playback_accepted',
                              {'playback_id': result['playback_id'], 'duration_seconds': result['duration_seconds']}, publish=False)
            with contextlib.suppress(ValueError):
                await self.read_status(identity)
            return result

    def events(self, device: str='', limit: int=50, event: str='') -> R_audio_terminal_events:
        """读取有界的设备事件历史。断线期间无补传；VAD/训练候选只记录，不自动唤醒 Agent。

        Args:
            device(string): 完整设备 ID；留空查询所有设备。
            limit(int): 最近事件数量，1到200。
            event(string): 事件名前缀，例如 wake.、playback.；留空不限。
        """
        if device:
            device_id(device)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('limit 必须为1到200的整数')
        rows = [row for row in reversed(list(self.history)) if (not device or row['device_id'] == device)
                and row['event'].startswith(event)]
        return {'items': rows[:limit], 'total_retained': len(rows), 'limit': limit}

    async def api_state(self, request):
        return {**await self.devices(), 'events': self.events(request.query_params.get('device', ''), limit=200)['items'],
                'subscribe_events': bool(self.config.get('subscribe_events'))}

    async def api_refresh(self, request):
        await self.refresh()
        return await self.devices()

    async def api_control(self, request):
        data = await request.json()
        if not isinstance(data, dict) or set(data) - {'device', 'action', 'parameters'}:
            raise ValueError('控制请求格式不正确')
        if data.get('action') == 'stop':
            return await self.stop_playback(data.get('device'))
        if data.get('action') == 'status':
            return await self.status(data.get('device'))
        return await self.control(data.get('device'), data.get('action'), data.get('parameters'))

    async def api_play(self, request):
        identity = self.resolve(request.path_params['device'])
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_WAV:
                raise ValueError('WAV 文件过大，最长120秒')
        return await self.play_data(identity, bytes(data))
