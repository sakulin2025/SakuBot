"""HA success contracts: required keys and nullable values are distinct.

Transport/validation failures raise exceptions and never masquerade as strings.
"""
from typing import Annotated, Literal, NotRequired, TypedDict, TypeAlias
from sakubot.contracts.common import DynamicObject, DynamicJSON


class EntityIdentity(TypedDict):
    entity_id: Annotated[str, '完整 HA 实体 ID，始终存在']
    name: Annotated[str, '配置名称，缺失时使用 HA 友好名称或实体 ID']
    friendly_name: Annotated[str, 'HA 友好名称，缺失时使用 name']
    display_name: Annotated[str, '优先本地别名的显示名称']
    domain: Annotated[str, '实际实体域，例如 switch/light/sensor']
    area: Annotated[str, '房间标识，未设置为空字符串']
    alias: Annotated[str, '本地别名，未设置为空字符串']
    group: Annotated[str, '逻辑分组，未设置为空字符串']
    policy: Annotated[str | None, '实体策略；键存在，未配置时值为 null']


class QueryEntity(EntityIdentity):
    state: Annotated[str | None, '实时原始状态；键始终存在，HA 未提供值时为 null']
    state_text: Annotated[str | None, '状态显示文本；键始终存在，未知值沿用原状态']
    attributes: NotRequired[Annotated[DynamicObject, '仅 summary=false 时返回的 HA 动态属性，键由实体能力决定']]


class QueryResult(TypedDict):
    entities: Annotated[list[QueryEntity], '查询成功始终返回的实体列表；无匹配为 []']
    total: Annotated[int, '截断前匹配实体总数']
    truncated: Annotated[bool, 'entities 是否因100项上限截断']
    domains: NotRequired[Annotated[dict[str, int], '仅 summary=true 时返回的域名到实体数量映射']]
    related_entities: NotRequired[Annotated[list[QueryEntity], '按 light 查询时额外发现的照明用途 switch/input_boolean']]
    related_total: NotRequired[Annotated[int, '存在 related_entities 时的未截断相关实体总数']]
    related_truncated: NotRequired[Annotated[bool, '相关实体列表是否截断']]
    note: NotRequired[Annotated[str, '类型/用途匹配提示；仅适用时返回']]


class HistoryState(TypedDict):
    state: Annotated[str | None, '该条历史的原始状态；键始终存在，缺失值为 null']
    last_changed: Annotated[str | None, '状态最后变化时间，含时区 ISO8601，HA 未提供则为 null']
    last_updated: Annotated[str | None, '最后更新时间，含时区 ISO8601，HA 未提供则为 null']
    attributes: Annotated[DynamicObject, '本条历史保留的状态属性，未提供为 {}']


class History(TypedDict):
    entity: Annotated[EntityIdentity, '实体身份及名称，不包含实时状态']
    start: Annotated[str, '含时区 ISO8601 起始时间']
    end: Annotated[str, '含时区 ISO8601 结束时间']
    records: Annotated[list[HistoryState], '当前页历史状态；无记录为 []']
    total: Annotated[int, '历史记录总数']
    offset: Annotated[int, '当前分页偏移']
    truncated: Annotated[bool, '是否仍有后续历史记录']
    next_offset: Annotated[int | None, '下一页偏移；键始终存在，无后续为 null']
    note: Annotated[str, '历史保留和初始状态的解释']


class Plan(TypedDict):
    domain: Annotated[str, 'HA 服务所属域']
    service: Annotated[str, '服务名称']
    data: Annotated[DynamicObject, '按所选服务定义的请求体']


class ActionResult(Plan):
    success: Annotated[bool, '此项服务是否成功']
    device: Annotated[EntityIdentity, '本项控制实体的身份和名称']
    error: NotRequired[Annotated[str, '本项服务失败时的原因；失败后不自动重试']]


class PreviewControl(TypedDict):
    preview: Annotated[Literal[True], '仅预览，不执行设备操作']
    plans: Annotated[list[Plan], '准备执行的服务计划']


class ExecutedControl(TypedDict):
    success: Annotated[bool, '所有服务是否成功；部分失败仍保留逐项执行结果']
    results: Annotated[list[ActionResult], '依实际执行顺序返回各项结果，不自动重放失败项']


Control: TypeAlias = PreviewControl | ExecutedControl
Entity: TypeAlias = EntityIdentity


class Manual(TypedDict):
    title: Annotated[str, '手册标题']
    content: Annotated[str, '手册正文']
    shared_across_sessions: Annotated[bool, '跨会话共享标志']
    saved: NotRequired[Annotated[bool, '写入操作返回的保存标志']]
    device_operations: NotRequired[Annotated[int, '写入手册实际控制设备次数，始终为0']]


class ApiResult(TypedDict):
    ok: Annotated[bool, 'HTTP 状态是否为2xx；非2xx仍返回此固定结果封装']
    status: Annotated[int, 'HTTP 状态码']
    content_type: Annotated[str, '响应 MIME 类型']
    data: Annotated[DynamicJSON, '所选 REST 端点的实际响应，字段按该端点文档解释']
    truncated: NotRequired[Annotated[bool, '文本响应是否截断']]
    error: NotRequired[Annotated[str, 'HTTP 错误提示；例如认证失败']]


class InitializationStatus(TypedDict):
    initialized: Annotated[bool, '是否已发布初始化配置']
    has_draft: Annotated[bool, '是否有未发布草稿']
    status: Annotated[str, '初始化状态说明']
    built_at: Annotated[str, '发布时间，尚未发布为空']
    rooms: Annotated[list[DynamicObject], '当前已发布房间配置']
    entities: Annotated[list[DynamicObject], '当前已发布实体配置']


class InitializationProgress(TypedDict):
    message: Annotated[str, '本次向导操作结果说明']
    rooms: NotRequired[Annotated[list[DynamicObject], '该操作返回的房间草稿']]
    entity_count: NotRequired[Annotated[int, '扫描发现的实体数量']]


Initialization: TypeAlias = InitializationStatus | InitializationProgress
R_ha_initialize: TypeAlias = Initialization | list[DynamicObject]
R_ha_query: TypeAlias = QueryResult
R_ha_history: TypeAlias = History
R_ha_control: TypeAlias = Control
R_ha_manual: TypeAlias = Manual
R_ha_api: TypeAlias = ApiResult
RESULTS = {'ha_initialize': R_ha_initialize, 'ha_query': R_ha_query, 'ha_history': R_ha_history,
           'ha_control': R_ha_control, 'ha_manual': R_ha_manual, 'ha_api': R_ha_api}
