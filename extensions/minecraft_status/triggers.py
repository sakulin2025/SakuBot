"""Server-scoped generic observations and state/player transition families."""
from sakubot.plugin import object_schema

FAMILIES = {
    'observation': '服务器状态与人数', 'status_changed': '服务器状态变化',
    'server_online': '服务器开服', 'server_offline': '服务器疑似关服',
    'players_changed': '在线人数变化', 'players_increased': '在线人数增加',
    'players_decreased': '在线人数减少', 'players_joined': '服务器从无人到有人',
    'players_reached': '在线人数达到阈值', 'players_below': '在线人数跌破阈值',
}


def register(plugin):
    async def options():
        return {'server_id': [{'value': key, 'label': row.get('alias') or row['name']}
                              for key, row in (await plugin.records()).items()]}

    def matcher(family):
        def match(event, params):
            if params.get('server_id') and event['server_id'] != params['server_id']:
                return False
            if family == 'observation':
                return params.get('change', 'observation') == 'observation' or params['change'] in event['changes']
            before, after = event['previous'].get('players'), event['current'].get('players')
            threshold = params.get('threshold', 1)
            if family == 'players_reached': return before < threshold <= after
            if family == 'players_below': return before >= threshold > after
            return True
        return match

    schema = object_schema({'server_id': {'type': 'string'}, 'server': {'type': 'object'},
        'previous': {'type': 'object'}, 'current': {'type': 'object'},
        'changes': {'type': 'array', 'items': {'type': 'string'}}}, ('server_id', 'previous', 'current', 'changes'))
    for family, title in FAMILIES.items():
        fields = {'server_id': {'type': 'string', 'title': '服务器 · 留空全部'}}
        if family == 'observation':
            fields['change'] = {'type': 'string', 'title': '触发条件', 'enum': ['observation', 'status', 'players'], 'default': 'observation'}
        if family in ('players_reached', 'players_below'):
            fields['threshold'] = {'type': 'integer', 'title': '人数阈值', 'minimum': 1, 'default': 1}
        plugin.trigger_source(family + '.*', title, object_schema(fields), schema, options=options,
            match=matcher(family), legacy_ids=('observation',) if family == 'observation' else ())


def publish(plugin, record, previous, current, changes):
    payload = {'server_id': record['id'], 'server': plugin.public(record),
               'previous': previous, 'current': current, 'changes': changes}
    families = ['observation']
    if previous.get('stable') in ('online', 'offline') and current.get('stable') in ('online', 'offline') and 'status' in changes:
        families.extend(['status_changed', 'server_' + current['stable']])
    before, after = previous.get('players'), current.get('players')
    if previous.get('stable') == current.get('stable') == 'online' and type(before) is int and type(after) is int and before != after:
        families.extend(['players_changed', 'players_increased' if after > before else 'players_decreased',
                         'players_reached' if after > before else 'players_below'])
        if before == 0 and after > 0: families.append('players_joined')
    for family in families:
        plugin.publish_trigger(family + '.' + record['id'], payload,
            uid=family + ':' + record['id'] + ':' + str(current['checked_at']))
