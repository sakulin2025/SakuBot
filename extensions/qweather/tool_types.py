"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Location(TypedDict, total=False):
    id: Annotated[str, '和风城市 Location ID']
    name: Annotated[str, '城市名']
    adm1: Annotated[str, '省级行政区']
    adm2: Annotated[str, '地级行政区']
    country: Annotated[str, '国家']
    lat: Annotated[str, '纬度']
    lon: Annotated[str, '经度']
    tz: Annotated[str, 'IANA 时区']
    utcOffset: Annotated[str, 'UTC 偏移']
    type: Annotated[str, '地点分类']
Location: TypeAlias = Annotated[_Location, {'additionalProperties': True}]

class Geo(TypedDict, total=False):
    query: Required[Annotated[str, '检索地点']]
    locations: Required[Annotated[list[Location], '城市候选']]
    refer: Required[Annotated[DynamicObject, '接口归因与来源资料']]
    source: Required[Annotated[DynamicObject, '服务来源信息']]
    fetched_at: Required[Annotated[str, '查询时间，含时区 ISO8601']]
    cached: Required[Annotated[bool, '是否缓存']]
    cache_age_seconds: Required[Annotated[int, '缓存年龄秒数']]
    cache_ttl_seconds: Required[Annotated[int, '缓存有效秒数']]

class WeatherService(TypedDict):
    service: Annotated[str, '实际查询的 now/daily/hourly/minutely/warning/air/indices 服务']
    location: Annotated[Location, '已确定的实际查询地点']
    source: Annotated[DynamicObject, '归因和原始数据来源']
    data: Annotated[DynamicObject, '所选服务的原始 JSON 内容，具体字段按该服务文档解释']
    fetched_at: Annotated[str, '含时区 ISO8601 查询时间']
    cached: Annotated[bool, '是否来自缓存']
    cache_age_seconds: Annotated[int, '缓存年龄，秒']
    cache_ttl_seconds: Annotated[int, '缓存有效时间，秒']

class WeatherOverview(TypedDict):
    location: Annotated[Location, '已确定的实际查询地点']
    services: Annotated[dict[str, WeatherService], '成功的 now/daily 查询；子服务失败时不包含对应键']
    errors: Annotated[dict[str, str], '子服务名到失败原因的映射，成功子服务不在此映射中']
    source: Annotated[DynamicObject, '天气来源']

class LocationSelection(TypedDict):
    needs_selection: Annotated[Literal[True], '地点存在歧义，尚未查询天气']
    query: Annotated[str, '原始地点输入']
    candidates: Annotated[list[Location], '候选城市，需辨认实际城市 ID']
    note: Annotated[str, '选择城市的提示']

Weather: TypeAlias = WeatherService | WeatherOverview | LocationSelection

R_qweather_geo: TypeAlias = Geo
R_qweather_weather: TypeAlias = Weather

RESULTS = {'qweather_geo': R_qweather_geo, 'qweather_weather': R_qweather_weather}
