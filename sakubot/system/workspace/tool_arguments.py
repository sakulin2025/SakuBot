"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_workspace_shell1 = TypedDict(
    'A_workspace_shell1',
    {
        'command': Required[Annotated[str, {'description': '要交给 /bin/sh 执行的完整命令'}]],
        'cwd': NotRequired[Annotated[str, {'description': '相对工作空间的初始目录，默认根目录'}]],
        'timeout': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 600, 'description': '前台 Shell 命令超时秒数，默认60，最大600'}]],
    },
    total=False,
)

A_workspace_shell: TypeAlias = Annotated[A_workspace_shell1, {'additionalProperties': False}]

A_workspace_shell_start2 = TypedDict(
    'A_workspace_shell_start2',
    {
        'command': Required[Annotated[str, {'description': '完整 /bin/sh 命令'}]],
        'cwd': NotRequired[Annotated[str, {'description': '相对工作空间目录'}]],
        'description': NotRequired[Annotated[str, {'description': '任务用途'}]],
        'notify': NotRequired[Annotated[bool, {'default': True, 'description': '结束后唤醒主 Agent，默认开启'}]],
        'timeout': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 604800, 'description': '后台 Shell 任务超时秒数，默认3600，最大604800（7天）'}]],
    },
    total=False,
)

A_workspace_shell_start: TypeAlias = Annotated[A_workspace_shell_start2, {'additionalProperties': False}]

A_workspace_shell_status3 = TypedDict(
    'A_workspace_shell_status3',
    {
        'id': Required[Annotated[str, {'description': '后台任务 id'}]],
        'wait_seconds': NotRequired[Annotated[int, {'minimum': 0, 'maximum': 30, 'description': '等待任务结束的最长秒数，0立即返回，最大30'}]],
    },
    total=False,
)

A_workspace_shell_status: TypeAlias = Annotated[A_workspace_shell_status3, {'additionalProperties': False}]

A_workspace_shell_list4 = TypedDict(
    'A_workspace_shell_list4',
    {
    },
    total=False,
)

A_workspace_shell_list: TypeAlias = Annotated[A_workspace_shell_list4, {'additionalProperties': False}]

A_workspace_shell_stop5 = TypedDict(
    'A_workspace_shell_stop5',
    {
        'id': Required[Annotated[str, {'description': '后台任务 id'}]],
    },
    total=False,
)

A_workspace_shell_stop: TypeAlias = Annotated[A_workspace_shell_stop5, {'additionalProperties': False}]

A_workspace_publish6 = TypedDict(
    'A_workspace_publish6',
    {
        'path': Required[Annotated[str, {'description': '工作空间相对文件路径'}]],
        'kind': NotRequired[Annotated[Literal['auto', 'image', 'video', 'audio', 'file'], {'description': '消息内容类型；auto 按文件扩展名识别'}]],
        'name': NotRequired[Annotated[str, {'description': '可选显示文件名'}]],
        'send': NotRequired[Annotated[bool, {'default': True, 'description': '是否将附件作为主对话消息提交；false 只发布并返回附件信息'}]],
    },
    total=False,
)

A_workspace_publish: TypeAlias = Annotated[A_workspace_publish6, {'additionalProperties': False}]

A_workspace_list7 = TypedDict(
    'A_workspace_list7',
    {
        'path': NotRequired[Annotated[str, {'description': '相对目录，默认根目录'}]],
        'offset': NotRequired[Annotated[int, {'minimum': 0, 'description': '从0开始的分页偏移；按同一工具返回的下一页偏移继续'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 200, 'description': '本页目录条目数，默认100，范围1至200'}]],
        'query': NotRequired[Annotated[str, {'description': '文件名的大小写不敏感包含匹配；留空列全部'}]],
    },
    total=False,
)

A_workspace_list: TypeAlias = Annotated[A_workspace_list7, {'additionalProperties': False}]

A_workspace_read8 = TypedDict(
    'A_workspace_read8',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
        'offset': NotRequired[Annotated[int, {'minimum': 0, 'description': '从0开始的行偏移'}]],
        'limit': NotRequired[Annotated[int, {'minimum': 1, 'maximum': 500, 'description': '本次读取的最大行数，默认200，范围1至500'}]],
    },
    total=False,
)

A_workspace_read: TypeAlias = Annotated[A_workspace_read8, {'additionalProperties': False}]

