from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = 'slash.<command>；星号为去掉前导斜杠的指令名称，例如 slash.weather 对应 /weather。'
