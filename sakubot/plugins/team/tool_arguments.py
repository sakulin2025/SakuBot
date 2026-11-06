"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_team_requests1 = TypedDict(
    'A_team_requests1',
    {
        'status': NotRequired[Annotated[Literal['waiting', 'answered', 'all'], {'description': 'waiting 仅待答复；all 包含全部请求'}]],
    },
    total=False,
)

A_team_requests: TypeAlias = Annotated[A_team_requests1, {'additionalProperties': False}]

A_team_resolve2 = TypedDict(
    'A_team_resolve2',
    {
        'request_id': Required[Annotated[str, {'description': '待确认工具返回的请求 ID'}]],
        'answer': NotRequired[Annotated[str, {'description': '给成员的文字答复；question类型需要'}]],
        'approved': NotRequired[Annotated[bool, {'description': 'confirmation 类型是否批准；question类型可省略'}]],
    },
    total=False,
)

A_team_resolve: TypeAlias = Annotated[A_team_resolve2, {'additionalProperties': False}]

A_team_members3 = TypedDict(
    'A_team_members3',
    {
    },
    total=False,
)

A_team_members: TypeAlias = Annotated[A_team_members3, {'additionalProperties': False}]

A_team_delegate4 = TypedDict(
    'A_team_delegate4',
    {
        'agent_id': Required[Annotated[str, {'description': 'team_members 返回的 Agent ID'}]],
        'goal': Required[Annotated[str, {'description': '任务目标与完成标准'}]],
        'context': NotRequired[Annotated[str, {'description': '必需资料'}]],
        'resources': NotRequired[Annotated[list[Annotated[str, {'description': '一个列表元素；本任务占用的资源标识列表，冲突资源不能同时操作'}]], {'maxItems': 10, 'description': '本任务占用的资源标识列表，冲突资源不能同时操作'}]],
        'timeout': NotRequired[Annotated[int, {'minimum': 30, 'maximum': 3600, 'description': '成员任务的执行超时秒数，不含等待确认时间'}]],
    },
    total=False,
)

A_team_delegate: TypeAlias = Annotated[A_team_delegate4, {'additionalProperties': False}]

A_team_tasks5 = TypedDict(
    'A_team_tasks5',
    {
        'action': Required[Annotated[Literal['list', 'get', 'cancel'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '团队任务 ID，不是智能体 ID'}]],
    },
    total=False,
)

A_team_tasks: TypeAlias = Annotated[A_team_tasks5, {'additionalProperties': False}]

A_team_create_member6 = TypedDict(
    'A_team_create_member6',
    {
        'name': Required[Annotated[str, {'description': '成员名称'}]],
        'description': Required[Annotated[str, {'description': '职责和适用任务'}]],
        'prompt': Required[Annotated[str, {'description': '完整人格和工作方式，不要把一次性任务当成人格'}]],
        'visible_plugins': NotRequired[Annotated[Annotated[list[Annotated[str, {'description': '一个列表元素；元素结构由该参数定义'}]], {'maxItems': 100}] | None, {'description': '可见插件 ID；null 表示所有插件，空数组表示不提供插件工具。团队待确认和报告函数需要包含 team。'}]],
        'model_id': NotRequired[Annotated[str, {'description': '框架模型条目 ID，留空继承默认'}]],
    },
    total=False,
)

A_team_create_member: TypeAlias = Annotated[A_team_create_member6, {'additionalProperties': False}]

A_team_get_member7 = TypedDict(
    'A_team_get_member7',
    {
        'agent_id': Required[Annotated[str, {'description': '团队 Agent ID'}]],
    },
    total=False,
)

A_team_get_member: TypeAlias = Annotated[A_team_get_member7, {'additionalProperties': False}]

A_team_update_member8 = TypedDict(
    'A_team_update_member8',
    {
        'agent_id': Required[Annotated[str, {'description': '团队 Agent ID'}]],
        'name': NotRequired[Annotated[str, {'description': '更新后的成员显示名；省略保留'}]],
        'description': NotRequired[Annotated[str, {'description': '更新后的职责描述；省略保留'}]],
        'prompt': NotRequired[Annotated[str, {'description': '自管理人格完整内容'}]],
        'visible_plugins': NotRequired[Annotated[Annotated[list[Annotated[str, {'description': '一个列表元素；元素结构由该参数定义'}]], {'maxItems': 100}] | None, {'description': '可见插件 ID；null 表示所有插件，空数组表示不提供插件工具。团队待确认和报告函数需要包含 team。'}]],
        'model_id': NotRequired[Annotated[str, {'description': '框架模型条目 ID，空字符串继承默认'}]],
    },
    total=False,
)

A_team_update_member: TypeAlias = Annotated[A_team_update_member8, {'additionalProperties': False}]

ARGUMENTS = {'team_requests': A_team_requests, 'team_resolve': A_team_resolve, 'team_members': A_team_members, 'team_delegate': A_team_delegate, 'team_tasks': A_team_tasks, 'team_create_member': A_team_create_member, 'team_get_member': A_team_get_member, 'team_update_member': A_team_update_member}
