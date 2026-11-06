"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Source(TypedDict, total=False):
    id: Required[Annotated[str, '完整来源 ID']]
    plugin_id: Required[Annotated[str, '声明插件 ID']]
    name: Required[Annotated[str, '显示名称']]
    trusted: Required[Annotated[bool, '当前信任状态']]
    capabilities: Required[Annotated[list[str], '支持的接收类型']]
    available: Required[Annotated[bool, '是否可用']]
    reason: Required[Annotated[str, '不可用原因，正常为空']]

class SourceCatalog(TypedDict, total=False):
    current: Required[Annotated[str, '当前响应来源，未选择时为空']]
    items: Required[Annotated[list[Source], '已声明来源']]
    mode: Required[Annotated[str, '响应路由模式']]
    targets: Required[Annotated[list[str], '当前外部响应目标']]
    web_synced: Required[Annotated[bool, '网页是否同步']]
    changed: Annotated[bool, '是否改变了响应源']
    send_result_to_source: Annotated[bool, '当前轮自动投递开关']
    explicit_target: Annotated[str, '当前轮显式投递目标']

from .types import SendResult

R_message_sources: TypeAlias = SourceCatalog
R_message_select_source: TypeAlias = SourceCatalog
R_message_set_source_trust: TypeAlias = SourceCatalog
R_message_send: TypeAlias = SendResult

RESULTS = {'message_sources': R_message_sources, 'message_select_source': R_message_select_source, 'message_set_source_trust': R_message_set_source_trust, 'message_send': R_message_send}