A_workspace_write9 = TypedDict(
    'A_workspace_write9',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
        'content': Required[Annotated[str, {'description': '完整正文'}]],
        'version': NotRequired[Annotated[str, {'description': '可选读取版本；新文件省略'}]],
        'base_content': NotRequired[Annotated[str, {'description': '可选读取时的完整原文；提供时按内容而非版本判断覆盖冲突'}]],
    },
    total=False,
)

A_workspace_write: TypeAlias = Annotated[A_workspace_write9, {'additionalProperties': False}]

A_workspace_edit10 = TypedDict(
    'A_workspace_edit10',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
        'old': Required[Annotated[str, {'description': '唯一匹配的原文，包含必要上下文，不带行号前缀'}]],
        'new': Required[Annotated[str, {'description': '替换正文'}]],
        'version': NotRequired[Annotated[str, {'description': '可选，仅用于报告是否已基于新版本修改'}]],
    },
    total=False,
)

A_workspace_edit: TypeAlias = Annotated[A_workspace_edit10, {'additionalProperties': False}]

A_workspace_patch_hunksItem12 = TypedDict(
    'A_workspace_patch_hunksItem12',
    {
        'start_line': Required[Annotated[int, {'minimum': 1, 'description': '读取时的起始行号，漂移后按 old 唯一匹配重新定位'}]],
        'old': Required[Annotated[str, {'description': '含上下文的非空原文，不带行号前缀'}]],
        'new': Required[Annotated[str, {'description': '替换正文，空字符串表示删除'}]],
    },
    total=False,
)

A_workspace_patch11 = TypedDict(
    'A_workspace_patch11',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
        'version': NotRequired[Annotated[str, {'description': '可选，仅报告版本漂移'}]],
        'hunks': Required[Annotated[list[Annotated[A_workspace_patch_hunksItem12, {'description': '一个列表元素；修改块列表；每项包含读取时的1起始行号 start_line、含上下文的唯一原文 old 和替换正文 new', 'additionalProperties': False}]], {'minItems': 1, 'maxItems': 100, 'description': '修改块列表；每项包含读取时的1起始行号 start_line、含上下文的唯一原文 old 和替换正文 new'}]],
    },
    total=False,
)

A_workspace_patch: TypeAlias = Annotated[A_workspace_patch11, {'additionalProperties': False}]

A_workspace_mkdir13 = TypedDict(
    'A_workspace_mkdir13',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
    },
    total=False,
)

A_workspace_mkdir: TypeAlias = Annotated[A_workspace_mkdir13, {'additionalProperties': False}]

A_workspace_move14 = TypedDict(
    'A_workspace_move14',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
        'destination': Required[Annotated[str, {'description': '目标工作空间相对路径；不能覆盖已存在的目标'}]],
        'version': Required[Annotated[str, {'description': '源文件或源目录的最新版本，先读取或列目录获取'}]],
    },
    total=False,
)

A_workspace_move: TypeAlias = Annotated[A_workspace_move14, {'additionalProperties': False}]

A_workspace_remove15 = TypedDict(
    'A_workspace_remove15',
    {
        'path': Required[Annotated[str, {'description': '相对于共享工作空间的路径，不是宿主机任意路径'}]],
        'version': Required[Annotated[str, {'description': '目标文件或目录的最新版本，先读取或列目录获取'}]],
        'recursive': NotRequired[Annotated[bool, {'description': 'true 允许递归删除非空目录；默认false只删除文件或空目录'}]],
    },
    total=False,
)

A_workspace_remove: TypeAlias = Annotated[A_workspace_remove15, {'additionalProperties': False}]

ARGUMENTS = {'workspace_shell': A_workspace_shell, 'workspace_shell_start': A_workspace_shell_start, 'workspace_shell_status': A_workspace_shell_status, 'workspace_shell_list': A_workspace_shell_list, 'workspace_shell_stop': A_workspace_shell_stop, 'workspace_publish': A_workspace_publish, 'workspace_list': A_workspace_list, 'workspace_read': A_workspace_read, 'workspace_write': A_workspace_write, 'workspace_edit': A_workspace_edit, 'workspace_patch': A_workspace_patch, 'workspace_mkdir': A_workspace_mkdir, 'workspace_move': A_workspace_move, 'workspace_remove': A_workspace_remove}
