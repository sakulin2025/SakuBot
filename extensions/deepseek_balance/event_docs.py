from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = 'balance_low.<provider_id>.<currency>；动态部分依次为框架供应商 ID 和币种，例如 balance_low.deepseek.CNY。'
