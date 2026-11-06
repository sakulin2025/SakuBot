"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class _Workout(TypedDict, total=False):
    id: Annotated[str, '训练 UUID']
    name: Annotated[str | None, '训练显示名称']
    source: Annotated[str | None, '主要来源']
    sources: Annotated[list[object] | None, '原始来源列表']
    start_time: Annotated[str | None, '训练开始 ISO8601，按插件转为 Asia/Shanghai']
    end_time: Annotated[str | None, '结束 ISO8601']
    duration_sec: Annotated[float | None, '训练时长秒']
    distance: Annotated[float | None, '距离值']
    distance_units: Annotated[str | None, '距离单位，不能默认米']
Workout: TypeAlias = Annotated[_Workout, {'additionalProperties': True}]

class Workouts(TypedDict, total=False):
    items: Required[Annotated[list[Workout], '本页训练']]
    total: Required[Annotated[int, '匹配总数']]
    offset: Required[Annotated[int, '0起始偏移']]
    has_more: Required[Annotated[bool, '是否有更多']]

class _Detail(TypedDict, total=False):
    id: Annotated[str, '训练 UUID']
    name: Annotated[str, '训练名']
    workout: Annotated[Workout, '训练记录']
    detail: Annotated[DynamicObject | None, '上游训练完整详情，未同步则为 null']
    detail_unavailable: Annotated[bool, '上游详情是否不存在']
    sets: Annotated[list[DynamicObject] | DynamicObject | None, '训练组明细，结构由训练类型决定，未同步为null']
    sets_unavailable: Annotated[bool, '组明细是否不存在']
    records: Annotated[list[DynamicObject], '平台记录明细']
Detail: TypeAlias = Annotated[_Detail, {'additionalProperties': True}]

class _Report(TypedDict, total=False):
    path: Required[Annotated[str, '工作空间报告 PNG 路径']]
    format: Required[Annotated[str, 'png']]
    timezone: Required[Annotated[str, '图表时间的 IANA 时区']]
    delivery: Required[Annotated[str, '发布方式说明']]
Report: TypeAlias = Annotated[_Report, {'additionalProperties': True}]

R_freereps_workouts: TypeAlias = Workouts
R_freereps_workout_detail: TypeAlias = Detail
R_freereps_activity: TypeAlias = DynamicJSON
R_freereps_metrics: TypeAlias = DynamicJSON
R_freereps_sleep: TypeAlias = DynamicJSON
R_freereps_status: TypeAlias = DynamicObject
R_freereps_workout_report: TypeAlias = Report

RESULTS = {'freereps_workouts': R_freereps_workouts, 'freereps_workout_detail': R_freereps_workout_detail, 'freereps_activity': R_freereps_activity, 'freereps_metrics': R_freereps_metrics, 'freereps_sleep': R_freereps_sleep, 'freereps_status': R_freereps_status, 'freereps_workout_report': R_freereps_workout_report}
