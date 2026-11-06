"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Server(TypedDict, total=False):
    id: Required[Annotated[str, '保存条目 ID']]
    name: Required[Annotated[str, '名称']]
    alias: Annotated[str, '别名']
    description: Annotated[str, '本地描述']
    edition: Required[Annotated[str, 'java/bedrock']]
    address: Required[Annotated[str, '保存的域名/IP，可包含端口；实际查询以此字段为准']]
    host: Annotated[str, '服务器域名或 IP']
    port: Annotated[int, '查询端口']
    display_name: Required[Annotated[str, '优先使用别名的显示名称']]
Server: TypeAlias = Annotated[_Server, {'additionalProperties': True}]

class ServerList(TypedDict):
    items: Annotated[list[Server], '保存的服务器条目']
    total: Annotated[int, '条目总数']

class SavedServer(TypedDict):
    saved: Annotated[Literal[True], '条目已保存']
    server: Annotated[Server, '保存后的完整条目']

class RemovedServer(TypedDict):
    removed: Annotated[str, '已删除条目 ID']

Servers: TypeAlias = ServerList | SavedServer | RemovedServer

class StatusBase(TypedDict):
    server: Annotated[Server, '查询目标的本地条目资料']
    checked_at: Annotated[str, '含时区 ISO8601 查询时间']
    cached: Annotated[bool, '是否来自缓存']
    age_seconds: Annotated[float, '缓存年龄秒数']

class OnlineStatus(StatusBase):
    online: Annotated[Literal[True], '状态协议可达']
    state: Annotated[Literal['online'], '已成功查询在线状态']
    version: Annotated[str, '服务器自报版本']
    protocol: Annotated[int, '协议版本号']
    motd: Annotated[str, '已转换为纯文本的服务器公告']
    latency_ms: Annotated[float, '状态查询延迟，毫秒']
    players_online: Annotated[int, '当前在线人数']
    players_max: Annotated[int, '服务器人数容量']
    player_sample: Annotated[list[str], '可能不完整的服务器自报玩家样本']
    sample_note: Annotated[str, '玩家样本的可靠性说明']
    map_name: NotRequired[Annotated[str | None, '基岩版地图名称']]
    gamemode: NotRequired[Annotated[str | None, '基岩版游戏模式']]

class UnreachableStatus(StatusBase):
    online: Annotated[None, '无法确认当前在线状态；不代表确定关服']
    state: Annotated[Literal['unreachable'], '未收到有效状态响应']
    error: Annotated[str, '不可达原因']
    error_type: Annotated[str, '查询异常类别']
    note: Annotated[str, '不能将不可达等同关服的提示']

Status: TypeAlias = OnlineStatus | UnreachableStatus

class StatusList(TypedDict, total=False):
    items: Required[Annotated[list[Status], '逐服务器查询结果']]
    total: Required[Annotated[int, '查询目标数']]
    note: Required[Annotated[str, '数据可靠性提示']]

class Alerts(TypedDict, total=False):
    saved: Annotated[bool, '是否保存']
    polling: Required[Annotated[DynamicObject, '轮询设置和运行状态，包含间隔、连续失败阈值及最近时间']]
    alerts: Required[Annotated[list[DynamicObject], '持久提醒规则，按所选提醒类型解释 threshold']]
    notification_history: Required[Annotated[list[DynamicObject], '最近事件和投递结果']]

R_minecraft_servers: TypeAlias = Server | Servers
R_minecraft_status: TypeAlias = StatusList
R_minecraft_alerts: TypeAlias = Alerts

RESULTS = {'minecraft_servers': R_minecraft_servers, 'minecraft_status': R_minecraft_status, 'minecraft_alerts': R_minecraft_alerts}
