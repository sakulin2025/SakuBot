"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_alist_scan_folders1 = TypedDict(
    'A_alist_scan_folders1',
    {
    },
    total=False,
)

A_alist_scan_folders: TypeAlias = Annotated[A_alist_scan_folders1, {'additionalProperties': False}]

A_alist_browse2 = TypedDict(
    'A_alist_browse2',
    {
        'path': NotRequired[Annotated[str, {'description': 'AList 绝对路径，默认根目录。', 'default': '/'}]],
        'action': NotRequired[Annotated[str, {'description': 'list 列目录、info 详情、download 获取文件下载链接。', 'default': 'list'}]],
        'page': NotRequired[Annotated[int, {'description': '列表页码，每页最多200项。', 'default': 1}]],
    },
    total=False,
)

A_alist_browse: TypeAlias = Annotated[A_alist_browse2, {'additionalProperties': False}]

A_alist_write3 = TypedDict(
    'A_alist_write3',
    {
        'action': Required[Annotated[str, {'description': 'mkdir/upload/remove/rename/move/copy。'}]],
        'path': Required[Annotated[str, {'description': '完整源路径；mkdir/upload 时为完整目标路径。'}]],
        'target': NotRequired[Annotated[str, {'description': 'rename 为新文件名；move/copy 为已存在的目标目录。', 'default': ''}]],
        'source_url': NotRequired[Annotated[str, {'description': 'upload 的 http/https 文件来源，下载后上传到 path。', 'default': ''}]],
        'confirmed': NotRequired[Annotated[bool, {'description': '用户已明确确认本次预览才为 true，默认 false。', 'default': False}]],
    },
    total=False,
)

A_alist_write: TypeAlias = Annotated[A_alist_write3, {'additionalProperties': False}]

ARGUMENTS = {'alist_scan_folders': A_alist_scan_folders, 'alist_browse': A_alist_browse, 'alist_write': A_alist_write}
