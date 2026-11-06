from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = '<事件分类>.<entity_id>；星号替换为完整 HA 实体 ID（包含域名），例如 entity_turned_on.light.lab。'
