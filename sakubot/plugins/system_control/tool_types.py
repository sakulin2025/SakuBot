"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Operation(TypedDict, total=False):
    operation_id: Annotated[str, '排队管理操作 ID']
    id: Annotated[str, '操作 ID']
    status: Required[Annotated[str, '管理操作状态']]
    execution: Annotated[str, 'after_current_wake 表示本轮结束后执行']
    action: Annotated[str, '管理动作']
    payload: Annotated[DynamicObject, '操作请求']
    result: Annotated[DynamicJSON, '操作的具体结果']
    error: Annotated[str, '失败说明']
Operation: TypeAlias = Annotated[_Operation, {'additionalProperties': True}]

class _Status(TypedDict, total=False):
    version: Required[Annotated[str, '框架版本']]
    boot_id: Required[Annotated[str, '本次启动 ID']]
    uptime_seconds: Required[Annotated[int | float, '运行时长秒']]
    platform: Required[Annotated[str, '运行平台']]
    python: Required[Annotated[str, 'Python 版本']]
    restart_supported: Required[Annotated[bool, '是否支持受监督重启']]
    running: Required[Annotated[DynamicObject | None, '当前运行摘要']]
    error: Required[Annotated[str, '框架错误说明']]
    plugins: Required[Annotated[list[DynamicObject], '插件状态和工具/页面声明']]
    config: Required[Annotated[DynamicObject, '按 Settings 模型生成的公开配置，密钥隐藏']]
    paths: Required[Annotated[dict[str, str], '运行目录路径']]
Status: TypeAlias = Annotated[_Status, {'additionalProperties': True}]

class _Scan(TypedDict, total=False):
    plugins: Required[Annotated[list[DynamicObject], '扫描后的插件目录']]
    added: Required[Annotated[list[str], '新发现插件 ID']]
    removed: Annotated[list[str], '已不存在的插件 ID']
    changed: Annotated[list[str], '发生变化的插件 ID']
Scan: TypeAlias = Annotated[_Scan, {'additionalProperties': True}]

class _Project(TypedDict, total=False):
    id: Annotated[str, '开发项目 ID']
    version: Annotated[str, '项目版本']
    files: Annotated[list[DynamicObject] | list[str], '项目文件列表']
    path: Annotated[str, '文件相对路径']
    content: Annotated[str, '读取的正文']
    file_version: Annotated[str, '文件版本，写入时须原样提供']
    directory: Annotated[str, 'SDK 目录']
    guide: Annotated[str, '开发指南路径']
    build_script: Annotated[str, '构建脚本路径']
    example: Annotated[str, '示例文档路径']
    python_syntax: Annotated[str, '语法检查结果']
    dependencies: Annotated[list[object], '依赖声明']
Project: TypeAlias = Annotated[_Project, {'additionalProperties': True}]

R_system_status: TypeAlias = Status
R_system_plugins: TypeAlias = Operation | Scan | list[DynamicObject]
R_system_config: TypeAlias = Operation | DynamicObject
R_plugin_project: TypeAlias = Operation | Project | list[Project]
R_system_operations: TypeAlias = Operation | list[Operation]
R_system_restart: TypeAlias = Operation

RESULTS = {'system_status': R_system_status, 'system_plugins': R_system_plugins, 'system_config': R_system_config, 'plugin_project': R_plugin_project, 'system_operations': R_system_operations, 'system_restart': R_system_restart}
