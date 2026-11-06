"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class SearchItem(TypedDict, total=False):
    title: Required[Annotated[str, '搜索结果标题']]
    url: Required[Annotated[str, '实际来源 URL']]
    snippet: Required[Annotated[str, '搜索摘要，不等于已核实全文']]

class SearchResult(TypedDict, total=False):
    query: Required[Annotated[str, '实际搜索词']]
    provider: Required[Annotated[str, '使用的搜索服务']]
    fetched_at: Required[Annotated[float, '查询时间，Unix 秒']]
    results: Required[Annotated[list[SearchItem], '搜索结果']]

class _Link(TypedDict, total=False):
    url: Required[Annotated[str, '链接绝对地址']]
    text: Annotated[str, '链接文字']
Link: TypeAlias = Annotated[_Link, {'additionalProperties': True}]

class FetchResult(TypedDict, total=False):
    url: Required[Annotated[str, '请求网页地址']]
    title: Required[Annotated[str, '页面标题']]
    content_type: Required[Annotated[str, '响应内容类型']]
    fetched_at: Required[Annotated[float, '抓取 Unix 秒']]
    text: Required[Annotated[str, '本页正文']]
    links: Required[Annotated[list[Link], '提取的链接']]
    cached: Required[Annotated[bool, '是否使用缓存']]
    offset: Required[Annotated[int, '正文字符偏移']]
    total_chars: Required[Annotated[int, '全文字符数']]
    has_more: Required[Annotated[bool, '是否还有正文']]
    next_offset: Required[Annotated[int | None, '下一页字符偏移']]

R_web_search: TypeAlias = SearchResult
R_web_fetch: TypeAlias = FetchResult

RESULTS = {'web_search': R_web_search, 'web_fetch': R_web_fetch}
