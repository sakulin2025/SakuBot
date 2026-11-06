"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_script_manage1 = TypedDict(
    'A_script_manage1',
    {
        'action': Required[Annotated[Literal['list', 'get', 'check', 'save', 'delete', 'revisions'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '脚本 ID；新建可省略由框架分配'}]],
        'version': NotRequired[Annotated[str, {'description': 'get 时可选的历史版本哈希'}]],
        'name': NotRequired[Annotated[str, {'description': '脚本名称，1至100字'}]],
        'description': NotRequired[Annotated[str, {'description': '脚本用途，最多4000字'}]],
        'code': NotRequired[Annotated[str, {'description': '完整 Python 源代码，不是文件路径'}]],
        'parameters': NotRequired[Annotated[dict[str, object], {'description': '脚本参数的 JSON Schema，根节点为 object；动态字段由该脚本定义'}]],
        'expected_version': NotRequired[Annotated[str, {'description': '修改前读取的当前版本；版本不一致时拒绝覆盖'}]],
        'event_sources': NotRequired[Annotated[list[Annotated[str, {'description': '事件 ID 或泛 ID，决定 ctx.event["data"] 的类型'}]], {'description': '脚本接受的事件 ID 或泛事件模式；决定 ctx.event["data"] 的类型'}]],
        'tool_plugins': NotRequired[Annotated[list[Annotated[str, {'description': '需要的工具插件 ID；省略时包含全部可用脚本工具'}]], {'description': '生成 SDK 时包含的工具插件 ID 列表；省略包含全部可用工具'}]],
        'hard': NotRequired[Annotated[bool, {'default': False, 'description': '仅在明确理解诊断后强制保存类型错误或警告；不能绕过语法错误或检查器故障'}]],
        'hard_reason': NotRequired[Annotated[str, {'description': '强制保存诊断的明确原因'}]],
        'timeout': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 86400, 'description': '执行超时秒数；允许范围见类型约束'}]],
        'enabled': NotRequired[Annotated[bool, {'description': '是否启用本对象，true 启用，false 停用'}]],
        'concurrency': NotRequired[Annotated[Literal['queue', 'merge', 'skip'], {'description': '脚本忙碌时的新触发策略：merge 合并待执行事件，queue 排队，skip 忽略'}]],
        'on_failure': NotRequired[Annotated[Literal['none', 'wake', 'notify'], {'description': '失败处理：none 仅记日志，wake 唤醒主智能体，notify 直接通知'}]],
        'failure_threshold': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'description': '触发失败策略前需要连续失败的次数'}]],
        'cooldown_seconds': NotRequired[Annotated[int, {'minimum': 30, 'description': '重复失败通知的冷却秒数'}]],
        'send_result_to_source': NotRequired[Annotated[bool, {'description': '是否把本次唤醒结果或通知投递到当前主会话源；网页始终同步'}]],
        'confirm': NotRequired[Annotated[bool, {'description': '仅在用户已明确确认本次删除或危险操作时为true'}]],
    },
    total=False,
)

A_script_manage: TypeAlias = Annotated[A_script_manage1, {'additionalProperties': False}]

A_script_development2 = TypedDict(
    'A_script_development2',
    {
        'id': NotRequired[Annotated[str, {'description': '可选已存在的脚本 ID'}]],
        'sources': NotRequired[Annotated[list[Annotated[str, {'description': '完整或泛事件来源 ID'}]], {'description': '需要生成类型的完整事件 ID 或泛事件模式'}]],
        'parameters': NotRequired[Annotated[dict[str, object], {'description': '脚本参数的 JSON Schema，根节点为 object；动态字段由该脚本定义'}]],
        'tool_plugins': NotRequired[Annotated[list[Annotated[str, {'description': '需要的工具插件 ID'}]], {'description': '生成 SDK 时包含的工具插件 ID 列表；省略包含全部可用工具'}]],
        'offset': NotRequired[Annotated[int, {'minimum': 0, 'description': 'SDK 文本字符偏移，首次0；下一页使用 next_offset'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1000, 'maximum': 12000, 'description': '本页 SDK 字符数，1000至12000，默认10000'}]],
        'sdk_hash': NotRequired[Annotated[str, {'description': '翻页时提供上一页哈希，防止定义变动'}]],
    },
    total=False,
)

A_script_development: TypeAlias = Annotated[A_script_development2, {'additionalProperties': False}]

