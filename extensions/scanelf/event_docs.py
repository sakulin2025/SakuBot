from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = '<事件分类>.<mac>；星号为规范化的完整 MAC，例如 device_online.AA:BB:CC:DD:EE:FF。'
