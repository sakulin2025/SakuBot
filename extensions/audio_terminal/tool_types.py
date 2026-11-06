"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Device(TypedDict, total=False):
    id: Annotated[str, '设备 ID']
    device_id: Annotated[str, '设备 ID']
    name: Annotated[str, '设备显示名']
    online: Annotated[bool | None, '在线状态，连接故障时未知']
    events_connected: Annotated[bool, '设备事件流是否连接']
    events_error: Annotated[str, '事件流错误']
Device: TypeAlias = Annotated[_Device, {'additionalProperties': True}]

class DeviceList(TypedDict, total=False):
    connected: Required[Annotated[bool, '终端服务是否连接']]
    error: Required[Annotated[str, '连接错误，正常为空']]
    observed_at: Required[Annotated[float, '最近观测时间，Unix 毫秒']]
    items: Required[Annotated[list[Device], '设备资料']]

class Status(TypedDict, total=False):
    device_id: Required[Annotated[str, '查询设备 ID']]
    status: Required[Annotated[DynamicObject, '设备/固件状态动态字段，包括音量、唤醒或播放状态等，具体以固件为准']]

class _Control(TypedDict, total=False):
    ok: Annotated[bool, '请求是否被接受，不等于播放结束']
    device_id: Annotated[str, '设备 ID']
    result: Annotated[DynamicJSON, '服务原始控制确认']
    already_stopped: Annotated[bool, '是否原本已停止']
    request_id: Annotated[str, '播放请求 ID']
    playback_id: Annotated[int, '固件返回的整数播放 ID']
    duration_seconds: Annotated[float, '播放音频时长，秒']
    completed: Annotated[bool, '仅接受播放时为 false，播放完成以事件为准']
    status: Annotated[str, '原始服务确认状态']
Control: TypeAlias = Annotated[_Control, {'additionalProperties': True}]

class AudioEvent(TypedDict, total=False):
    id: Required[Annotated[str, '去重 ID']]
    device_id: Required[Annotated[str, '设备 ID']]
    event: Required[Annotated[str, '原始事件名']]
    received_at: Required[Annotated[float, '接收 Unix 毫秒']]
    timestamp_ms: Required[Annotated[float | None, '固件原始毫秒时钟，未提供为 null']]
    data: Required[Annotated[DynamicObject, '按 event 类型变化的事件载荷']]

class Events(TypedDict, total=False):
    items: Required[Annotated[list[AudioEvent], '最近事件，最新在前']]
    total_retained: Required[Annotated[int, '保留的匹配事件数']]
    limit: Required[Annotated[int, '本次条数上限']]

R_audio_terminal_devices: TypeAlias = DeviceList
R_audio_terminal_status: TypeAlias = Status
R_audio_terminal_control: TypeAlias = Control
R_audio_terminal_stop: TypeAlias = Control
R_audio_terminal_play: TypeAlias = Control
R_audio_terminal_events: TypeAlias = Events

RESULTS = {'audio_terminal_devices': R_audio_terminal_devices, 'audio_terminal_status': R_audio_terminal_status, 'audio_terminal_control': R_audio_terminal_control, 'audio_terminal_stop': R_audio_terminal_stop, 'audio_terminal_play': R_audio_terminal_play, 'audio_terminal_events': R_audio_terminal_events}
