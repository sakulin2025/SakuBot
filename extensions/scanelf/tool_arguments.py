"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_scanelf_devices1 = TypedDict(
    'A_scanelf_devices1',
    {
        'state': NotRequired[Annotated[str, {'description': 'all/online/offline，默认包括所有可见设备；断连时筛选的是最后已知状态。', 'default': 'all'}]],
        'match': NotRequired[Annotated[str, {'description': '按 MAC、名称、本地别名、描述或标签进行关键词筛选，留空不限。', 'default': ''}]],
        'limit': NotRequired[Annotated[int, {'description': '每页设备数，1到100。', 'default': 50}]],
        'offset': NotRequired[Annotated[int, {'description': '筛选后列表的分页偏移，从0开始。', 'default': 0}]],
        'refresh': NotRequired[Annotated[bool, {'description': 'true 立即请求原生 HTTP API；默认最多使用30秒缓存。', 'default': False}]],
    },
    total=False,
)

A_scanelf_devices: TypeAlias = Annotated[A_scanelf_devices1, {'additionalProperties': False}]

A_scanelf_device_memory2 = TypedDict(
    'A_scanelf_device_memory2',
    {
        'action': NotRequired[Annotated[str, {'description': 'list 列出有本地记忆的可见设备；get 查看某台设备；set 更新；append 追加描述；remove 删除该设备全部本地别名和描述。', 'default': 'list'}]],
        'device': NotRequired[Annotated[str, {'description': '设备完整 MAC、准确名称或唯一本地别名；list 留空。', 'default': ''}]],
        'details': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'set 可传 alias、description，省略的字段保留，空字符串清空；append 传 description 追加到原描述。其他动作留空对象。alias 最长100字，description 最长8000字。'}] | None, {'default': None, 'description': '本地记忆字段 alias（别名）和 description（额外描述）；不修改上游扫描器'}]],
    },
    total=False,
)

A_scanelf_device_memory: TypeAlias = Annotated[A_scanelf_device_memory2, {'additionalProperties': False}]

A_scanelf_device_timeline3 = TypedDict(
    'A_scanelf_device_timeline3',
    {
        'device': Required[Annotated[str, {'description': '已发现设备的完整MAC、准确名称或唯一本地别名；重名时先查设备列表再使用MAC。'}]],
        'limit': NotRequired[Annotated[int, {'description': '每页1到100条，默认100；这是分页大小，不是完整历史的总条数上限。', 'default': 100}]],
        'before': NotRequired[Annotated[int, {'description': '首次为0从最新开始；继续分页填上一页 next_cursor 的实际整数值，不要自行猜测或递减。', 'default': 0}]],
    },
    total=False,
)

A_scanelf_device_timeline: TypeAlias = Annotated[A_scanelf_device_timeline3, {'additionalProperties': False}]

A_scanelf_device_manage4 = TypedDict(
    'A_scanelf_device_manage4',
    {
        'action': NotRequired[Annotated[str, {'description': 'list/get/add/update。', 'default': 'list'}]],
        'device': NotRequired[Annotated[str, {'description': 'add 必须为完整 MAC；get/update 可用实际名称、本地别名或 MAC，重名时使用 MAC。', 'default': ''}]],
        'details': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'add/update 可含 name（最多80字）、tags（最多20项，每项1～32字）、favorite/resident/ignored（布尔值）；update 省略字段保留。空名称/空 tags 清空对应字段。'}] | None, {'default': None, 'description': '上游可管理字段 name、tags、favorite、resident、ignored；未提供字段保持原值'}]],
        'limit': NotRequired[Annotated[int, {'description': 'list 每页1～100条。', 'default': 50}]],
        'offset': NotRequired[Annotated[int, {'description': 'list 非负分页偏移。', 'default': 0}]],
    },
    total=False,
)

A_scanelf_device_manage: TypeAlias = Annotated[A_scanelf_device_manage4, {'additionalProperties': False}]

ARGUMENTS = {'scanelf_devices': A_scanelf_devices, 'scanelf_device_memory': A_scanelf_device_memory, 'scanelf_device_timeline': A_scanelf_device_timeline, 'scanelf_device_manage': A_scanelf_device_manage}
