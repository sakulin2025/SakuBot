"""Device source registration; transport and transition detection live separately."""
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

    plugin.trigger_source('device_state_changed','设备上下线',
        object_schema({'mac':{'type':'string','title':'设备 MAC'},'state':{'type':'string','title':'状态','enum':['any','online','offline'],'default':'any'}}),
        object_schema({'mac':{'type':'string'},'online':{'type':'boolean'},'previous_online':{'type':'boolean'},'device':{'type':'object'},'at':{'type':'number'}},('mac','online')),
        subscribe=plugin.device_watcher.subscribe,match=match,options=options,validate=validate)
