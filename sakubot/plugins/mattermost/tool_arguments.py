"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_mattermost_command1 = TypedDict(
    'A_mattermost_command1',
    {
        'action': Required[Annotated[Literal['list', 'get', 'save', 'enable', 'disable', 'repair', 'rotate_token', 'delete'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '本地指令 ID；新建时不填'}]],
        'team_id': NotRequired[Annotated[str, {'description': '创建指令的 Mattermost 团队 ID'}]],
        'trigger': NotRequired[Annotated[str, {'description': '指令名称，不带 /，字母、数字、下划线或连字符'}]],
        'display_name': NotRequired[Annotated[str, {'description': '显示名称，最多 64 字'}]],
        'description': NotRequired[Annotated[str, {'description': '自动补全描述，最多 256 字'}]],
        'hint': NotRequired[Annotated[str, {'description': '自动补全参数提示，最多 128 字'}]],
        'script_id': NotRequired[Annotated[str, {'description': '可选，设置脚本动作；留空保留框架现有动作'}]],
        'params': NotRequired[Annotated[dict[str, object], {'description': '传给脚本的固定参数；Slash 参数来自事件 text'}]],
        'user_id': NotRequired[Annotated[str, {'description': '可选，仅接受此用户；留空不限'}]],
        'channel_id': NotRequired[Annotated[str, {'description': '可选，仅接受此频道；留空不限'}]],
        'enabled': NotRequired[Annotated[bool, {'description': '是否启用此托管命令；停用不删除远端记录'}]],
        'confirm': NotRequired[Annotated[bool, {'description': 'delete 时仅在明确确认删除远端指令和本地绑定后为true'}]],
        'remote': NotRequired[Annotated[bool, {'description': 'list 时同时查询团队的远端指令，需 team_id'}]],
    },
    total=False,
)

A_mattermost_command: TypeAlias = Annotated[A_mattermost_command1, {'additionalProperties': False}]

A_mattermost_lookup2 = TypedDict(
    'A_mattermost_lookup2',
    {
        'action': Required[Annotated[Literal['me', 'user', 'users_search', 'teams', 'channels', 'channel', 'members'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '用户 ID、频道 ID；user 也支持 @用户名'}]],
        'team_id': NotRequired[Annotated[str, {'description': 'channels 使用的团队 ID'}]],
        'query': NotRequired[Annotated[str, {'description': 'users_search 的搜索词'}]],
        'page': NotRequired[Annotated[int, {'minimum': 0, 'maximum': 10000, 'default': 0, 'description': '从0开始的页码，默认0'}]],
        'per_page': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'default': 30, 'description': '每页条数，默认30，最大100'}]],
    },
    total=False,
)

A_mattermost_lookup: TypeAlias = Annotated[A_mattermost_lookup2, {'additionalProperties': False}]

A_mattermost_read_posts3 = TypedDict(
    'A_mattermost_read_posts3',
    {
        'action': Required[Annotated[Literal['list', 'get', 'thread', 'search'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'channel_id': NotRequired[Annotated[str, {'description': 'list 使用的频道 ID'}]],
        'post_id': NotRequired[Annotated[str, {'description': 'get 或 thread 使用的消息 ID'}]],
        'team_id': NotRequired[Annotated[str, {'description': 'search 使用的团队 ID'}]],
        'query': NotRequired[Annotated[str, {'description': 'search 搜索词'}]],
        'page': NotRequired[Annotated[int, {'minimum': 0, 'maximum': 10000, 'default': 0, 'description': '从0开始的页码，默认0'}]],
        'per_page': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'default': 30, 'description': '每页条数，默认30，最大100'}]],
    },
    total=False,
)

A_mattermost_read_posts: TypeAlias = Annotated[A_mattermost_read_posts3, {'additionalProperties': False}]

A_mattermost_send4 = TypedDict(
    'A_mattermost_send4',
    {
        'channel_id': NotRequired[Annotated[str, {'description': '频道 ID'}]],
        'user_id': NotRequired[Annotated[str, {'description': '私聊目标用户 ID，与 channel_id 二选一'}]],
        'message': NotRequired[Annotated[str, {'description': '消息正文'}]],
        'root_id': NotRequired[Annotated[str, {'description': '可选的父消息 ID'}]],
        'files': NotRequired[Annotated[list[Annotated[str, {'description': '工作空间相对路径'}]], {'maxItems': 5, 'description': '工作空间相对文件路径列表，最多5个；附件只随首个消息分段发送'}]],
    },
    total=False,
)

A_mattermost_send: TypeAlias = Annotated[A_mattermost_send4, {'additionalProperties': False}]

A_mattermost_post_action5 = TypedDict(
    'A_mattermost_post_action5',
    {
        'action': Required[Annotated[Literal['edit', 'delete', 'react', 'unreact', 'pin', 'unpin', 'reactions'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'post_id': Required[Annotated[str, {'description': '消息 ID'}]],
        'message': NotRequired[Annotated[str, {'description': 'edit 的新内容'}]],
        'emoji': NotRequired[Annotated[str, {'description': 'react/unreact 的表情名，不带冒号'}]],
    },
    total=False,
)

A_mattermost_post_action: TypeAlias = Annotated[A_mattermost_post_action5, {'additionalProperties': False}]

A_mattermost_file6 = TypedDict(
    'A_mattermost_file6',
    {
        'action': Required[Annotated[Literal['info', 'download', 'upload'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'file_id': NotRequired[Annotated[str, {'description': 'info/download 的文件 ID'}]],
        'channel_id': NotRequired[Annotated[str, {'description': 'upload 的频道 ID'}]],
        'path': NotRequired[Annotated[str, {'description': '工作空间中的下载目标或上传源路径'}]],
    },
    total=False,
)

A_mattermost_file: TypeAlias = Annotated[A_mattermost_file6, {'additionalProperties': False}]

A_mattermost_request7 = TypedDict(
    'A_mattermost_request7',
    {
        'method': Required[Annotated[Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], {'description': '官方 REST HTTP 方法，写请求不自动重试'}]],
        'path': Required[Annotated[str, {'description': '官方 API 路径，例如 /api/v4/teams；不要传 URL、查询字符串或令牌'}]],
        'query': NotRequired[Annotated[dict[str, object], {'description': '所选 REST 端点的查询参数对象；键和值按该端点定义'}]],
        'body': NotRequired[Annotated[Annotated[dict[str, object], {'description': '所选 REST 端点的 JSON 请求体，可为对象、数组或null；结构由 path 决定'}] | Annotated[list[object], {'description': '所选 REST 端点的 JSON 请求体，可为对象、数组或null；结构由 path 决定'}] | Annotated[None, {'description': '所选 REST 端点的 JSON 请求体，可为对象、数组或null；结构由 path 决定'}], {'description': '所选 REST 端点的 JSON 请求体，可为对象、数组或null；结构由 path 决定'}]],
    },
    total=False,
)

A_mattermost_request: TypeAlias = Annotated[A_mattermost_request7, {'additionalProperties': False}]

ARGUMENTS = {'mattermost_command': A_mattermost_command, 'mattermost_lookup': A_mattermost_lookup, 'mattermost_read_posts': A_mattermost_read_posts, 'mattermost_send': A_mattermost_send, 'mattermost_post_action': A_mattermost_post_action, 'mattermost_file': A_mattermost_file, 'mattermost_request': A_mattermost_request}
