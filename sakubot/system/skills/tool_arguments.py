"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_skill_list1 = TypedDict(
    'A_skill_list1',
    {
        'query': NotRequired[Annotated[str, {'description': '名称、ID或描述关键词'}]],
        'offset': NotRequired[Annotated[int, {'minimum': 0, 'description': '从0开始的技能条目偏移'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'description': '最多返回的技能条目数，默认50'}]],
    },
    total=False,
)

A_skill_list: TypeAlias = Annotated[A_skill_list1, {'additionalProperties': False}]

A_skill_read2 = TypedDict(
    'A_skill_read2',
    {
        'id': Required[Annotated[str, {'description': '例如 workspace.files、team.collaboration 或 local.example'}]],
    },
    total=False,
)

A_skill_read: TypeAlias = Annotated[A_skill_read2, {'additionalProperties': False}]

A_skill_read_file3 = TypedDict(
    'A_skill_read_file3',
    {
        'id': Required[Annotated[str, {'description': '完整技能 ID，例如 team.collaboration'}]],
        'path': Required[Annotated[str, {'description': '相对于技能目录的路径'}]],
        'offset': NotRequired[Annotated[int, {'minimum': 0, 'description': '从0开始的行偏移'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 500, 'description': '本次读取的最大行数，默认200'}]],
    },
    total=False,
)

A_skill_read_file: TypeAlias = Annotated[A_skill_read_file3, {'additionalProperties': False}]

ARGUMENTS = {'skill_list': A_skill_list, 'skill_read': A_skill_read, 'skill_read_file': A_skill_read_file}
