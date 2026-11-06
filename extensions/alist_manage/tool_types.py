"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _FileInfo(TypedDict, total=False):
    name: Annotated[str, '文件名']
    size: Annotated[int, '字节数']
    is_dir: Annotated[bool, '是否目录']
    modified: Annotated[str, '上游修改时间']
    path: Annotated[str, 'AList 绝对路径']
    raw_url: Annotated[str, '按权限获取的原始下载地址']
    sign: Annotated[str, '上游临时签名，不对外泄露']
FileInfo: TypeAlias = Annotated[_FileInfo, {'additionalProperties': True}]

class _Listing(TypedDict, total=False):
    content: Annotated[list[FileInfo] | None, '本页文件元数据']
    total: Annotated[int, '条目总数']
    items: Annotated[list[FileInfo], '插件整理后的条目']
    path: Annotated[str, '所列路径']
    page: Annotated[int, '从1开始页码']
Listing: TypeAlias = Annotated[_Listing, {'additionalProperties': True}]

class _Write(TypedDict, total=False):
    preview: Annotated[bool, '是否仅预览']
    action: Annotated[str, '文件操作名称']
    path: Annotated[str, '源/目标绝对路径']
    target: Annotated[str, '移动复制目标']
    consequence: Annotated[str, '操作后果']
    next: Annotated[str, '确认流程要求']
    success: Annotated[bool, '是否成功']
    task: Annotated[DynamicObject, '上游异步任务信息']
Write: TypeAlias = Annotated[_Write, {'additionalProperties': True}]

R_alist_scan_folders: TypeAlias = str
R_alist_browse: TypeAlias = Listing | FileInfo
R_alist_write: TypeAlias = Write | DynamicJSON

RESULTS = {'alist_scan_folders': R_alist_scan_folders, 'alist_browse': R_alist_browse, 'alist_write': R_alist_write}
