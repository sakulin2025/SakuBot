"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Post(TypedDict, total=False):
    id: Required[Annotated[str, 'Mattermost 消息唯一 ID']]
    channel_id: Annotated[str, '目标频道 ID']
    user_id: Annotated[str, '消息发送者 ID']
    message: Annotated[str, '消息正文']
    root_id: Annotated[str, '所属话题根消息 ID，空字符串为独立消息']
    create_at: Annotated[int, '创建时间，Unix 毫秒']
    update_at: Annotated[int, '更新时间，Unix 毫秒']
    file_ids: Annotated[list[str], '附件文件 ID 列表']
    props: Annotated[DynamicObject, '平台自定义消息属性，具体键取决于消息类型']
Post: TypeAlias = Annotated[_Post, {'additionalProperties': True}]

class _SendResult(TypedDict, total=False):
    id: Required[Annotated[str, '首段消息 ID；成功返回时保证存在']]
    split: Required[Annotated[bool, '是否实际分成多条消息发送']]
    part_count: Required[Annotated[int, '已成功发送的分段数量']]
    post_ids: Required[Annotated[list[str], '所有分段的消息 ID，按发送顺序']]
    channel_id: Annotated[str, '目标频道 ID']
    user_id: Annotated[str, '发消息的机器人用户 ID']
    message: Annotated[str, '首段实际发送正文']
    root_id: Annotated[str, '话题根消息 ID']
    file_ids: Annotated[list[str], '首段附带的文件 ID']
    create_at: Annotated[int, '首段创建时间，Unix 毫秒']
SendResult: TypeAlias = Annotated[_SendResult, {'additionalProperties': True}]

class _PostCollection(TypedDict, total=False):
    order: Annotated[list[str], '消息 ID 排序列表']
    posts: Required[Annotated[dict[str, Post], '以消息 ID 为键的消息字典']]
    next_post_id: Annotated[str, '平台分页游标，可能为空']
    prev_post_id: Annotated[str, '平台分页游标，可能为空']
    has_next: Annotated[bool, '平台是否声明仍有后续结果']
PostCollection: TypeAlias = Annotated[_PostCollection, {'additionalProperties': True}]

class _User(TypedDict, total=False):
    id: Annotated[str, '用户 ID']
    username: Annotated[str, '登录用户名']
    nickname: Annotated[str, '昵称']
    first_name: Annotated[str, '名字']
    last_name: Annotated[str, '姓氏']
    roles: Annotated[str, '平台角色字符串，不等于主人的信任权限']
User: TypeAlias = Annotated[_User, {'additionalProperties': True}]

class _Channel(TypedDict, total=False):
    id: Annotated[str, '频道 ID']
    team_id: Annotated[str, '团队 ID']
    type: Annotated[str, 'O 公开频道、P 私有频道、D 私聊、G 多人私聊']
    name: Annotated[str, '频道 URL 名称']
    display_name: Annotated[str, '频道显示名']
Channel: TypeAlias = Annotated[_Channel, {'additionalProperties': True}]

class _Team(TypedDict, total=False):
    id: Annotated[str, '团队 ID']
    name: Annotated[str, '团队 URL 名称']
    display_name: Annotated[str, '显示名称']
Team: TypeAlias = Annotated[_Team, {'additionalProperties': True}]

class _FileInfo(TypedDict, total=False):
    id: Annotated[str, '平台文件 ID']
    name: Annotated[str, '文件名']
    size: Annotated[int, '文件大小，字节']
    mime_type: Annotated[str, 'MIME 类型']
    extension: Annotated[str, '文件扩展名']
FileInfo: TypeAlias = Annotated[_FileInfo, {'additionalProperties': True}]

class Download(TypedDict, total=False):
    path: Required[Annotated[str, '保存的工作空间相对路径']]
    file_id: Required[Annotated[str, '原始 Mattermost 文件 ID']]
    size: Required[Annotated[int, '下载字节数']]

class _CommandRecord(TypedDict, total=False):
    id: Annotated[str, '本地托管命令 ID']
    trigger: Annotated[str, '不带斜杠的触发名称']
    display_name: Annotated[str, '显示名称']
    team_id: Annotated[str, '团队 ID']
    status: Annotated[str, '本地同步状态']
    enabled: Annotated[bool, '是否启用']
    command_id: Annotated[str, 'Mattermost 远端命令 ID']
    error: Annotated[str, '同步错误，空表示无已知错误']
    ready: Annotated[bool, '当前命令是否可用']
CommandRecord: TypeAlias = Annotated[_CommandRecord, {'additionalProperties': True}]

class _CommandResult(TypedDict, total=False):
    commands: Annotated[list[CommandRecord], '已声明命令列表']
    removed: Annotated[str | bool, '被删除的本地命令或删除标志']
    saved: Annotated[bool, '是否保存成功']
    synced: Annotated[bool, '是否完成远端同步']
    deleted: Annotated[str, '被删除的本地命令 ID']
    callback_url: Annotated[str, '当前 Slash 回调 URL']
    remote: Annotated[list[DynamicObject], '可选的远端指令清单，已移除令牌']
CommandResult: TypeAlias = Annotated[_CommandResult, {'additionalProperties': True}]

R_mattermost_send: TypeAlias = SendResult
R_mattermost_lookup: TypeAlias = User | Channel | list[User] | list[Channel] | list[Team] | DynamicObject | list[DynamicObject] | Truncated
R_mattermost_read_posts: TypeAlias = Post | PostCollection | Truncated
R_mattermost_post_action: TypeAlias = Post | DynamicObject | list[DynamicObject] | Truncated
R_mattermost_file: TypeAlias = FileInfo | Download | Truncated
R_mattermost_request: TypeAlias = DynamicJSON | Truncated
R_mattermost_command: TypeAlias = CommandRecord | CommandResult | list[CommandRecord]

RESULTS = {'mattermost_send': R_mattermost_send, 'mattermost_lookup': R_mattermost_lookup, 'mattermost_read_posts': R_mattermost_read_posts, 'mattermost_post_action': R_mattermost_post_action, 'mattermost_file': R_mattermost_file, 'mattermost_request': R_mattermost_request, 'mattermost_command': R_mattermost_command}
