"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class PublicKey(TypedDict, total=False):
    public_key: Required[Annotated[str, 'OpenSSH 公钥，非私钥']]
    fingerprint: Required[Annotated[str, '公钥指纹']]
    trust_command: Required[Annotated[str, '用户可选的授权命令']]
    next: Required[Annotated[str, '后续配置步骤']]

class _Device(TypedDict, total=False):
    id: Annotated[str, '设备 ID']
    name: Annotated[str, '名称']
    description: Annotated[str, '用途描述']
    address: Annotated[str, 'SSH 主机地址']
    port: Annotated[int, 'SSH 端口']
    username: Annotated[str, '远端用户名']
Device: TypeAlias = Annotated[_Device, {'additionalProperties': True}]

class _Session(TypedDict, total=False):
    id: Annotated[str, '会话 ID']
    device_id: Annotated[str, '设备 ID']
    device: Annotated[str, '设备名称']
    description: Annotated[str, '会话用途']
    address: Annotated[str, '远端地址']
    username: Annotated[str, '登录用户']
    port: Annotated[int, '端口']
    shell: Annotated[str, 'powershell/posix/not_detected']
    cwd: Annotated[str, '远端当前目录']
    connected: Annotated[bool, 'SSH 是否连接']
    busy: Annotated[bool, '会话是否正在执行命令']
Session: TypeAlias = Annotated[_Session, {'additionalProperties': True}]

class _DeviceResult(TypedDict, total=False):
    devices: Annotated[list[Device], '设备列表']
    saved: Annotated[bool, '保存标志']
    device: Annotated[Device, '保存后的设备']
    connected: Annotated[bool, '是否连接']
    removed: Annotated[str, '已删除设备 ID']
    name: Annotated[str, '已删除设备名']
DeviceResult: TypeAlias = Annotated[_DeviceResult, {'additionalProperties': True}]

class _SessionResult(TypedDict, total=False):
    sessions: Annotated[list[Session], '会话列表']
    removed: Annotated[str, '被删除会话 ID']
SessionResult: TypeAlias = Annotated[_SessionResult, {'additionalProperties': True}]

class _Terminal(TypedDict, total=False):
    session_id: Required[Annotated[str, '会话 ID']]
    device: Required[Annotated[str, '设备名称']]
    command: Annotated[str, '实际命令']
    stdout: Annotated[str, '标准输出']
    stderr: Annotated[str, '标准错误']
    output: Annotated[str, '合并输出，按当前平台返回']
    exit_code: Annotated[int | None, '退出码，结果未知时为空']
    status: Annotated[str, '执行状态']
    cwd: Annotated[str, '执行后目录']
    timed_out: Annotated[bool, '是否超时']
    truncated: Annotated[bool, '输出是否截断']
    note: Annotated[str, '中断或结果未知提示']
Terminal: TypeAlias = Annotated[_Terminal, {'additionalProperties': True}]

class _ParallelItem(TypedDict, total=False):
    index: Required[Annotated[int, '原始任务的0起始位置']]
    session_id: Annotated[str, '所用会话']
    error: Annotated[str, '该项失败或不确定结果']
    stdout: Annotated[str, '标准输出']
    stderr: Annotated[str, '标准错误']
    exit_code: Annotated[int | None, '退出码']
ParallelItem: TypeAlias = Annotated[_ParallelItem, {'additionalProperties': True}]

class Parallel(TypedDict, total=False):
    results: Required[Annotated[list[ParallelItem], '按原任务顺序排列的逐项结果']]

class _RemoteFile(TypedDict, total=False):
    name: Annotated[str, '条目名']
    path: Annotated[str, '远端路径']
    size: Annotated[int | None, '字节数']
    mtime: Annotated[float | None, '修改 Unix 秒']
    directory: Annotated[bool, '是否目录']
    permissions: Annotated[int | None, '远端权限位']
RemoteFile: TypeAlias = Annotated[_RemoteFile, {'additionalProperties': True}]

class _FileResult(TypedDict, total=False):
    session_id: Required[Annotated[str, 'SSH 会话 ID']]
    path: Annotated[str, '远端路径']
    items: Annotated[list[RemoteFile], '目录条目']
    size: Annotated[int | None, '文件字节数']
    mtime: Annotated[float | None, '修改时间 Unix 秒']
    directory: Annotated[bool, '是否目录']
    permissions: Annotated[int | None, '远端权限']
    bytes: Annotated[int, '传输/写入字节数']
    content: Annotated[str, '读取的文本']
    truncated: Annotated[bool, '是否截断']
    success: Annotated[bool, '操作标志']
    target: Annotated[str, '目标路径']
FileResult: TypeAlias = Annotated[_FileResult, {'additionalProperties': True}]

R_ssh_public_key: TypeAlias = PublicKey
R_ssh_device: TypeAlias = Device | DeviceResult
R_ssh_session: TypeAlias = Session | SessionResult
R_ssh_terminal: TypeAlias = Terminal
R_ssh_parallel: TypeAlias = Parallel
R_ssh_file: TypeAlias = FileResult

RESULTS = {'ssh_public_key': R_ssh_public_key, 'ssh_device': R_ssh_device, 'ssh_session': R_ssh_session, 'ssh_terminal': R_ssh_terminal, 'ssh_parallel': R_ssh_parallel, 'ssh_file': R_ssh_file}
