"""Authenticated Audio Terminal v1 client. Commands are never retried."""
import io
import json
import math
import re
import wave
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

DEVICE = re.compile(r'^[A-Za-z0-9:_-]{1,64}$')
MAX_WAV = 3_840_044


def device_id(value):
    if not isinstance(value, str) or not DEVICE.fullmatch(value):
        raise ValueError('请使用设备列表中的完整设备 ID')
    return value


def base_url(value):
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        valid = (parsed.scheme in ('http', 'https') and parsed.hostname and not
                 (parsed.username or parsed.password or parsed.query or parsed.fragment) and
                 not any(c.isspace() for c in value))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError('请填写音频终端服务的 HTTP/HTTPS 地址')
    return value.rstrip('/')


def validate_wav(data):
    if len(data) > MAX_WAV:
        raise ValueError('音频不能超过 120 秒')
    try:
        with wave.open(io.BytesIO(data), 'rb') as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError('请选择 16kHz、单声道、PCM16 WAV')
            frames = source.getnframes()
            if not 0 < frames <= 1_920_000 or len(source.readframes(frames)) != frames * 2:
                raise ValueError('WAV 为空、被截断或超过 120 秒')
            return frames / 16000
    except (wave.Error, EOFError):
        raise ValueError('无法读取 WAV 文件') from None


def control_params(action, values, current=None):
    if not isinstance(values, dict):
        raise ValueError('parameters 必须为对象')
    rules = {
        'volume': ('speaker.volume', {'volume'}),
        'wake': ('wake.select', {'module'}),
        'upload': ('audio.upload.configure', {'mode', 'session_open'}),
        'knock': ('wake.configure', {'min_peak', 'noise_ratio', 'min_interval_ms', 'max_interval_ms', 'cooldown_ms'}),
        'save': ('config.save', set()),
    }
    if not isinstance(action, str) or action not in rules:
        raise ValueError('action 请选择 volume、wake、upload、knock 或 save')
    method, allowed = rules[action]
    if set(values) - allowed:
        raise ValueError('包含此操作不支持的字段')
    if action == 'volume' and (type(values.get('volume')) is not int or not 0 <= values['volume'] <= 100):
        raise ValueError('volume 必须是 0–100 的整数')
    if action == 'wake' and values.get('module') not in ('knock', 'keyword', 'disabled'):
        raise ValueError('module 请选择 knock、keyword 或 disabled')
    if action == 'upload':
        if values.get('mode') not in ('vad', 'continuous', 'session', 'off'):
            raise ValueError('mode 请选择 vad、continuous、session 或 off')
        if 'session_open' in values and type(values['session_open']) is not bool:
            raise ValueError('session_open 必须为布尔值')
    if action == 'knock':
        if not values:
            raise ValueError('请填写至少一个敲击参数')
        ranges = {'min_peak': (300, 15000), 'noise_ratio': (2, 20),
                  'min_interval_ms': (80, 999), 'max_interval_ms': (81, 1000), 'cooldown_ms': (500, 10000)}
        for key, value in values.items():
            low, high = ranges[key]
            if (type(value) not in (int, float) or not low <= value <= high or
                    not math.isfinite(value) or (key != 'noise_ratio' and type(value) is not int)):
                raise ValueError('敲击参数范围或类型无效：' + key)
        merged = {**(current or {}), **values}
        if merged.get('min_interval_ms', 80) >= merged.get('max_interval_ms', 1000):
            raise ValueError('最长间隔必须大于最短间隔')
    return method, dict(values)


class Client:
    def __init__(self, config):
        self.config = config
        self.http = httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False,
                                      limits=httpx.Limits(max_connections=16, max_keepalive_connections=8))

    def headers(self):
        token = self.config.get('token', '')
        if not isinstance(token, str) or not token.strip() or any(c in token for c in '\r\n'):
            raise ValueError('请配置音频终端 API_TOKEN')
        return {'Authorization': 'Bearer ' + token.strip()}

    async def close(self):
        await self.http.aclose()

    def path(self, identity, suffix):
        return '/v1/devices/' + quote(device_id(identity), safe='') + suffix

    def events_url(self, identity):
        url = urlsplit(base_url(self.config.get('base_url', '')) + self.path(identity, '/events'))
        return urlunsplit(('wss' if url.scheme == 'https' else 'ws', url.netloc, url.path, '', ''))

    async def request(self, method, path, **kwargs):
        try:
            async with self.http.stream(method, base_url(self.config.get('base_url', '')) + path,
                                        headers=self.headers(), **kwargs) as response:
                if response.status_code in (401, 403):
                    raise ValueError('音频终端认证失败，请检查 API_TOKEN')
                if response.status_code == 404:
                    raise ValueError('设备离线或不存在')
                if response.status_code == 504:
                    raise ValueError('命令结果未知，请查询设备状态后决定是否重试')
                if response.status_code >= 400:
                    raise ValueError('音频终端请求失败（HTTP ' + str(response.status_code) + '）')
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 1_048_576:
                        raise ValueError('音频终端响应过大')
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError('音频终端响应格式不正确')
                return value
        except httpx.HTTPError:
            reason = '命令结果未知，请查询状态后决定是否重试' if method != 'GET' else '无法连接音频终端服务'
            raise ValueError(reason) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError('音频终端响应不是有效 JSON') from None

    async def devices(self):
        value = await self.request('GET', '/v1/devices')
        rows = value.get('devices')
        if not isinstance(rows, list) or len(rows) > 64:
            raise ValueError('设备列表格式或数量不正确')
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('hello'), dict):
                raise ValueError('设备列表格式不正确')
            device_id(row.get('device_id'))
        return rows

    async def command(self, identity, method, params=None):
        value = await self.request('POST', self.path(identity, '/commands'),
                                   json={'method': method, 'params': params or {}})
        if value.get('ok') is not True:
            errors = {'invalid_params': '设备拒绝参数', 'wake_module_unavailable': '此唤醒模块暂不可用',
                      'unsupported_method': '设备不支持此操作'}
            raise ValueError(errors.get(str(value.get('error')), '设备未执行命令'))
        result = value.get('result', {})
        return result if isinstance(result, dict) else {}

    async def play(self, identity, data):
        duration = validate_wav(data)
        value = await self.request('POST', self.path(identity, '/playback'), content=data,
                                   timeout=10)
        if value.get('ok') is not True or type(value.get('playback_id')) is not int:
            raise ValueError('设备未接受播放')
        return {**value, 'duration_seconds': duration, 'completed': False}
