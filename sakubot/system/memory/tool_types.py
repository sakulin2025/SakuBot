"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Match(TypedDict, total=False):
    key: Required[Annotated[str, '记忆或文档块 ID']]
    text: Required[Annotated[str, '记忆正文或文档片段']]
    source: Required[Annotated[str, '数据来源']]
    score: Required[Annotated[float, '向量相似度']]
    kind: Annotated[str, '记忆或文档分类']
    updated: Annotated[float, '更新时间，Unix 秒']
    id: Annotated[str | int, '记录标识']
Match: TypeAlias = Annotated[_Match, {'additionalProperties': True}]

class SavedMemory(TypedDict):
    saved: Annotated[str, '已保存的记忆 key']

class DeletedMemory(TypedDict):
    deleted: Annotated[str, '已删除的记忆 key']

Write: TypeAlias = SavedMemory | DeletedMemory

class _Event(TypedDict, total=False):
    id: Required[Annotated[int, '历史事件 ID']]
    kind: Annotated[str, '事件类型']
    source: Annotated[str, '来源']
    content: Annotated[str, '事件内容']
    target: Annotated[str, '目标']
    actor: Annotated[str, '说话人标识']
    at: Annotated[float, '事件 Unix 秒']
    meta: Annotated[str | DynamicObject, '存储的事件元数据，可能为 JSON 字符串']
    status: Annotated[str, '处理状态']
Event: TypeAlias = Annotated[_Event, {'additionalProperties': True}]

class EventPage(TypedDict, total=False):
    items: Required[Annotated[list[Event], '匹配的历史事件']]
    next_before: Required[Annotated[int | None, '下一页 before 游标，无条目时为空']]

R_memory_search: TypeAlias = list[Match]
R_memory_write: TypeAlias = Write
R_event_search: TypeAlias = EventPage

RESULTS = {'memory_search': R_memory_search, 'memory_write': R_memory_write, 'event_search': R_event_search}
