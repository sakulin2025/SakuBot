from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = '<事件分类>.<device_id>；星号为终端设备 ID，例如 wake.speaker-1。'
