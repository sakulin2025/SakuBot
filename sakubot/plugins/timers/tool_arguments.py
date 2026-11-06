"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_schedule_manage1 = TypedDict(
    'A_schedule_manage1',
    {
        'action': Required[Annotated[Literal['list', 'save', 'delete'], {'description': '本工具要执行的动作；仅接受枚举列出的操作'}]],
        'id': NotRequired[Annotated[str, {'description': '更新或删除的任务 ID'}]],
        'name': NotRequired[Annotated[str, {'description': '定时任务显示名称'}]],
        'content': NotRequired[Annotated[str, {'description': 'wake 提示词或 context/notify 正文；script 模式可省略'}]],
        'script_id': NotRequired[Annotated[str, {'description': 'script 模式的脚本 ID'}]],
        'script_params': NotRequired[Annotated[dict[str, object], {'description': '交给指定脚本的参数对象，按该脚本参数类型校验'}]],
        'mode': NotRequired[Annotated[Literal['context', 'wake', 'notify', 'script'], {'description': 'wake 唤醒智能体、context 加上下文、notify 直接通知、script 执行脚本'}]],
        'at': NotRequired[Annotated[str, {'description': '一次性时间，需带时区，例如 2026-10-26T09:00:00+08:00'}]],
        'interval_seconds': NotRequired[Annotated[int, {'minimum': 0, 'maximum': 31536000, 'description': '重复间隔秒数；与 at/daily_time 三选一'}]],
        'daily_time': NotRequired[Annotated[str, {'description': '每日时间，格式 HH:MM'}]],
        'timezone': NotRequired[Annotated[str, {'description': 'IANA 时区，例如 Asia/Shanghai'}]],
        'send_result_to_source': NotRequired[Annotated[bool, {'description': '是否发送结果或通知到主对话源，默认 true'}]],
        'enabled': NotRequired[Annotated[bool, {'description': '是否接受未来定时触发'}]],
        'include_context': NotRequired[Annotated[bool, {'description': '是否把固定通知加入主上下文；默认false，避免常规后台数据污染上下文'}]],
    },
    total=False,
)

A_schedule_manage: TypeAlias = Annotated[A_schedule_manage1, {'additionalProperties': False}]

ARGUMENTS = {'schedule_manage': A_schedule_manage}
