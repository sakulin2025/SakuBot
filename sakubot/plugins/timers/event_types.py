"""Documented plugin event contracts; TypedDict values are ordinary dicts."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

EventData1 = TypedDict('EventData1', {'scheduled_at': Required[Annotated[float, {'description': '计划触发时间，Unix 秒时间戳（UTC 基准）', 'x-unit': 'seconds'}]], 'observed_at': Required[Annotated[float, {'description': '实际发现到期时间，Unix 秒时间戳（UTC 基准）', 'x-unit': 'seconds'}]]}, total=False)

EventData: TypeAlias = Annotated[EventData1, {'description': '按绑定的 interval/daily/once 计划到期产生事件；实际观测时间可能晚于计划时间，不自动重放已完成的一次性任务。', 'examples': [{'scheduled_at': 1793926800, 'observed_at': 1793926800.1}], 'additionalProperties': True}]

EventParameters2 = TypedDict('EventParameters2', {'timing': Required[Annotated[Literal['interval', 'daily', 'once'], {'description': '定时触发方式', 'title': '触发方式', 'default': 'interval', 'x-enum-descriptions': {'interval': '固定间隔触发', 'daily': '指定时区每日触发', 'once': '指定绝对时间仅一次'}}]], 'interval_seconds': NotRequired[Annotated[int, {'description': '间隔触发时使用，单位：秒', 'title': '间隔 · 秒', 'minimum': 30, 'maximum': 31536000, 'default': 300, 'x-unit': 'seconds'}]], 'daily_time': NotRequired[Annotated[str, {'description': '每日触发时使用，HH:MM，按 timezone 解释', 'title': '每日时间', 'format': 'time', 'default': '09:00'}]], 'timezone': NotRequired[Annotated[str, {'description': 'IANA 时区名称，供每日触发解释本地时间，例如 Asia/Shanghai', 'title': '时区', 'default': 'Asia/Shanghai'}]], 'at': NotRequired[Annotated[str, {'description': '一次性触发时间，ISO 8601，必须包含时区偏移或 Z', 'title': '一次性时间 · ISO 8601'}]]}, total=False)

EventParameters: TypeAlias = Annotated[EventParameters2, {'additionalProperties': True}]
