from sakubot.contracts import schema_from_type
from .event_types import EventData, EventParameters

EVENT = schema_from_type(EventData)
PARAMETERS = schema_from_type(EventParameters)

ID_DESCRIPTION = '<事件分类>.<day>；星号是 Asia/Shanghai 日期 YYYY-MM-DD，例如 record_changed.2026-11-06。'
