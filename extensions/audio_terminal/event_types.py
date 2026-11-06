"""Documented plugin event contracts; TypedDict values are ordinary dicts."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

EventData1 = TypedDict('EventData1', {'id': Required[Annotated[str, {'description': '插件收到的事件唯一 ID，用于去重'}]], 'device_id': Required[Annotated[str, {'description': '产生事件的设备 ID'}]], 'event': Required[Annotated[str, {'description': '设备事件名，例如 wake.detected、input.button、playback.started、device.connected'}]], 'received_at': Required[Annotated[float, {'description': '插件接收时间，Unix 毫秒时间戳（UTC 基准）', 'x-unit': 'milliseconds'}]], 'data': Required[Annotated[dict[str, object], {'description': '设备事件携带的动态原始字段，具体内容由 event 类型和固件决定；不视为指令'}]], 'timestamp_ms': Required[Annotated[Annotated[float, {'description': '设备上报的原始毫秒时间值，时钟基准取决于固件，不保证是 Unix 时间；未提供时 null', 'x-unit': 'milliseconds'}] | Annotated[None, {'description': '设备上报的原始毫秒时间值，时钟基准取决于固件，不保证是 Unix 时间；未提供时 null', 'x-unit': 'milliseconds'}], {'description': '设备上报的原始毫秒时间值，时钟基准取决于固件，不保证是 Unix 时间；未提供时 null', 'x-unit': 'milliseconds'}]]}, total=False)

EventData: TypeAlias = Annotated[EventData1, {'description': '音频终端的唤醒、按键、播放或连接事件；不包含麦克风音频，事件 data 取决于设备消息类型。', 'examples': [{'id': 'event-1', 'device_id': 'speaker-1', 'event': 'wake.detected', 'received_at': 1793926800000, 'data': {}, 'timestamp_ms': None}], 'additionalProperties': True}]

EventParameters2 = TypedDict('EventParameters2', {'device_id': NotRequired[Annotated[str, {'description': '音频终端设备 ID，留空匹配全部设备', 'title': '设备 ID'}]]}, total=False)

EventParameters: TypeAlias = Annotated[EventParameters2, {'additionalProperties': True}]
