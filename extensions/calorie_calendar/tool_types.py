"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

from .event_types import EventData

class Entry(TypedDict, total=False):
    id: Required[Annotated[str, '记录 ID']]
    day: Required[Annotated[str, '日期 YYYY-MM-DD，Asia/Shanghai']]
    kind: Required[Annotated[str, 'intake 摄入、expenditure 消耗']]
    label: Required[Annotated[str, '餐次或消耗标签']]
    kcal: Required[Annotated[float, '热量，kcal']]
    estimated: Required[Annotated[int | bool, '数据库 0/1 或布尔值，是否为估算']]
    note: Required[Annotated[str, '具体食物、份量、依据']]
    source: Required[Annotated[str, '记录来源']]
    created: Required[Annotated[float, '创建 Unix 秒']]
    updated: Required[Annotated[float, '修改 Unix 秒']]

class Day(TypedDict, total=False):
    day: Required[Annotated[str, '归属日期，YYYY-MM-DD']]
    intake: Required[Annotated[float, '摄入总 kcal']]
    expenditure: Required[Annotated[float, '消耗总 kcal']]
    balance: Required[Annotated[float, '摄入减消耗，kcal']]
    count: Required[Annotated[int, '记录条数']]
    confirmed: Required[Annotated[bool, '是否确认并计入统计']]
    entries: Required[Annotated[list[Entry], '全部当日记录']]

class Totals(TypedDict, total=False):
    days: Required[Annotated[int, '纳入统计的已确认天数']]
    intake: Required[Annotated[float, '已确认日摄入总 kcal']]
    expenditure: Required[Annotated[float, '已确认日消耗总 kcal']]
    balance: Required[Annotated[float, '摄入减消耗，kcal']]

class DaySummary(TypedDict, total=False):
    day: Required[Annotated[str, '日期 YYYY-MM-DD']]
    intake: Required[Annotated[float, '摄入 kcal']]
    expenditure: Required[Annotated[float, '消耗 kcal']]
    balance: Required[Annotated[float, '摄入减消耗 kcal']]
    count: Required[Annotated[int, '记录数']]
    confirmed: Required[Annotated[bool, '确认状态']]

class Report(TypedDict, total=False):
    start: Required[Annotated[str, '起始日期 YYYY-MM-DD']]
    end: Required[Annotated[str, '结束日期 YYYY-MM-DD']]
    days: Required[Annotated[list[DaySummary], '各日汇总']]
    total: Required[Annotated[Totals, '仅已确认日期的统计']]

R_calorie_record: TypeAlias = Day
R_calorie_confirm: TypeAlias = Day
R_calorie_report: TypeAlias = Day | Report

RESULTS = {'calorie_record': R_calorie_record, 'calorie_confirm': R_calorie_confirm, 'calorie_report': R_calorie_report}
