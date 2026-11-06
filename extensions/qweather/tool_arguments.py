"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_qweather_geo1 = TypedDict(
    'A_qweather_geo1',
    {
        'location': NotRequired[Annotated[str, {'description': '城市名称、Location ID 或 经度,纬度；留空使用配置的默认城市。', 'default': ''}]],
        'adm': NotRequired[Annotated[str, {'description': '上级行政区过滤，如 beijing，用于排除重名城市。', 'default': ''}]],
        'country': NotRequired[Annotated[str, {'description': '可选国家或地区 ISO 代码，如 cn；留空搜索全球。', 'default': ''}]],
        'limit': NotRequired[Annotated[int, {'description': '返回数量1到20，默认10。', 'default': 10}]],
        'refresh': NotRequired[Annotated[bool, {'description': '默认使用7天地理信息缓存；只有需要更新时才为true。', 'default': False}]],
    },
    total=False,
)

A_qweather_geo: TypeAlias = Annotated[A_qweather_geo1, {'additionalProperties': False}]

A_qweather_weather2 = TypedDict(
    'A_qweather_weather2',
    {
        'service': NotRequired[Annotated[str, {'description': 'overview/now/daily/hourly/minutely/warning/air/indices。', 'default': 'overview'}]],
        'location': NotRequired[Annotated[str, {'description': '城市、Location ID或 经度,纬度；留空默认城市。', 'default': ''}]],
        'adm': NotRequired[Annotated[str, {'description': '可选上级行政区，消除重名。', 'default': ''}]],
        'days': NotRequired[Annotated[int, {'description': '仅daily使用，1到10天，默认3；用户明确需要更长预报才增加。', 'default': 3}]],
        'hours': NotRequired[Annotated[int, {'description': '仅hourly使用，1到240小时，默认24；用户明确需要才增加。', 'default': 24}]],
        'index_types': NotRequired[Annotated[str, {'description': '仅indices使用，逗号分隔0到16；3穿衣、5紫外线、9感冒，0全部不能混用。默认3,5，今日指数。', 'default': '3,5'}]],
        'refresh': NotRequired[Annotated[bool, {'description': 'true刷新指定天气服务；默认复用缓存，实时15分钟、每日1小时、小时/空气30分钟、降水/预警5分钟、指数1小时。', 'default': False}]],
    },
    total=False,
)

A_qweather_weather: TypeAlias = Annotated[A_qweather_weather2, {'additionalProperties': False}]

ARGUMENTS = {'qweather_geo': A_qweather_geo, 'qweather_weather': A_qweather_weather}
