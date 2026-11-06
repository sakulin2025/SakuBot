"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Balance(TypedDict, total=False):
    currency: Required[Annotated[str | None, '币种 CNY/USD 等，未提供则 null']]
    total_balance: Required[Annotated[str | None, '总余额，十进制金额字符串，单位由 currency 决定']]
    granted_balance: Required[Annotated[str | None, '赠送余额，十进制金额字符串']]
    topped_up_balance: Required[Annotated[str | None, '充值余额，十进制金额字符串']]

class Result(TypedDict, total=False):
    provider_id: Required[Annotated[str, '框架供应商 ID']]
    is_available: Required[Annotated[bool, '余额是否足够继续调用']]
    balance_infos: Required[Annotated[list[Balance], '按币种分别列出的余额']]
    fetched_at: Required[Annotated[str, '查询时间，ISO8601 含时区']]

R_deepseek_balance: TypeAlias = Result

RESULTS = {'deepseek_balance': R_deepseek_balance}
