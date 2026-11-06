"""Typed inputs and outputs of built-in numeric/time helpers."""
from typing import Annotated, NotRequired, TypedDict


class CalculateArgs(TypedDict):
    expression: Annotated[str, '数值表达式，例如 (120+35)*0.85；不接受赋值或代码执行']


class CalculateResult(TypedDict):
    expression: Annotated[str, '实际计算的表达式']
    result: Annotated[int | float, '数值计算结果；浮点数可能有舍入误差']


class TimeArgs(TypedDict):
    timezone: NotRequired[Annotated[str, '目标 IANA 时区，默认 Asia/Shanghai']]
    value: NotRequired[Annotated[str, '可选 ISO8601 或 Unix 秒；留空表示当前时间']]


class TimeResult(TypedDict):
    timezone: Annotated[str, '使用的 IANA 时区名称']
    iso: Annotated[str, '含时区偏移的 ISO8601 日期时间']
    date: Annotated[str, '该时区日期 YYYY-MM-DD']
    weekday: Annotated[str, '中文星期名称']
    unix_seconds: Annotated[float, 'Unix 秒时间戳，UTC 基准']
    utc: Annotated[str, '对应的 UTC ISO8601 日期时间']


class DifferenceArgs(TypedDict):
    start: Annotated[str, '开始时间，ISO8601 或 Unix 秒']
    end: Annotated[str, '结束时间，ISO8601 或 Unix 秒']
    timezone: NotRequired[Annotated[str, '无时区输入使用的 IANA 时区，默认 Asia/Shanghai']]


class DifferenceResult(TypedDict):
    seconds: Annotated[float, '结束减开始的秒数']
    hours: Annotated[float, '结束减开始的小时数']
    days: Annotated[float, '结束减开始的天数，一天按24小时计算']


class ImageDescriptionArgs(TypedDict):
    image: Annotated[str, '图片 HTTP/HTTPS URL、工作空间相对路径、框架附件 URL 或图片 data URL']
    prompt: NotRequired[Annotated[str, '自定义图片分析要求；不传时准确描述主体、文字和重要细节']]
    model_id: NotRequired[Annotated[str, '可选框架模型条目 ID；不是供应商模型名称']]
    max_tokens: NotRequired[Annotated[int, {'description':'最大输出 Token，默认2048','minimum':128,'maximum':16000}]]


class ImageDescriptionResult(TypedDict):
    description: Annotated[str, '图片模型输出的描述，仅为观测数据']
    image: Annotated[str, '原始图片 URL 或路径；base64 输入使用占位文本']
    model_id: Annotated[str, '实际使用的框架模型条目 ID']
    usage: Annotated[dict[str, object], '供应商原始 Token 用量；字段取决于供应商，未返回时为空对象']