A_script_run_event4 = TypedDict(
    'A_script_run_event4',
    {
        'id': Required[Annotated[str, {'description': '生产者去重 ID'}]],
        'source': Required[Annotated[str, {'description': '实际完整事件 ID，不含星号'}]],
        'at': Required[Annotated[float, {'description': '事件分发 Unix 秒'}]],
        'data': Required[Annotated[dict[str, object], {'description': '业务数据，须符合选定脚本的事件类型'}]],
    },
    total=False,
)

A_script_run3 = TypedDict(
    'A_script_run3',
    {
        'id': Required[Annotated[str, {'description': '脚本 ID'}]],
        'params': NotRequired[Annotated[dict[str, object], {'description': '该动作所需的参数对象；具体键和值依动作定义，不猜测字段'}]],
        'event': NotRequired[Annotated[A_script_run_event4, {'description': '可选完整事件样本 {id,source,at,data}；事件脚本手动运行时必须提供匹配数据', 'additionalProperties': False}]],
    },
    total=False,
)

A_script_run: TypeAlias = Annotated[A_script_run3, {'additionalProperties': False}]

A_script_execution5 = TypedDict(
    'A_script_execution5',
    {
        'action': Required[Annotated[Literal['list', 'get', 'stop'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '执行 ID'}]],
        'script_id': NotRequired[Annotated[str, {'description': 'list 时按脚本 ID 筛选；留空不限'}]],
    },
    total=False,
)

A_script_execution: TypeAlias = Annotated[A_script_execution5, {'additionalProperties': False}]

A_script_binding6 = TypedDict(
    'A_script_binding6',
    {
        'action': Required[Annotated[Literal['sources', 'options', 'list', 'save', 'delete'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '已有绑定 ID；新建省略'}]],
        'source': NotRequired[Annotated[str, {'description': '插件声明的完整或泛事件 ID，也允许尚未声明的软来源'}]],
        'target_kind': NotRequired[Annotated[Literal['script', 'wake'], {'description': '动作类型：wake 直接唤醒主智能体，script 执行脚本'}]],
        'prompt': NotRequired[Annotated[str, {'description': '唤醒主智能体的提示词'}]],
        'script_id': NotRequired[Annotated[str, {'description': '已保存脚本的唯一 ID，先查询脚本列表'}]],
        'name': NotRequired[Annotated[str, {'description': '绑定显示名称'}]],
        'source_params': NotRequired[Annotated[dict[str, object], {'description': '事件筛选参数，严格按所选来源的参数定义提供，不是脚本执行参数'}]],
        'params': NotRequired[Annotated[dict[str, object], {'description': '该动作所需的参数对象；具体键和值依动作定义，不猜测字段'}]],
        'enabled': NotRequired[Annotated[bool, {'description': '是否启用本对象，true 启用，false 停用'}]],
        'on_failure': NotRequired[Annotated[Literal['none', 'wake', 'notify'], {'description': '失败处理：none 仅记日志，wake 唤醒主智能体，notify 直接通知'}]],
        'failure_threshold': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 100, 'description': '触发失败策略前需要连续失败的次数'}]],
        'cooldown_seconds': NotRequired[Annotated[int, {'minimum': 30, 'description': '重复失败通知的冷却秒数'}]],
        'send_result_to_source': NotRequired[Annotated[bool, {'description': '是否把本次唤醒结果或通知投递到当前主会话源；网页始终同步'}]],
        'confirm': NotRequired[Annotated[bool, {'description': '仅在用户已明确确认本次删除或危险操作时为true'}]],
    },
    total=False,
)

A_script_binding: TypeAlias = Annotated[A_script_binding6, {'additionalProperties': False}]

A_script_tools7 = TypedDict(
    'A_script_tools7',
    {
        'plugin': NotRequired[Annotated[str, {'description': '可选插件 ID，只列该插件的工具'}]],
        'query': NotRequired[Annotated[str, {'description': '工具名或描述的关键词'}]],
    },
    total=False,
)

A_script_tools: TypeAlias = Annotated[A_script_tools7, {'additionalProperties': False}]

ARGUMENTS = {'script_manage': A_script_manage, 'script_development': A_script_development, 'script_run': A_script_run, 'script_execution': A_script_execution, 'script_binding': A_script_binding, 'script_tools': A_script_tools}
