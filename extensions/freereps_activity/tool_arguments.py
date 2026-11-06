"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_freereps_workouts1 = TypedDict(
    'A_freereps_workouts1',
    {
        'start': NotRequired[Annotated[str, {'description': '开始日期或带时区的 ISO 时间；日期按 Asia/Shanghai 理解，默认最近七天。', 'default': ''}]],
        'end': NotRequired[Annotated[str, {'description': '结束日期或带时区的 ISO 时间；日期按 Asia/Shanghai 理解，默认当前时间。', 'default': ''}]],
        'workout_type': NotRequired[Annotated[str, {'description': 'FreeReps 训练类型，留空全部。', 'default': ''}]],
        'limit': NotRequired[Annotated[int, {'description': '每页条数，1 至 100。', 'default': 30}]],
        'offset': NotRequired[Annotated[int, {'description': '分页偏移，从 0 开始。', 'default': 0}]],
    },
    total=False,
)

A_freereps_workouts: TypeAlias = Annotated[A_freereps_workouts1, {'additionalProperties': False}]

A_freereps_workout_detail2 = TypedDict(
    'A_freereps_workout_detail2',
    {
        'id': Required[Annotated[str, {'description': 'FreeReps 训练 UUID。'}]],
        'include_sets': NotRequired[Annotated[bool, {'description': '是否同时查询训练动作与组数。', 'default': True}]],
        'start': NotRequired[Annotated[str, {'description': '合成训练的开始时间，使用列表提供的 ISO 时间。', 'default': ''}]],
        'end': NotRequired[Annotated[str, {'description': '合成训练的结束时间，使用列表提供的 ISO 时间。', 'default': ''}]],
    },
    total=False,
)

A_freereps_workout_detail: TypeAlias = Annotated[A_freereps_workout_detail2, {'additionalProperties': False}]

A_freereps_activity3 = TypedDict(
    'A_freereps_activity3',
    {
        'start': NotRequired[Annotated[str, {'default': '', 'description': '起始日期 YYYY-MM-DD 或带时区 ISO8601；具体默认范围见工具描述'}]],
        'end': NotRequired[Annotated[str, {'default': '', 'description': '结束日期 YYYY-MM-DD 或带时区 ISO8601；具体默认范围见工具描述'}]],
    },
    total=False,
)

A_freereps_activity: TypeAlias = Annotated[A_freereps_activity3, {'additionalProperties': False}]

A_freereps_metrics4 = TypedDict(
    'A_freereps_metrics4',
    {
        'metric': NotRequired[Annotated[str, {'default': '', 'description': '指标名称，按 FreeReps 实际支持的指标选择'}]],
        'start': NotRequired[Annotated[str, {'default': '', 'description': '起始日期 YYYY-MM-DD 或带时区 ISO8601；具体默认范围见工具描述'}]],
        'end': NotRequired[Annotated[str, {'default': '', 'description': '结束日期 YYYY-MM-DD 或带时区 ISO8601；具体默认范围见工具描述'}]],
        'mode': NotRequired[Annotated[str, {'default': 'latest', 'description': 'history 查询历史，stats 查询统计，其他模式按工具说明'}]],
    },
    total=False,
)

A_freereps_metrics: TypeAlias = Annotated[A_freereps_metrics4, {'additionalProperties': False}]

A_freereps_sleep5 = TypedDict(
    'A_freereps_sleep5',
    {
        'start': NotRequired[Annotated[str, {'default': '', 'description': '起始日期 YYYY-MM-DD 或带时区 ISO8601；具体默认范围见工具描述'}]],
        'end': NotRequired[Annotated[str, {'default': '', 'description': '结束日期 YYYY-MM-DD 或带时区 ISO8601；具体默认范围见工具描述'}]],
    },
    total=False,
)

A_freereps_sleep: TypeAlias = Annotated[A_freereps_sleep5, {'additionalProperties': False}]

A_freereps_status6 = TypedDict(
    'A_freereps_status6',
    {
        'include_sources': NotRequired[Annotated[bool, {'default': False, 'description': '是否同时查询来源同步信息；false 只查询基础状态'}]],
    },
    total=False,
)

A_freereps_status: TypeAlias = Annotated[A_freereps_status6, {'additionalProperties': False}]

A_freereps_workout_report7 = TypedDict(
    'A_freereps_workout_report7',
    {
        'id': Required[Annotated[str, {'description': 'FreeReps 训练 UUID；先通过 freereps_workouts 查询。'}]],
    },
    total=False,
)

A_freereps_workout_report: TypeAlias = Annotated[A_freereps_workout_report7, {'additionalProperties': False}]

ARGUMENTS = {'freereps_workouts': A_freereps_workouts, 'freereps_workout_detail': A_freereps_workout_detail, 'freereps_activity': A_freereps_activity, 'freereps_metrics': A_freereps_metrics, 'freereps_sleep': A_freereps_sleep, 'freereps_status': A_freereps_status, 'freereps_workout_report': A_freereps_workout_report}
