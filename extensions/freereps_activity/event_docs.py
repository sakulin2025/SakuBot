from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = 'workout_added.<workout_id>；星号是新增训练的唯一 ID，例如 workout_added.workout-1。'
