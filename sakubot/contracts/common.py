"""Shared documented boundaries for genuinely dynamic external data."""
from typing import Annotated, NotRequired, TypedDict

DynamicObject = Annotated[dict[str, object], '动态字段映射；具体键和值由所选远端 API、实体属性或扩展决定，须查对应接口文档，不猜字段']
DynamicJSON = Annotated[dict[str, object] | list[object] | str | int | float | bool | None, '所选原生 API 的 JSON 数据，具体形状由接口决定；先确认接口文档再按类型读取']


class Artifact(TypedDict):
    url: Annotated[str, '框架附件 URL，有时效，不是工作空间路径']
    name: Annotated[str, '文件显示名称']
    mime: Annotated[str, 'MIME 内容类型']
    expires: Annotated[float, '附件过期时间，Unix 秒，UTC 基准']


class Truncated(TypedDict):
    truncated: Annotated[bool, 'true 表示原始响应已截断，不能当成完整原始对象读取']
    preview: Annotated[str, '被截断原始 JSON 的文本预览，不是完整 JSON 文档']
    hint: Annotated[str, '缩小范围或分页的提示']


class DeliveryStatus(TypedDict):
    ok: Annotated[bool, '本轮自动投递状态修改成功']
    send_result_to_source: Annotated[bool, '本轮是否自动投递至主会话源']
    targets: Annotated[list[str], '当前响应源 ID 列表']
    web_synced: Annotated[bool, '网页始终同步']
