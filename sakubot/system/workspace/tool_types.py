"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Entry(TypedDict, total=False):
    name: Required[Annotated[str, '文件或目录名']]
    path: Required[Annotated[str, '工作空间相对路径']]
    type: Required[Annotated[str, '条目类型 file 或 directory 等实际分类']]
    size: Required[Annotated[int, '文件或目录的文件系统大小，字节；目录值由文件系统决定']]
    version: Required[Annotated[str, '条目版本，修改/移动/删除时使用']]
    modified: Annotated[float, '修改时间，Unix 秒']
    mtime: Annotated[float, '修改时间，Unix 秒']

class Listing(TypedDict, total=False):
    path: Required[Annotated[str, '所列目录相对路径']]
    version: Required[Annotated[str, '当前目录自身的版本']]
    items: Required[Annotated[list[Entry], '本页子条目']]
    total: Required[Annotated[int, '匹配条目总数']]
    offset: Annotated[int, '从0开始的偏移']
    has_more: Required[Annotated[bool, '是否还有条目']]

class TextPage(TypedDict, total=False):
    path: Annotated[str, '工作空间相对路径']
    version: Required[Annotated[str, '读取时文件版本']]
    size: Required[Annotated[int, '原文件字节数']]
    binary: Required[Annotated[bool, '是否为二进制文件']]
    content: Required[Annotated[str, '该页原始正文；二进制时为空']]
    numbered_content: Annotated[str, '带1起始行号的正文']
    offset: Annotated[int, '0起始行偏移']
    next_offset: Annotated[int, '下一页偏移']
    total_lines: Annotated[int, '总行数']
    has_more: Required[Annotated[bool, '是否还有正文']]

class _Edited(TypedDict, total=False):
    name: Annotated[str, '文件名']
    path: Required[Annotated[str, '修改后的相对路径']]
    type: Annotated[str, '条目类型']
    size: Annotated[int, '字节数']
    version: Required[Annotated[str, '新版本']]
    modified: Annotated[float, '修改时间，Unix 秒']
    rebased: Annotated[bool, '是否在版本漂移后成功重新定位']
    hunks: Annotated[int, '应用的修改块数']
Edited: TypeAlias = Annotated[_Edited, {'additionalProperties': True}]

class Removed(TypedDict, total=False):
    removed: Required[Annotated[str, '已删除的相对路径']]

class _ShellResult(TypedDict, total=False):
    exit_code: Required[Annotated[int | None, '退出码；未正常退出时可能为空']]
    timed_out: Required[Annotated[bool, '是否超时']]
    output: Required[Annotated[str, '合并标准输出和错误输出']]
    output_bytes: Required[Annotated[int, '实际读取的输出字节数']]
    truncated: Required[Annotated[bool, '输出是否截断']]
    duration_ms: Required[Annotated[int, '执行耗时，毫秒']]
    cwd: Annotated[str, '命令执行目录']
ShellResult: TypeAlias = Annotated[_ShellResult, {'additionalProperties': True}]

class _ShellJob(TypedDict, total=False):
    id: Required[Annotated[str, '后台任务 ID']]
    command: Required[Annotated[str, '实际命令']]
    cwd: Required[Annotated[str, '执行目录']]
    description: Required[Annotated[str, '任务用途']]
    timeout: Required[Annotated[int, '超时秒数']]
    status: Required[Annotated[str, 'running/completed/failed/timed_out/cancelled/interrupted']]
    started_at: Required[Annotated[float, '启动时间，Unix 秒']]
    finished_at: Required[Annotated[float | None, '结束时间，Unix 秒；运行中为空']]
    output: Annotated[str, '已保留的输出；列表中可省略']
    output_bytes: Required[Annotated[int, '已读取字节数']]
    truncated: Required[Annotated[bool, '输出是否截断']]
    exit_code: Required[Annotated[int | None, '退出码，未结束可能为空']]
    timed_out: Required[Annotated[bool, '是否超时']]
    completion: Annotated[DynamicObject | None, '可选完成通知的原始关联信息']
    notified: Annotated[bool, '是否已提交完成通知']
ShellJob: TypeAlias = Annotated[_ShellJob, {'additionalProperties': True}]

class JobList(TypedDict, total=False):
    items: Required[Annotated[list[ShellJob], '后台任务列表，最新在前']]

class Published(TypedDict, total=False):
    url: Required[Annotated[str, '附件地址']]
    name: Required[Annotated[str, '显示文件名']]
    mime: Required[Annotated[str, 'MIME 类型']]
    expires: Required[Annotated[float, '附件过期 Unix 秒']]
    kind: Required[Annotated[str, '发送内容类型']]
    sent: Required[Annotated[bool, '是否提交发送']]

R_workspace_list: TypeAlias = Listing
R_workspace_read: TypeAlias = TextPage
R_workspace_write: TypeAlias = Entry
R_workspace_edit: TypeAlias = Edited
R_workspace_patch: TypeAlias = Edited
R_workspace_mkdir: TypeAlias = Entry
R_workspace_move: TypeAlias = Entry
R_workspace_remove: TypeAlias = Removed
R_workspace_shell: TypeAlias = ShellResult
R_workspace_shell_start: TypeAlias = ShellJob
R_workspace_shell_status: TypeAlias = ShellJob
R_workspace_shell_stop: TypeAlias = ShellJob
R_workspace_shell_list: TypeAlias = JobList
R_workspace_publish: TypeAlias = Published

RESULTS = {'workspace_list': R_workspace_list, 'workspace_read': R_workspace_read, 'workspace_write': R_workspace_write, 'workspace_edit': R_workspace_edit, 'workspace_patch': R_workspace_patch, 'workspace_mkdir': R_workspace_mkdir, 'workspace_move': R_workspace_move, 'workspace_remove': R_workspace_remove, 'workspace_shell': R_workspace_shell, 'workspace_shell_start': R_workspace_shell_start, 'workspace_shell_status': R_workspace_shell_status, 'workspace_shell_stop': R_workspace_shell_stop, 'workspace_shell_list': R_workspace_shell_list, 'workspace_publish': R_workspace_publish}
