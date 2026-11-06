"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_deepseek_balance1 = TypedDict(
    'A_deepseek_balance1',
    {
        'provider_id': NotRequired[Annotated[str, {'description': '可选供应商 ID，留空使用当前 Agent 的模型供应商。', 'default': ''}]],
    },
    total=False,
)

A_deepseek_balance: TypeAlias = Annotated[A_deepseek_balance1, {'additionalProperties': False}]

ARGUMENTS = {'deepseek_balance': A_deepseek_balance}
