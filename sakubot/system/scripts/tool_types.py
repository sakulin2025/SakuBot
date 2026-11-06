"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Diagnostic(TypedDict, total=False):
    severity: Required[Annotated[str, 'error/warning/information']]
    message: Required[Annotated[str, '具体诊断']]
    line: Required[Annotated[int, '1起始行号']]
    column: Required[Annotated[int, '1起始列号']]
    rule: Required[Annotated[str, '检查规则']]

class _CheckReport(TypedDict, total=False):
    ok: Annotated[bool, '是否无错误警告']
    syntax_ok: Annotated[bool, '语法及入口是否有效']
    checker_available: Annotated[bool, '类型检查器是否完成']
    diagnostics: Required[Annotated[list[Diagnostic], '诊断列表']]
    diagnostic_count: Annotated[int, '全部诊断数']
    saved: Annotated[bool, '是否已保存，false不能视为成功']
    can_force: Annotated[bool, '是否可仅绕过类型诊断']
    error: Annotated[str, '保存失败说明']
    sdk_hash: Annotated[str, 'SDK 内容哈希']
    checker: Annotated[str, '检查器名称']
CheckReport: TypeAlias = Annotated[_CheckReport, {'additionalProperties': True}]

class _Script(TypedDict, total=False):
    id: Required[Annotated[str, '脚本 ID']]
    name: Required[Annotated[str, '名称']]
    version: Required[Annotated[str, '不可变代码版本']]
    parameters: Required[Annotated[DynamicObject, '脚本参数 JSON Schema']]
    description: Annotated[str, '用途']
    code: Annotated[str, 'get 时返回的 Python 源码']
    event_sources: Annotated[list[str], '接受的事件 ID/模式']
    tool_plugins: Annotated[list[str] | None, '类型化工具选择']
    validation: Annotated[DynamicObject, '检查诊断、是否强制和原因']
    sdk_hash: Annotated[str, '该版本 SDK 哈希']
    enabled: Annotated[bool, '是否接受新触发']
    saved: Annotated[bool, '保存成功标志']
    timeout: Annotated[int, '执行超时秒']
    concurrency: Annotated[str, 'merge/queue/skip']
Script: TypeAlias = Annotated[_Script, {'additionalProperties': True}]

class Revision(TypedDict, total=False):
    version: Required[Annotated[str, '历史版本哈希']]
    at: Required[Annotated[float, '版本文件修改 Unix 秒']]

class _Deleted(TypedDict, total=False):
    deleted: Annotated[str, '删除的脚本/绑定 ID']
    removed: Annotated[str, '已移除 ID']
Deleted: TypeAlias = Annotated[_Deleted, {'additionalProperties': True}]

class _Run(TypedDict, total=False):
    id: Annotated[str, '执行 ID，skipped/disabled 时可能不返回']
    status: Annotated[str, 'queued/running/done/failed/skipped 等执行状态']
    active_id: Annotated[str, 'skip 模式下占用中的执行 ID']
    script_id: Annotated[str, '脚本 ID']
    binding_id: Annotated[str, '绑定 ID']
    version: Annotated[str, '执行版本']
    queued: Annotated[float, '排队 Unix 秒']
    started: Annotated[float | None, '开始 Unix 秒']
    finished: Annotated[float | None, '完成 Unix 秒']
    input: Annotated[DynamicObject | str, '执行输入，详情接口可能已解析 JSON']
    output: Annotated[DynamicJSON, '脚本返回结果，内容由脚本决定']
    error: Annotated[str, '错误说明']
    logs: Annotated[str | list[object], '执行日志']
    duplicate: Annotated[bool, '是否复用了去重执行']
    tools: Annotated[list[DynamicObject], '执行时的工具调用资料']
Run: TypeAlias = Annotated[_Run, {'additionalProperties': True}]

class _Binding(TypedDict, total=False):
    id: Required[Annotated[str, '绑定 ID']]
    source: Required[Annotated[str, '事件完整 ID 或模式']]
    name: Annotated[str, '绑定名称']
    target_kind: Annotated[str, 'wake 或 script']
    script_id: Annotated[str, '脚本 ID']
    source_params: Annotated[DynamicObject, '事件筛选参数']
    params: Annotated[DynamicObject, '脚本参数']
    prompt: Annotated[str, '直接唤醒提示词']
    enabled: Annotated[bool, '是否启用']
    available: Annotated[bool, '当前是否可运行']
    reason: Annotated[str, '不可用原因']
Binding: TypeAlias = Annotated[_Binding, {'additionalProperties': True}]

class Source(TypedDict, total=False):
    id: Required[Annotated[str, '声明的完整或泛来源 ID']]
    plugin_id: Required[Annotated[str, '声明插件 ID']]
    name: Required[Annotated[str, '事件名称']]
    parameters: Required[Annotated[DynamicObject, '筛选参数 Schema']]
    event_schema: Required[Annotated[DynamicObject, '类型化事件数据 Schema，包含字段说明和样本']]
    id_description: Required[Annotated[str, '具名/泛 ID 的规则']]
    available: Required[Annotated[bool, '插件是否可用']]

class Option(TypedDict, total=False):
    value: Required[Annotated[str | int, '可选项的实际值']]
    label: Required[Annotated[str, '显示名称']]

class Development(TypedDict, total=False):
    sdk: Required[Annotated[str, '当前页的 Python SDK 文本']]
    sdk_hash: Required[Annotated[str, '整份 SDK 哈希']]
    total: Required[Annotated[int, 'SDK 总字符数']]
    next_offset: Required[Annotated[int | None, '下一页字符偏移，空表示结束']]
    sources: Required[Annotated[list[str], '选定来源']]
    unknown_sources: Required[Annotated[list[str], '未声明的来源']]
    unknown_results: Required[Annotated[list[str], '尚未定义返回结构的工具']]
    example: Required[Annotated[str, '类型化 main 模板']]
    conventions: Required[Annotated[dict[str, str], '实例/字典访问约定']]

class ToolDescription(TypedDict, total=False):
    plugin: Required[Annotated[str, '插件 ID']]
    name: Required[Annotated[str, '工具名']]
    description: Required[Annotated[str, '工具说明']]
    parameters: Required[Annotated[DynamicObject, '参数 JSON Schema']]
    result_schema: Required[Annotated[DynamicObject | None, '返回类型 Schema；null 表示未声明']]
    result_typed: Required[Annotated[bool, '是否有返回类型']]
    result_contract_kind: Annotated[str, 'fixed 固定结构、mixed 固定与动态联合、dynamic 原生动态数据、missing 未声明']

R_script_manage: TypeAlias = Script | list[Script] | CheckReport | list[Revision] | Deleted
R_script_development: TypeAlias = Development
R_script_run: TypeAlias = Run
R_script_execution: TypeAlias = Run | list[Run]
R_script_binding: TypeAlias = Binding | list[Binding] | list[Source] | dict[str, list[Option]] | Deleted
R_script_tools: TypeAlias = list[ToolDescription]

RESULTS = {'script_manage': R_script_manage, 'script_development': R_script_development, 'script_run': R_script_run, 'script_execution': R_script_execution, 'script_binding': R_script_binding, 'script_tools': R_script_tools}
