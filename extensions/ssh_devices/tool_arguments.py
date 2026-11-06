"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_ssh_public_key1 = TypedDict(
    'A_ssh_public_key1',
    {
    },
    total=False,
)

A_ssh_public_key: TypeAlias = Annotated[A_ssh_public_key1, {'additionalProperties': False}]

A_ssh_device2 = TypedDict(
    'A_ssh_device2',
    {
        'action': NotRequired[Annotated[str, {'description': 'list/get/add/update/remove。', 'default': 'list'}]],
        'device': NotRequired[Annotated[str, {'description': 'get/update/remove 的设备 ID 或唯一名字；list/add 留空。', 'default': ''}]],
        'details': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'add 提供 name、description、address、username，可选 port（默认22）；update 只提供要修改的字段，其他动作传空对象。'}] | None, {'default': None, 'description': '设备字段 name、description、address、username、port；端口默认22'}]],
    },
    total=False,
)

A_ssh_device: TypeAlias = Annotated[A_ssh_device2, {'additionalProperties': False}]

A_ssh_session3 = TypedDict(
    'A_ssh_session3',
    {
        'action': NotRequired[Annotated[str, {'description': 'list/open/get/update/connect/disconnect/reset/remove；disconnect 保留记录，remove 删除会话记录，reset 清除终端目录和环境。', 'default': 'list'}]],
        'device': NotRequired[Annotated[str, {'description': 'open 的设备 ID 或名字；list 可按设备筛选；其他动作留空。', 'default': ''}]],
        'session_id': NotRequired[Annotated[str, {'description': 'get/update/connect/disconnect/reset/remove 的会话 ID；open/list 留空。', 'default': ''}]],
        'details': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'open/update 可设置 description（连接用途描述）、timeout（单次操作超时秒数，默认60，0不限）、idle_timeout（空闲断开秒数，默认0不断开）。其他动作传空对象。'}] | None, {'default': None, 'description': '会话字段 description、cwd、connect_timeout、idle_timeout；按会话工具说明使用'}]],
    },
    total=False,
)

A_ssh_session: TypeAlias = Annotated[A_ssh_session3, {'additionalProperties': False}]

A_ssh_terminal4 = TypedDict(
    'A_ssh_terminal4',
    {
        'session_id': Required[Annotated[str, {'description': 'ssh_session 返回的实际会话 ID。'}]],
        'command': Required[Annotated[str, {'description': '要运行的完整命令；Windows 为 PowerShell 语法，Linux/macOS 为 POSIX sh 语法。'}]],
        'timeout': NotRequired[Annotated[int, {'description': '本次命令超时秒数，0 使用会话设置；可通过 ssh_session update 修改会话默认超时。', 'default': 0}]],
    },
    total=False,
)

A_ssh_terminal: TypeAlias = Annotated[A_ssh_terminal4, {'additionalProperties': False}]

A_ssh_parallel5 = TypedDict(
    'A_ssh_parallel5',
    {
        'jobs': Required[Annotated[list[Annotated[object, {'description': '一个列表元素；最多16项，每项必填 command；复用连接填 session_id，新连接填 device（设备ID或名字）并可填 description、timeout、idle_timeout。未给会话超时默认60秒。'}]], {'description': '最多16项，每项必填 command；复用连接填 session_id，新连接填 device（设备ID或名字）并可填 description、timeout、idle_timeout。未给会话超时默认60秒。'}]],
    },
    total=False,
)

A_ssh_parallel: TypeAlias = Annotated[A_ssh_parallel5, {'additionalProperties': False}]

A_ssh_file6 = TypedDict(
    'A_ssh_file6',
    {
        'session_id': Required[Annotated[str, {'description': '已打开 SSH 会话的 ID'}]],
        'action': Required[Annotated[str, {'description': '远端文件操作名称，需符合工具说明的支持动作'}]],
        'path': NotRequired[Annotated[str, {'default': '.', 'description': '远端路径，按会话检测的 Windows/POSIX 规则解释'}]],
        'content': NotRequired[Annotated[str, {'default': '', 'description': 'write 时写入的文本正文'}]],
        'target': NotRequired[Annotated[str, {'default': '', 'description': '远端移动、复制等操作的目标路径'}]],
        'local_path': NotRequired[Annotated[str, {'default': '', 'description': '上传源或下载目标的工作空间相对路径'}]],
    },
    total=False,
)

A_ssh_file: TypeAlias = Annotated[A_ssh_file6, {'additionalProperties': False}]

ARGUMENTS = {'ssh_public_key': A_ssh_public_key, 'ssh_device': A_ssh_device, 'ssh_session': A_ssh_session, 'ssh_terminal': A_ssh_terminal, 'ssh_parallel': A_ssh_parallel, 'ssh_file': A_ssh_file}
