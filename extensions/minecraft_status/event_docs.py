from sakubot.contracts import schema_from_type
from .event_types import EventData, Parameters0, Parameters1, Parameters2, Parameters3, Parameters4, Parameters5, Parameters6, Parameters7, Parameters8, Parameters9

EVENT = schema_from_type(EventData)
PARAMETER_TYPES = {'observation': Parameters0, 'players_reached': Parameters1, 'players_below': Parameters2, 'server_online': Parameters3, 'server_offline': Parameters4, 'status_changed': Parameters5, 'players_changed': Parameters6, 'players_increased': Parameters7, 'players_decreased': Parameters8, 'players_joined': Parameters9}

def parameters(family):
    return schema_from_type(PARAMETER_TYPES[family])

ID_DESCRIPTION = '<事件分类>.<server_id>；星号为保存条目 ID，例如 players_joined.survival。'
