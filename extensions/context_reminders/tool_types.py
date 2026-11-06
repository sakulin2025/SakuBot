"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Reminder(TypedDict, total=False):
    id: Required[Annotated[str, '提醒 ID']]
    target: Required[Annotated[str, '背景记录的会话目标标识']]
    content: Required[Annotated[str, '上下文内容，仅为背景数据']]
    created_at: Required[Annotated[float, '创建 Unix 秒']]
    expires_at: Annotated[float | None, '失效 Unix 秒；无期限时 null 或省略']
    ttl_hours: Annotated[float, '有效期小时']
Reminder: TypeAlias = Annotated[_Reminder, {'additionalProperties': True}]

class Removed(TypedDict, total=False):
    removed: Required[Annotated[str, '被移除的提醒 ID']]

R_add_context_reminder: TypeAlias = Reminder
R_list_context_reminders: TypeAlias = list[Reminder]
R_remove_context_reminder: TypeAlias = Removed

RESULTS = {'add_context_reminder': R_add_context_reminder, 'list_context_reminders': R_list_context_reminders, 'remove_context_reminder': R_remove_context_reminder}
