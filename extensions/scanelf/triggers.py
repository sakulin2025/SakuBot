"""Device source registration; transport and transition detection live separately."""
from .event_docs import PARAMETERS, EVENT, ID_DESCRIPTION
from sakubot.plugin import object_schema

from .client import normalize_mac
from .watcher import DeviceWatcher


def register(plugin):
    plugin.device_watcher = DeviceWatcher(plugin)

    def match(event, params):
        return ((not params.get('mac') or normalize_mac(params['mac']) == event['mac'])
                and (params.get('state', 'any') == 'any'
                     or event['online'] == (params['state'] == 'online')))

    def validate(params):
        if params.get('mac') and normalize_mac(params['mac']) is None:
            raise ValueError('请填写有效的设备 MAC')

    async def options():
        _, memories = await plugin.memories()
        devices = {row['mac']: dict(row) for row in plugin.last_devices}
        for mac, memory in memories.items():
            devices.setdefault(mac, {'mac': mac}).update(memory)
        return {'mac': [{'value': mac, 'label': (row.get('alias') or row.get('name') or mac) + ' · ' + mac}
                        for mac, row in devices.items()]}

    for family, title in [('device_state_changed', '设备上下线'), ('device_online', '设备上线'),
                          ('device_offline', '设备下线'), ('device_discovered', '发现新设备')]:
        plugin.trigger_source(family + '.*', title,
            PARAMETERS, EVENT, id_description=ID_DESCRIPTION,
            subscribe=plugin.device_watcher.subscribe,match=match,options=options,validate=validate,
            legacy_ids=(family,) if family == 'device_state_changed' else ())
