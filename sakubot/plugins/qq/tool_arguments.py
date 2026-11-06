"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_people_lookup1 = TypedDict(
    'A_people_lookup1',
    {
        'query': Required[Annotated[str, {'description': 'QQ ID、昵称或历史群名片的检索词；同名必须按稳定 QQ ID 区分'}]],
    },
    total=False,
)

A_people_lookup: TypeAlias = Annotated[A_people_lookup1, {'additionalProperties': False}]

A_qq_send_segmentsItem3 = TypedDict(
    'A_qq_send_segmentsItem3',
    {
        'type': Required[Annotated[str, {'description': '消息段类型，例如 text/image/at'}]],
        'data': Required[Annotated[dict[str, object], {'description': '按段类型定义的数据，例如 text.text、at.qq'}]],
    },
    total=False,
)

A_qq_send2 = TypedDict(
    'A_qq_send2',
    {
        'target': NotRequired[Annotated[str, {'description': 'owner、main、private:QQ号、group:群号；留空使用本轮来源，main 使用当前 QQ 主会话源'}]],
        'text': NotRequired[Annotated[str, {'description': '要发送的文字'}]],
        'segments': NotRequired[Annotated[list[Annotated[A_qq_send_segmentsItem3, {'description': '一个列表元素；OneBot 消息段数组；每项包含 type 和按消息类型变化的 data，例如 type=text 时 data.text 为文字', 'additionalProperties': True}]], {'maxItems': 30, 'description': 'OneBot 消息段数组；每项包含 type 和按消息类型变化的 data，例如 type=text 时 data.text 为文字'}]],
    },
    total=False,
)

A_qq_send: TypeAlias = Annotated[A_qq_send2, {'additionalProperties': False}]

A_qq_read4 = TypedDict(
    'A_qq_read4',
    {
        'action': Required[Annotated[Literal['get_login_info', 'get_friend_list', 'get_group_list', 'get_group_info', 'get_group_member_list', 'get_group_member_info', 'get_stranger_info'], {'description': '只读 OneBot 动作名称，必须来自枚举'}]],
        'params': NotRequired[Annotated[dict[str, object], {'description': '所选 OneBot 动作的原生参数对象，例如 group_id/user_id；按 qq_api 文档填写'}]],
    },
    total=False,
)

A_qq_read: TypeAlias = Annotated[A_qq_read4, {'additionalProperties': False}]

A_qq_action5 = TypedDict(
    'A_qq_action5',
    {
        'action': Required[Annotated[str, {'description': '当前协议端的 OneBot action 名称'}]],
        'params': NotRequired[Annotated[dict[str, object], {'description': '所选 OneBot 动作的原生参数对象，具体结构查当前 NapCat/SnowLuma 文档，不包含认证令牌'}]],
    },
    total=False,
)

A_qq_action: TypeAlias = Annotated[A_qq_action5, {'additionalProperties': False}]

A_qq_recent6 = TypedDict(
    'A_qq_recent6',
    {
        'target': NotRequired[Annotated[str, {'description': '可选 private:QQ号 或 group:群号'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'description': '最多返回的已归档 QQ 消息条数，默认30，范围1至100'}]],
    },
    total=False,
)

A_qq_recent: TypeAlias = Annotated[A_qq_recent6, {'additionalProperties': False}]

A_qq_notices7 = TypedDict(
    'A_qq_notices7',
    {
        'before': NotRequired[Annotated[int, {'minimum': 1, 'description': '上一页 next_before 的本地通知 ID，首次省略'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'description': '最多返回的通知条数，默认30'}]],
    },
    total=False,
)

A_qq_notices: TypeAlias = Annotated[A_qq_notices7, {'additionalProperties': False}]

A_qq_api8 = TypedDict(
    'A_qq_api8',
    {
    },
    total=False,
)

A_qq_api: TypeAlias = Annotated[A_qq_api8, {'additionalProperties': False}]

ARGUMENTS = {'people_lookup': A_people_lookup, 'qq_send': A_qq_send, 'qq_read': A_qq_read, 'qq_action': A_qq_action, 'qq_recent': A_qq_recent, 'qq_notices': A_qq_notices, 'qq_api': A_qq_api}
