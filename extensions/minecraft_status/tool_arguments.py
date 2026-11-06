"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_minecraft_servers1 = TypedDict(
    'A_minecraft_servers1',
    {
        'action': NotRequired[Annotated[str, {'description': 'list/get/add/update/remove。', 'default': 'list'}]],
        'server': NotRequired[Annotated[str, {'description': 'get/update/remove 的条目 ID、准确名称、别名或已保存地址；list/add 留空。', 'default': ''}]],
        'details': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'add 需要 name 与 address（或 ip，可含端口）；可填 alias、description、edition（java/bedrock，默认java）。update 仅传要改的字段；别名、描述空文本清空。Java 默认25565，基岩版默认19132；IPv6 带端口写 [IPv6]:端口。'}] | None, {'default': None, 'description': '条目字段：name、address（或 ip）、alias、description、edition（java/bedrock）；update 省略字段保持原值'}]],
    },
    total=False,
)

A_minecraft_servers: TypeAlias = Annotated[A_minecraft_servers1, {'additionalProperties': False}]

A_minecraft_status2 = TypedDict(
    'A_minecraft_status2',
    {
        'server': NotRequired[Annotated[str, {'description': '单个已保存条目的 ID、名称、别名或地址；与 servers 都留空时查询全部已保存条目。', 'default': ''}]],
        'servers': NotRequired[Annotated[Annotated[list[Annotated[object, {'description': '一个列表元素；多台已保存服务器的 ID、名称或别名，最多100台，结果分别返回。'}]], {'description': '多台已保存服务器的 ID、名称或别名，最多100台，结果分别返回。'}] | None, {'default': None, 'description': '需要查询的多个保存条目的 ID/名称/别名列表；不把显示名当作网络地址'}]],
        'address': NotRequired[Annotated[str, {'description': '临时查询未保存的 IP/域名，可带端口；填写时 server/servers 留空，不自动保存条目。', 'default': ''}]],
        'edition': NotRequired[Annotated[str, {'description': '仅临时地址使用，java/bedrock；已保存条目沿用自身的版本类型。', 'default': 'java'}]],
        'refresh': NotRequired[Annotated[bool, {'description': 'true 跳过30秒缓存，立即查询。', 'default': False}]],
    },
    total=False,
)

A_minecraft_status: TypeAlias = Annotated[A_minecraft_status2, {'additionalProperties': False}]

A_minecraft_alerts3 = TypedDict(
    'A_minecraft_alerts3',
    {
        'action': NotRequired[Annotated[str, {'description': 'list/settings/add/update/remove。', 'default': 'list'}]],
        'server': NotRequired[Annotated[str, {'description': 'add 的已保存服务器 ID、名称或别名；update 可改目标服务器，其他动作留空。', 'default': ''}]],
        'rule_id': NotRequired[Annotated[str, {'description': 'update/remove 使用 list 中的准确提醒规则ID，其他动作留空。', 'default': ''}]],
        'details': NotRequired[Annotated[Annotated[dict[str, object], {'description': 'settings 支持 enabled、interval_minutes（1到1440，默认5）、offline_confirmations（1到10，默认2）。add/update 支持 kind、enabled、target（main 或 private:QQ号/group:群号）、threshold。kind 为 players_joined（0变为有人）、players_reached（从低于threshold变为达到）、players_below（降至threshold以下）、players_increase、players_decrease、server_online、server_offline。threshold 为正整数，仅人数阈值类型使用。update 省略字段保留；新规则 target 省略则使用 main。'}] | None, {'default': None, 'description': '所选提醒动作的规则字段，例如 kind、threshold、enabled；按提醒工具说明提供，结果跟随主会话事件路由'}]],
    },
    total=False,
)

A_minecraft_alerts: TypeAlias = Annotated[A_minecraft_alerts3, {'additionalProperties': False}]

ARGUMENTS = {'minecraft_servers': A_minecraft_servers, 'minecraft_status': A_minecraft_status, 'minecraft_alerts': A_minecraft_alerts}
