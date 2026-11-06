"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Person(TypedDict, total=False):
    id: Annotated[str, '稳定 QQ 用户 ID']
    nickname: Annotated[str, '账号昵称，仅显示不用来授权']
    card: Annotated[str, '群名片，仅显示']
    groups: Annotated[DynamicObject | list[object], '按实际已见消息保存的群资料']
    names: Annotated[list[str], '历史称呼']
Person: TypeAlias = Annotated[_Person, {'additionalProperties': True}]

class _Message(TypedDict, total=False):
    id: Annotated[int, '本地归档分页 ID']
    uid: Annotated[str, '去重标识']
    at: Annotated[float, '消息 Unix 秒']
    session_id: Required[Annotated[str, 'Private:号码 或 Group:号码']]
    message_id: Required[Annotated[str, '平台消息 ID']]
    sender_id: Required[Annotated[str, '说话人 QQ ID']]
    sender_name: Required[Annotated[str, '说话人显示名']]
    sender_role: Annotated[str, '群角色标识']
    text: Required[Annotated[str, '框架预处理后的正文']]
    mentions: Annotated[list[str], '被提及的 QQ ID']
    parts: Annotated[list[DynamicObject], '已处理的消息内容块，字段按消息类型决定']
    reply_to: Annotated[str | None, '引用消息 ID']
    is_owner: Annotated[bool, '是否匹配配置的主人 QQ 号']
    identity: Annotated[DynamicObject, '当前 QQ 账号与主人 ID 环境']
Message: TypeAlias = Annotated[_Message, {'additionalProperties': True}]

class _SendResult(TypedDict, total=False):
    message_id: Annotated[int | str, 'OneBot 返回的已发送消息 ID']
    status: Annotated[str, '幂等投递状态，取决于底层动作记录']
    result: Annotated[DynamicJSON, '已保存的底层响应']
SendResult: TypeAlias = Annotated[_SendResult, {'additionalProperties': True}]

class Notice(TypedDict, total=False):
    id: Required[Annotated[int, '归档通知 ID']]
    at: Required[Annotated[float, '归档时间，Unix 秒']]
    data: Required[Annotated[DynamicObject, 'OneBot 通知/request 的实际数据，含处理申请所需 flag 时保留']]

class Notices(TypedDict, total=False):
    items: Required[Annotated[list[Notice], '本页归档通知']]
    next_before: Required[Annotated[int | None, '下一页 before 游标']]

class ApiDocs(TypedDict, total=False):
    backend: Required[Annotated[str, 'NapCat 或 SnowLuma 协议端标识']]
    docs: Required[Annotated[str, '对应协议端官方文档入口']]
    read_actions: Required[Annotated[list[str], '内置只读动作']]
    examples: Required[Annotated[dict[str, DynamicObject], '动作到参数示例的映射，仅为示例']]

R_people_lookup: TypeAlias = list[Person]
R_qq_send: TypeAlias = SendResult | DynamicJSON
R_qq_read: TypeAlias = DynamicJSON
R_qq_action: TypeAlias = DynamicJSON
R_qq_recent: TypeAlias = list[Message]
R_qq_notices: TypeAlias = Notices
R_qq_api: TypeAlias = ApiDocs

RESULTS = {'people_lookup': R_people_lookup, 'qq_send': R_qq_send, 'qq_read': R_qq_read, 'qq_action': R_qq_action, 'qq_recent': R_qq_recent, 'qq_notices': R_qq_notices, 'qq_api': R_qq_api}
