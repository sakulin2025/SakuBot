"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_message_sources1 = TypedDict(
    'A_message_sources1',
    {
    },
    total=False,
)

A_message_sources: TypeAlias = Annotated[A_message_sources1, {'additionalProperties': False}]

A_message_select_source2 = TypedDict(
    'A_message_select_source2',
    {
        'source_id': Required[Annotated[str, {'description': 'message_sources 返回的主会话源完整 ID'}]],
    },
    total=False,
)

A_message_select_source: TypeAlias = Annotated[A_message_select_source2, {'additionalProperties': False}]

A_message_set_source_trust3 = TypedDict(
    'A_message_set_source_trust3',
    {
        'source_id': Required[Annotated[str, {'description': '完整主会话源 ID'}]],
        'trusted': Required[Annotated[bool, {'description': 'true 设为可信，false 取消信任；执行时仍会校验本轮的可信来源环境'}]],
    },
    total=False,
)

A_message_set_source_trust: TypeAlias = Annotated[A_message_set_source_trust3, {'additionalProperties': False}]

A_message_send_partsItem5 = TypedDict(
    'A_message_send_partsItem5',
    {
        'type': Required[Annotated[Literal['text', 'image', 'video', 'audio', 'file'], {'description': '内容块类型：text/image/video/audio/file；不同类型使用对应正文或媒体字段'}]],
        'text': NotRequired[Annotated[str, {'description': 'text 类型正文'}]],
        'url': NotRequired[Annotated[str, {'description': '媒体 HTTP/HTTPS 地址或框架附件 URL'}]],
        'path': NotRequired[Annotated[str, {'description': '共享工作空间中的本地文件相对路径；与 url 二选一'}]],
        'name': NotRequired[Annotated[str, {'description': '可选文件名'}]],
    },
    total=False,
)

A_message_send4 = TypedDict(
    'A_message_send4',
    {
        'parts': Required[Annotated[list[Annotated[A_message_send_partsItem5, {'description': '一个列表元素；按发送顺序的消息内容块；type=text 用 text，媒体用 url 或工作空间 path 二选一', 'additionalProperties': False}]], {'minItems': 1, 'maxItems': 10, 'description': '按发送顺序的消息内容块；type=text 用 text，媒体用 url 或工作空间 path 二选一'}]],
    },
    total=False,
)

A_message_send: TypeAlias = Annotated[A_message_send4, {'additionalProperties': False}]

ARGUMENTS = {'message_sources': A_message_sources, 'message_select_source': A_message_select_source, 'message_set_source_trust': A_message_set_source_trust, 'message_send': A_message_send}
