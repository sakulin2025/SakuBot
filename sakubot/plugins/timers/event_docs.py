from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = 'schedule.<timing>；星号为 interval、daily 或 once，例如 schedule.daily。'
