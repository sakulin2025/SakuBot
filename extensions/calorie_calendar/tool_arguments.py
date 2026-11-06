"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_calorie_record1 = TypedDict(
    'A_calorie_record1',
    {
        'action': Required[Annotated[Literal['add', 'update', 'delete'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '修改或删除时提供记录 ID'}]],
        'date': NotRequired[Annotated[str, {'description': '日期 YYYY-MM-DD，新增时可留空表示今天'}]],
        'kind': NotRequired[Annotated[Literal['intake', 'expenditure'], {'description': 'intake 表示摄入，expenditure 表示消耗'}]],
        'label': NotRequired[Annotated[str, {'description': '餐次、消耗类型或自定义标签'}]],
        'kcal': NotRequired[Annotated[float, {'minimum': 0, 'maximum': 100000, 'description': '本条记录热量，单位千卡 kcal，必须为非负数'}]],
        'estimated': NotRequired[Annotated[bool, {'description': '是否为估算值；使用可靠营养标签或设备实测时通常为false'}]],
        'note': NotRequired[Annotated[str, {'description': '详情描述：具体食物、份量、估算依据或修正说明；追加食物时保留并更新已有详情'}]],
        'source': NotRequired[Annotated[str, {'description': '数据来源，例如用户、设备、品牌营养表或估算'}]],
    },
    total=False,
)

A_calorie_record: TypeAlias = Annotated[A_calorie_record1, {'additionalProperties': False}]

A_calorie_report2 = TypedDict(
    'A_calorie_report2',
    {
        'date': NotRequired[Annotated[str, {'description': '单日 YYYY-MM-DD'}]],
        'start': NotRequired[Annotated[str, {'description': '开始日期 YYYY-MM-DD'}]],
        'end': NotRequired[Annotated[str, {'description': '结束日期 YYYY-MM-DD'}]],
    },
    total=False,
)

A_calorie_report: TypeAlias = Annotated[A_calorie_report2, {'additionalProperties': False}]

A_calorie_confirm3 = TypedDict(
    'A_calorie_confirm3',
    {
        'date': NotRequired[Annotated[str, {'description': '日期 YYYY-MM-DD，留空表示今天'}]],
        'confirmed': Required[Annotated[bool, {'description': '是否将该日标为信息完整并纳入统计；后续修改记录不会自动改变此标志'}]],
    },
    total=False,
)

A_calorie_confirm: TypeAlias = Annotated[A_calorie_confirm3, {'additionalProperties': False}]

ARGUMENTS = {'calorie_record': A_calorie_record, 'calorie_report': A_calorie_report, 'calorie_confirm': A_calorie_confirm}
