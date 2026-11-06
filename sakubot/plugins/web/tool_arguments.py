"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_web_search1 = TypedDict(
    'A_web_search1',
    {
        'query': Required[Annotated[str, {'description': '搜索关键词'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 8, 'description': '最多搜索结果数，默认5，范围1至8'}]],
        'time_range': NotRequired[Annotated[Literal['', 'day', 'week', 'month', 'year'], {'description': '时间范围：空不限，day一天、week一周、month一月、year一年'}]],
    },
    total=False,
)

A_web_search: TypeAlias = Annotated[A_web_search1, {'additionalProperties': False}]

A_web_fetch2 = TypedDict(
    'A_web_fetch2',
    {
        'url': Required[Annotated[str, {'description': '完整网页 URL'}]],
        'offset': NotRequired[Annotated[int, {'minimum': 0, 'description': '静态正文的0起始字符偏移'}]],
        'max_chars': NotRequired[Annotated[int, {'minimum': 500, 'maximum': 12000, 'description': '本页最多正文字数，默认8000，500至12000'}]],
        'refresh': NotRequired[Annotated[bool, {'description': 'true 跳过短期缓存重新抓取'}]],
    },
    total=False,
)

A_web_fetch: TypeAlias = Annotated[A_web_fetch2, {'additionalProperties': False}]

ARGUMENTS = {'web_search': A_web_search, 'web_fetch': A_web_fetch}
