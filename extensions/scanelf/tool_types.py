"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Device(TypedDict, total=False):
    mac: Required[Annotated[str, '规范化 MAC 地址']]
    name: Annotated[str, '扫描器原始名称']
    display_name: Annotated[str, '优先本地别名的显示名']
    alias: Annotated[str, '本地别名']
    description: Annotated[str, '本地记忆描述']
    memory_matched: Annotated[bool, '是否命中本地记忆']
    online: Annotated[bool, '当前或最后已知在线状态，须结合 data_reliable']
    memory_updated_at: Annotated[str | None, '本地记忆更新时间，ISO8601']
    first_seen: Annotated[str | float | None, '首次发现，ISO8601 或 Unix 秒']
    last_seen: Annotated[str | float | None, '最近发现，ISO8601 或 Unix 秒']
    tags: Annotated[list[str], '上游标签']
    favorite: Annotated[bool, '是否收藏']
    resident: Annotated[bool, '是否常驻']
    ignored: Annotated[bool, '是否被上游忽略']
Device: TypeAlias = Annotated[_Device, {'additionalProperties': True}]

class DeviceIdentity(TypedDict):
    mac: Annotated[str, '规范化设备 MAC']
    name: Annotated[str, '扫描器名称，未设置为空字符串']
    display_name: Annotated[str, '优先本地别名的显示名称']
    alias: Annotated[str, '本地别名，未设置为空字符串']
    description: Annotated[str, '本地记忆描述，未设置为空字符串']
    memory_matched: Annotated[bool, '是否命中本地记忆']
    memory_updated_at: Annotated[str | None, '本地记忆更新时间，未保存为 null']

class _ObservedDevice(DeviceIdentity):
    online: Annotated[bool, '最后可靠快照的在线状态，是否仍可参考须看页面 data_reliable']
    status_text: Annotated[str, '状态显示文字']
    last_activity_text: Annotated[str, '最近活动显示文字']
    first_seen: Annotated[str | float | None, '首次发现时间，原始 ISO8601 或 Unix 秒，未知为 null']
    last_seen: Annotated[str | float | None, '最近发现时间，原始 ISO8601 或 Unix 秒，未知为 null']
    tags: Annotated[list[str], '上游标签列表']
    favorite: Annotated[bool, '是否收藏']
    resident: Annotated[bool, '是否常驻']
    ignored: NotRequired[Annotated[bool, '上游管理接口是否忽略此设备']]
    tags_text: NotRequired[Annotated[str, '管理页面的标签显示文字']]

ObservedDevice: TypeAlias = Annotated[_ObservedDevice, {'additionalProperties': True}]

class DeviceQueryPage(TypedDict):
    items: Annotated[list[ObservedDevice], '本页设备；即使没有匹配也始终返回 []']
    total: Annotated[int, '匹配总数']
    offset: Annotated[int, '0起始偏移']
    limit: Annotated[int, '请求页大小']
    has_more: Annotated[bool, '是否有后续页']
    scanner_connected: Annotated[bool, '扫描器是否连接']
    last_snapshot_at: Annotated[str | float | None, '原始快照时间，未知为 null']
    snapshot_fresh: Annotated[bool, '快照是否新鲜']
    data_reliable: Annotated[bool, '是否能用该快照判断当前状态']
    online_count: Annotated[int | None, '原始在线总数，未知为 null']
    note: Annotated[str, '观测可靠性提示']

class ManagedDevicePage(TypedDict):
    items: Annotated[list[ObservedDevice], '含上游忽略设备的本页管理资料']
    total: Annotated[int, '匹配总数']
    includes_ignored: Annotated[bool, '管理查询始终包含被忽略设备']
    offset: Annotated[int, '0起始偏移']
    has_more: Annotated[bool, '是否有后续页']

class LocalMemoryList(TypedDict):
    items: Annotated[list[DeviceIdentity], '已有本地记忆的设备身份列表']

class SavedMemory(TypedDict):
    saved: Annotated[bool, '本地记忆已更新']
    action: Annotated[str, 'set/append/remove 等记忆动作']
    device: Annotated[DeviceIdentity, '更新后的设备身份和本地记忆']

class _TimelineItem(TypedDict, total=False):
    id: Annotated[int | str, '上游事件 ID']
    at: Annotated[str | float, '上线/下线时间，使用上游原始时间格式']
    event: Annotated[str, '原始事件类型']
    online: Annotated[bool, '该事件是否上线']
    mac: Annotated[str, '设备 MAC']
TimelineItem: TypeAlias = Annotated[_TimelineItem, {'additionalProperties': True}]

class _Timeline(TypedDict, total=False):
    device: Required[Annotated[DeviceIdentity, '设备本地身份资料']]
    items: Required[Annotated[list[TimelineItem], '本页上下线记录']]
    count: Required[Annotated[int, '本页记录数']]
    limit: Required[Annotated[int, '请求页大小']]
    before: Required[Annotated[int, '输入的分页游标，0 表示最新开始']]
    next_cursor: Required[Annotated[int | None, '下一页游标']]
    has_more: Required[Annotated[bool, '是否有更早记录']]
    order: Required[Annotated[str, 'newest_first 最新在前']]
    fetched_at: Required[Annotated[str, '查询时间，ISO8601']]
Timeline: TypeAlias = Annotated[_Timeline, {'additionalProperties': True}]

class SavedDevice(TypedDict, total=False):
    saved: Required[Annotated[bool, '保存标志']]
    action: Annotated[str, '记忆操作类型']
    device: Required[Annotated[Device, '保存后的设备资料']]

R_scanelf_devices: TypeAlias = DeviceQueryPage
R_scanelf_device_memory: TypeAlias = DeviceIdentity | LocalMemoryList | SavedMemory
R_scanelf_device_timeline: TypeAlias = Timeline
R_scanelf_device_manage: TypeAlias = ObservedDevice | ManagedDevicePage | SavedDevice

RESULTS = {'scanelf_devices': R_scanelf_devices, 'scanelf_device_memory': R_scanelf_device_memory, 'scanelf_device_timeline': R_scanelf_device_timeline, 'scanelf_device_manage': R_scanelf_device_manage}
