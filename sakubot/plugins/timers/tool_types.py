"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _ScheduleData(TypedDict, total=False):
    content: Annotated[str, '任务提示词或通知正文']
    mode: Annotated[str, 'wake/context/notify/script']
    script_id: Annotated[str, 'script 模式脚本 ID']
    script_params: Annotated[DynamicObject, '脚本参数，按脚本 Schema 校验']
    send_result_to_source: Annotated[bool, '是否向主会话源投递']
    interval_seconds: Annotated[int, '重复间隔秒数']
    daily_time: Annotated[str, '每日 HH:MM']
    timezone: Annotated[str, 'IANA 时区']
    at: Annotated[str, '一次性含时区 ISO8601']
ScheduleData: TypeAlias = Annotated[_ScheduleData, {'additionalProperties': True}]

class _Schedule(TypedDict, total=False):
    id: Required[Annotated[str, '定时任务 ID']]
    data: Required[Annotated[ScheduleData, '任务定义']]
    next_at: Required[Annotated[float | None, '下一次 Unix 秒；已完成任务可为空']]
Schedule: TypeAlias = Annotated[_Schedule, {'additionalProperties': True}]

class Deleted(TypedDict, total=False):
    deleted: Required[Annotated[str, '已删除任务 ID']]

R_schedule_manage: TypeAlias = Schedule | list[Schedule] | Deleted

RESULTS = {'schedule_manage': R_schedule_manage}
