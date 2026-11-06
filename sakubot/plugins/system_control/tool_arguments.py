"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_system_status1 = TypedDict(
    'A_system_status1',
    {
    },
    total=False,
)

A_system_status: TypeAlias = Annotated[A_system_status1, {'additionalProperties': False}]

A_system_plugins2 = TypedDict(
    'A_system_plugins2',
    {
        'action': Required[Annotated[Literal['list', 'scan', 'enable', 'disable', 'reload', 'delete', 'import', 'export'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '插件 ID'}]],
        'path': NotRequired[Annotated[str, {'description': '导入 ZIP 的容器内路径'}]],
        'force': NotRequired[Annotated[bool, {'description': '仅在已明确允许中断运行任务时为true；不能当作绕过业务校验的通用开关'}]],
        'purge': NotRequired[Annotated[bool, {'description': '删除时是否同时删除插件配置与业务数据，默认false'}]],
        'confirm': NotRequired[Annotated[bool, {'description': '仅在用户已明确确认本次删除或危险操作时为true'}]],
        'include_data': NotRequired[Annotated[bool, {'description': '导入/导出时是否包含配置和业务数据，默认false'}]],
    },
    total=False,
)

A_system_plugins: TypeAlias = Annotated[A_system_plugins2, {'additionalProperties': False}]

A_system_config3 = TypedDict(
    'A_system_config3',
    {
        'action': Required[Annotated[Literal['read', 'patch'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'values': NotRequired[Annotated[dict[str, object], {'description': '框架配置补丁，严格按 Settings 模型字段；密钥只用于设置，不应对外报告'}]],
    },
    total=False,
)

A_system_config: TypeAlias = Annotated[A_system_config3, {'additionalProperties': False}]

A_plugin_project4 = TypedDict(
    'A_plugin_project4',
    {
        'action': Required[Annotated[Literal['list', 'create', 'checkout', 'inspect', 'read', 'write', 'check', 'build', 'publish', 'versions', 'rollback', 'sdk'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '第三方插件 ID，不能与内置能力重名'}]],
        'label': NotRequired[Annotated[str, {'description': '显示名称或标签'}]],
        'with_page': NotRequired[Annotated[bool, {'description': '创建插件项目时是否包含管理页面'}]],
        'path': NotRequired[Annotated[str, {'description': '项目内相对路径'}]],
        'content': NotRequired[Annotated[str, {'description': '写入开发项目文件的完整 UTF-8 正文'}]],
        'file_version': NotRequired[Annotated[str, {'description': '读取文件时返回的内容版本哈希；修改时必须原样提供'}]],
        'version': NotRequired[Annotated[str, {'description': 'check 返回的项目版本'}]],
        'revision': NotRequired[Annotated[str, {'description': 'versions 返回的历史版本'}]],
        'enable': NotRequired[Annotated[bool, {'description': '发布完成后是否启用插件'}]],
        'force': NotRequired[Annotated[bool, {'description': '仅在已明确允许中断运行任务时为true；不能当作绕过业务校验的通用开关'}]],
    },
    total=False,
)

A_plugin_project: TypeAlias = Annotated[A_plugin_project4, {'additionalProperties': False}]

A_system_operations5 = TypedDict(
    'A_system_operations5',
    {
        'action': Required[Annotated[Literal['list', 'get', 'cancel'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '持久系统操作 ID，使用提交操作返回的 operation_id'}]],
    },
    total=False,
)

A_system_operations: TypeAlias = Annotated[A_system_operations5, {'additionalProperties': False}]

A_system_restart6 = TypedDict(
    'A_system_restart6',
    {
        'reason': Required[Annotated[str, {'description': '本次受监督重启的原因'}]],
        'progress': NotRequired[Annotated[str, {'description': '已完成动作、结果未知的动作、待处理事项'}]],
        'resume': NotRequired[Annotated[str, {'description': '重启后继续的明确目标；留空不唤醒'}]],
        'send_result_to_source': NotRequired[Annotated[bool, {'description': '是否把本次唤醒结果或通知投递到当前主会话源；网页始终同步'}]],
    },
    total=False,
)

A_system_restart: TypeAlias = Annotated[A_system_restart6, {'additionalProperties': False}]

ARGUMENTS = {'system_status': A_system_status, 'system_plugins': A_system_plugins, 'system_config': A_system_config, 'plugin_project': A_plugin_project, 'system_operations': A_system_operations, 'system_restart': A_system_restart}
