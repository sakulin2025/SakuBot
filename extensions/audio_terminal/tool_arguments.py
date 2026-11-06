"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_audio_terminal_devices1 = TypedDict(
    'A_audio_terminal_devices1',
    {
        'refresh': NotRequired[Annotated[bool, {'description': 'true 立即刷新；默认使用后台最多约五秒的设备列表缓存。', 'default': False}]],
    },
    total=False,
)

A_audio_terminal_devices: TypeAlias = Annotated[A_audio_terminal_devices1, {'additionalProperties': False}]

A_audio_terminal_status2 = TypedDict(
    'A_audio_terminal_status2',
    {
        'device': Required[Annotated[str, {'description': '设备列表返回的完整设备 ID'}]],
    },
    total=False,
)

A_audio_terminal_status: TypeAlias = Annotated[A_audio_terminal_status2, {'additionalProperties': False}]

A_audio_terminal_control3 = TypedDict(
    'A_audio_terminal_control3',
    {
        'device': Required[Annotated[str, {'description': '设备列表中的完整 device_id。'}]],
        'action': Required[Annotated[str, {'description': 'volume/wake/upload/knock/save。'}]],
        'parameters': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'volume 用 {volume:0到100}；wake 用 {module:knock/keyword/disabled}；upload 用 {mode:vad/continuous/session/off,session_open:布尔可选}；knock 可填 min_peak、noise_ratio、min_interval_ms、max_interval_ms、cooldown_ms；save 传空对象。'}] | None, {'default': None, 'description': '固件控制参数：volume 用 volume；wake 用 module；upload 用 mode/session_open；knock 用阈值和时间参数；save 用空对象'}]],
    },
    total=False,
)

A_audio_terminal_control: TypeAlias = Annotated[A_audio_terminal_control3, {'additionalProperties': False}]

A_audio_terminal_stop4 = TypedDict(
    'A_audio_terminal_stop4',
    {
        'device': Required[Annotated[str, {'description': '需要停止播放的完整设备 ID'}]],
    },
    total=False,
)

A_audio_terminal_stop: TypeAlias = Annotated[A_audio_terminal_stop4, {'additionalProperties': False}]

A_audio_terminal_play5 = TypedDict(
    'A_audio_terminal_play5',
    {
        'device': Required[Annotated[str, {'description': '设备列表中的完整 device_id。'}]],
        'path': Required[Annotated[str, {'description': '工作空间相对文件路径，不接受 URL。'}]],
    },
    total=False,
)

A_audio_terminal_play: TypeAlias = Annotated[A_audio_terminal_play5, {'additionalProperties': False}]

A_audio_terminal_events6 = TypedDict(
    'A_audio_terminal_events6',
    {
        'device': NotRequired[Annotated[str, {'description': '完整设备 ID；留空查询所有设备。', 'default': ''}]],
        'limit': NotRequired[Annotated[int, {'description': '最近事件数量，1到200。', 'default': 50}]],
        'event': NotRequired[Annotated[str, {'description': '事件名前缀，例如 wake.、playback.；留空不限。', 'default': ''}]],
    },
    total=False,
)

A_audio_terminal_events: TypeAlias = Annotated[A_audio_terminal_events6, {'additionalProperties': False}]

ARGUMENTS = {'audio_terminal_devices': A_audio_terminal_devices, 'audio_terminal_status': A_audio_terminal_status, 'audio_terminal_control': A_audio_terminal_control, 'audio_terminal_stop': A_audio_terminal_stop, 'audio_terminal_play': A_audio_terminal_play, 'audio_terminal_events': A_audio_terminal_events}
