"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_ha_initialize1 = TypedDict(
    'A_ha_initialize1',
    {
        'action': NotRequired[Annotated[str, {'description': 'status/scan/rooms/entities/room/policy/review_room/build/reset。', 'default': 'status'}]],
        'area': NotRequired[Annotated[str, {'description': '房间标识，未分配区域为 __unassigned__。', 'default': ''}]],
        'enabled': NotRequired[Annotated[bool, {'description': 'room 操作是否启用房间。', 'default': False}]],
        'entity_id': NotRequired[Annotated[str, {'description': 'policy 操作的完整实体ID。', 'default': ''}]],
        'policy': NotRequired[Annotated[str, {'description': 'controllable/readonly/ignore。', 'default': ''}]],
        'alias': NotRequired[Annotated[str, {'description': 'policy 操作的别名，多个用 / 分隔，空字符串清空。', 'default': ''}]],
        'group': NotRequired[Annotated[str, {'description': 'policy 操作的分组，空字符串清空。', 'default': ''}]],
        'confirmed': NotRequired[Annotated[bool, {'description': '用户确认覆盖草稿、采纳本房间建议、发布或重置后才可为 true。', 'default': False}]],
    },
    total=False,
)

A_ha_initialize: TypeAlias = Annotated[A_ha_initialize1, {'additionalProperties': False}]

A_ha_query2 = TypedDict(
    'A_ha_query2',
    {
        'entity_id': NotRequired[Annotated[str, {'description': '完整实体ID，留空列出允许的实体。', 'default': ''}]],
        'match': NotRequired[Annotated[str, {'description': '原名、HA friendly_name、别名、区域、分组或ID关键词，例如 灯、左灯、顶灯。', 'default': ''}]],
        'domain': NotRequired[Annotated[str, {'description': '可选的 HA 技术类型，多个用逗号分隔；按设备用途查询时优先留空，灯也可能属于 switch。', 'default': ''}]],
        'summary': NotRequired[Annotated[bool, {'description': '返回按技术类型统计并保留设备名字、别名和状态，省略详细 attributes。', 'default': False}]],
    },
    total=False,
)

A_ha_query: TypeAlias = Annotated[A_ha_query2, {'additionalProperties': False}]

A_ha_history3 = TypedDict(
    'A_ha_history3',
    {
        'entity_id': Required[Annotated[str, {'description': '完整实体 ID，例如 sensor.temperature。'}]],
        'start': NotRequired[Annotated[str, {'description': '开始时间，ISO 8601 格式并带时区，例如 2026-10-31T00:00:00+08:00；留空为结束时间前 24 小时。', 'default': ''}]],
        'end': NotRequired[Annotated[str, {'description': '结束时间，ISO 8601 格式并带时区；留空为当前时间。分页时保持首次返回的 start 和 end 不变。', 'default': ''}]],
        'limit': NotRequired[Annotated[int, {'description': '每页记录数，默认 200，最大 1000。', 'default': 200}]],
        'offset': NotRequired[Annotated[int, {'description': '从第几条开始，默认 0；下一页使用 next_offset。', 'default': 0}]],
    },
    total=False,
)

A_ha_history: TypeAlias = Annotated[A_ha_history3, {'additionalProperties': False}]

A_ha_control4 = TypedDict(
    'A_ha_control4',
    {
        'entity_id': NotRequired[Annotated[str, {'description': '单台设备的实际完整实体ID；批量操作可留空。', 'default': ''}]],
        'action': NotRequired[Annotated[str, {'description': 'on/off/set。', 'default': ''}]],
        'params': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'set参数，brightness百分比/音量、temperature温度、mode模式、option选项、position位置、value数值；无参数用空对象。'}] | None, {'default': None, 'description': '所选 HA 控制动作的服务参数，例如 brightness/temperature；结构按 domain 和 action 决定'}]],
        'entity_ids': NotRequired[Annotated[Annotated[list[Annotated[object, {'description': '一个列表元素；多台设备的实际实体ID，使用相同动作和参数；可一次打开或关闭多盏灯，不要猜ID。'}]], {'description': '多台设备的实际实体ID，使用相同动作和参数；可一次打开或关闭多盏灯，不要猜ID。'}] | None, {'default': None, 'description': '批量操作的完整 HA 实体 ID 列表，与单实体参数按工具说明选择'}]],
        'preview': NotRequired[Annotated[bool, {'description': 'true 只返回计划、不操作设备；默认 false 按当前指令直接执行，无强制确认步骤。', 'default': False}]],
        'force': NotRequired[Annotated[bool, {'description': '用户明确要求控制诊断实体时为 true。', 'default': False}]],
    },
    total=False,
)

A_ha_control: TypeAlias = Annotated[A_ha_control4, {'additionalProperties': False}]

A_ha_manual5 = TypedDict(
    'A_ha_manual5',
    {
        'action': NotRequired[Annotated[str, {'description': 'read/append/write/clear。用户说“记住”时直接保存；纠正或删除某条要求可先 read 再 write。', 'default': 'read'}]],
        'content': NotRequired[Annotated[str, {'description': 'append 的新增要求，或 write 的完整更新文档；read/clear 留空。write 时保留仍有效的其他要求。', 'default': ''}]],
    },
    total=False,
)

A_ha_manual: TypeAlias = Annotated[A_ha_manual5, {'additionalProperties': False}]

A_ha_api6 = TypedDict(
    'A_ha_api6',
    {
        'method': NotRequired[Annotated[str, {'description': 'GET/POST/PUT/PATCH/DELETE。', 'default': 'GET'}]],
        'path': NotRequired[Annotated[str, {'description': '以 /api/ 开头的官方 REST 路径，例如 /api/config、/api/services、/api/states、/api/template、/api/services/light/turn_on；不要传协议、域名、查询字符串或 ..。时间区间等参数放在 query 中。', 'default': '/api/'}]],
        'query': NotRequired[Annotated[Annotated[dict[str, object], {'description': '查询参数对象；数组会按逗号连接，布尔值转为 true/false，值为 null 的键会被忽略。例如 {"filter_entity_id": "sensor.a,sensor.b"}。'}] | None, {'default': None, 'description': '官方 REST 端点的查询参数；数组按逗号连接，布尔值转 true/false，null 键忽略'}]],
        'body': NotRequired[Annotated[Annotated[dict[str, object] | list[Annotated[object, {'description': '一个列表元素；元素结构由该参数定义'}]] | None, {'description': 'POST/PUT/PATCH 的 JSON 请求体，可以是对象或数组；GET 和 DELETE 不支持 body。'}] | None, {'default': None, 'description': 'POST/PUT/PATCH JSON 对象或数组；GET/DELETE不接受请求体'}]],
    },
    total=False,
)

A_ha_api: TypeAlias = Annotated[A_ha_api6, {'additionalProperties': False}]

ARGUMENTS = {'ha_initialize': A_ha_initialize, 'ha_query': A_ha_query, 'ha_history': A_ha_history, 'ha_control': A_ha_control, 'ha_manual': A_ha_manual, 'ha_api': A_ha_api}
