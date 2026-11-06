"""Documented plugin event contracts; TypedDict values are ordinary dicts."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

EventData_previous2 = TypedDict('EventData_previous2', {'signature': NotRequired[Annotated[list[Annotated[Annotated[str, {'description': '版本类型、地址或端口'}] | Annotated[int, {'description': '版本类型、地址或端口'}], {'description': '版本类型、地址或端口'}]], {'description': '本次查询目标签名，依次为 edition、host、port；用于区分配置改变后的基线'}]], 'stable': NotRequired[Annotated[Literal['online', 'offline', None], {'description': '经连续失败判定的稳定状态；尚未建基线时可能为空', 'x-enum-descriptions': {'online': '可达', 'offline': '连续失败达到阈值，疑似离线', 'None': '尚无稳定状态'}}]], 'failures': NotRequired[Annotated[int, {'description': '连续查询失败次数，单位：次', 'x-unit': 'count'}]], 'players': NotRequired[Annotated[Annotated[int, {'description': '在线人数，单位：人；未知时 null', 'x-unit': 'players'}] | Annotated[None, {'description': '在线人数，单位：人；未知时 null', 'x-unit': 'players'}], {'description': '在线人数，单位：人；未知时 null', 'x-unit': 'players'}]], 'result': NotRequired[Annotated[dict[str, object], {'description': '状态协议原始查询结果，可能含 online、version、MOTD、players_online、players_max、延迟和错误信息；以实际返回为准'}]], 'checked_at': NotRequired[Annotated[str, {'description': '本次查询时间，ISO 8601 含时区'}]]}, total=False)

EventData_current3 = TypedDict('EventData_current3', {'signature': NotRequired[Annotated[list[Annotated[Annotated[str, {'description': '版本类型、地址或端口'}] | Annotated[int, {'description': '版本类型、地址或端口'}], {'description': '版本类型、地址或端口'}]], {'description': '本次查询目标签名，依次为 edition、host、port；用于区分配置改变后的基线'}]], 'stable': NotRequired[Annotated[Literal['online', 'offline', None], {'description': '经连续失败判定的稳定状态；尚未建基线时可能为空', 'x-enum-descriptions': {'online': '可达', 'offline': '连续失败达到阈值，疑似离线', 'None': '尚无稳定状态'}}]], 'failures': NotRequired[Annotated[int, {'description': '连续查询失败次数，单位：次', 'x-unit': 'count'}]], 'players': NotRequired[Annotated[Annotated[int, {'description': '在线人数，单位：人；未知时 null', 'x-unit': 'players'}] | Annotated[None, {'description': '在线人数，单位：人；未知时 null', 'x-unit': 'players'}], {'description': '在线人数，单位：人；未知时 null', 'x-unit': 'players'}]], 'result': NotRequired[Annotated[dict[str, object], {'description': '状态协议原始查询结果，可能含 online、version、MOTD、players_online、players_max、延迟和错误信息；以实际返回为准'}]], 'checked_at': NotRequired[Annotated[str, {'description': '本次查询时间，ISO 8601 含时区'}]]}, total=False)

EventData1 = TypedDict('EventData1', {'server_id': Required[Annotated[str, {'description': '保存条目的唯一 ID'}]], 'server': NotRequired[Annotated[dict[str, object], {'description': '保存的服务器资料，包含 id/name/alias/description/edition/host/port/display_name；不是服务器返回的指令'}]], 'previous': Required[Annotated[EventData_previous2, {'description': '上次观测快照；首次观测可能为空对象', 'additionalProperties': True}]], 'current': Required[Annotated[EventData_current3, {'description': '本次观测快照', 'additionalProperties': True}]], 'changes': Required[Annotated[list[Annotated[Literal['status', 'players'], {'description': '变化类别', 'x-enum-descriptions': {'status': '稳定在线状态改变', 'players': '在线人数改变'}}]], {'description': '实际变化类别；空数组表示无状态或人数变化'}]]}, total=False)

EventData: TypeAlias = Annotated[EventData1, {'description': '服务器轮询观测及状态/人数变化；离线为连续不可达判定，不保证服务器进程已关闭。人数阈值绑定在筛选阶段计算。', 'examples': [{'server_id': 'survival', 'server': {'id': 'survival', 'name': '生存服', 'host': 'mc.example.com', 'port': 25565}, 'previous': {'stable': 'online', 'players': 0, 'signature': ['java', 'mc.example.com', 25565], 'failures': 0, 'result': {'online': True}, 'checked_at': '2026-11-06T08:55:00+08:00'}, 'current': {'stable': 'online', 'players': 2, 'signature': ['java', 'mc.example.com', 25565], 'failures': 0, 'result': {'online': True}, 'checked_at': '2026-11-06T09:00:00+08:00'}, 'changes': ['players']}], 'additionalProperties': True}]

Parameters04 = TypedDict('Parameters04', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]], 'change': NotRequired[Annotated[Literal['observation', 'status', 'players'], {'description': '限定哪些观测触发动作', 'title': '触发条件', 'default': 'observation', 'x-enum-descriptions': {'observation': '每次观测均触发', 'status': '仅稳定在线状态改变', 'players': '仅在线人数改变'}}]]}, total=False)

Parameters0: TypeAlias = Annotated[Parameters04, {'additionalProperties': True}]

Parameters15 = TypedDict('Parameters15', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]], 'threshold': NotRequired[Annotated[int, {'description': '在线人数交叉阈值，单位：人；达到为从低于变为大于等于，跌破为从大于等于变为低于', 'title': '人数阈值', 'minimum': 1, 'default': 1, 'x-unit': 'players'}]]}, total=False)

Parameters1: TypeAlias = Annotated[Parameters15, {'additionalProperties': True}]

Parameters26 = TypedDict('Parameters26', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]], 'threshold': NotRequired[Annotated[int, {'description': '在线人数交叉阈值，单位：人；达到为从低于变为大于等于，跌破为从大于等于变为低于', 'title': '人数阈值', 'minimum': 1, 'default': 1, 'x-unit': 'players'}]]}, total=False)

Parameters2: TypeAlias = Annotated[Parameters26, {'additionalProperties': True}]

Parameters37 = TypedDict('Parameters37', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters3: TypeAlias = Annotated[Parameters37, {'additionalProperties': True}]

Parameters48 = TypedDict('Parameters48', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters4: TypeAlias = Annotated[Parameters48, {'additionalProperties': True}]

Parameters59 = TypedDict('Parameters59', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters5: TypeAlias = Annotated[Parameters59, {'additionalProperties': True}]

Parameters610 = TypedDict('Parameters610', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters6: TypeAlias = Annotated[Parameters610, {'additionalProperties': True}]

Parameters711 = TypedDict('Parameters711', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters7: TypeAlias = Annotated[Parameters711, {'additionalProperties': True}]

Parameters812 = TypedDict('Parameters812', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters8: TypeAlias = Annotated[Parameters812, {'additionalProperties': True}]

Parameters913 = TypedDict('Parameters913', {'server_id': NotRequired[Annotated[str, {'description': '保存的服务器条目 ID，留空匹配所有服务器', 'title': '服务器 · 留空全部'}]]}, total=False)

Parameters9: TypeAlias = Annotated[Parameters913, {'additionalProperties': True}]
