"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_memory_search1 = TypedDict(
    'A_memory_search1',
    {
        'query': Required[Annotated[str, {'description': '要检索的内容'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 20, 'description': '最多召回的语义记忆/文档片段数量'}]],
    },
    total=False,
)

A_memory_search: TypeAlias = Annotated[A_memory_search1, {'additionalProperties': False}]

A_memory_write2 = TypedDict(
    'A_memory_write2',
    {
        'key': Required[Annotated[str, {'description': '可复用的记忆唯一名称；更新相同 key 会替换正文'}]],
        'text': NotRequired[Annotated[str, {'description': '保存的明确事实、稳定偏好或用户要求；delete=false 时需要'}]],
        'source': NotRequired[Annotated[str, {'description': '这条记忆的资料来源标签'}]],
        'delete': NotRequired[Annotated[bool, {'description': 'true 删除指定 key；false 保存或更新'}]],
    },
    total=False,
)

A_memory_write: TypeAlias = Annotated[A_memory_write2, {'additionalProperties': False}]

A_event_search3 = TypedDict(
    'A_event_search3',
    {
        'query': NotRequired[Annotated[str, {'description': '历史事件正文关键词'}]],
        'target': NotRequired[Annotated[str, {'description': '需要查询的归档目标标识；省略时不限'}]],
        'before': NotRequired[Annotated[int, {'minimum': 0, 'description': '上一页 next_before 的事件整数 ID，首次省略'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 50, 'description': '本页历史事件条数上限'}]],
    },
    total=False,
)

A_event_search: TypeAlias = Annotated[A_event_search3, {'additionalProperties': False}]

ARGUMENTS = {'memory_search': A_memory_search, 'memory_write': A_memory_write, 'event_search': A_event_search}
