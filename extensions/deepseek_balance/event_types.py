"""Documented plugin event contracts; TypedDict values are ordinary dicts."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

EventData1 = TypedDict('EventData1', {'provider_id': Required[Annotated[str, {'description': '框架供应商唯一 ID'}]], 'provider_name': NotRequired[Annotated[str, {'description': '供应商显示名称'}]], 'currency': Required[Annotated[str, {'description': '金额的币种代码，例如 CNY；所有金额均使用此币种'}]], 'previous_balance': Required[Annotated[str, {'description': '上次成功查询的总余额，十进制金额字符串，单位由 currency 指定'}]], 'balance': Required[Annotated[str, {'description': '本次总余额，十进制金额字符串，单位由 currency 指定'}]], 'threshold': Required[Annotated[str, {'description': '触发使用的预警金额，十进制字符串，单位由 currency 指定'}]], 'fetched_at': Required[Annotated[str, {'description': '本次查询时间，ISO 8601，包含时区偏移'}]]}, total=False)

EventData: TypeAlias = Annotated[EventData1, {'description': '轮询发现同一供应商、同一币种的总余额由大于预警值变为小于等于预警值。首次查询只建基线，不触发。金额为十进制字符串。', 'examples': [{'provider_id': 'deepseek', 'provider_name': 'DeepSeek', 'currency': 'CNY', 'previous_balance': '10.01', 'balance': '9.98', 'threshold': '10', 'fetched_at': '2026-11-06T09:00:00+08:00'}], 'additionalProperties': True}]

EventParameters2 = TypedDict('EventParameters2', {'provider_id': NotRequired[Annotated[str, {'description': '框架供应商 ID；留空匹配所有 DeepSeek 官方供应商', 'title': '供应商 ID'}]], 'currency': NotRequired[Annotated[str, {'description': '余额币种，例如 CNY 或 USD；留空不限', 'title': '币种'}]]}, total=False)

EventParameters: TypeAlias = Annotated[EventParameters2, {'additionalProperties': True}]
