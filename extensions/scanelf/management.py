"""Remote ScanElf device administration; local memory remains a separate service."""
from .tool_types import R_scanelf_device_manage
from .client import PluginError, normalize_mac


def validate_details(details):
    if not isinstance(details, dict) or not details or set(details) - {'name', 'tags', 'favorite', 'resident', 'ignored'}:
        raise PluginError('details 仅支持 name、tags、favorite、resident、ignored，至少提供一项。')
    if 'name' in details and (not isinstance(details['name'], str) or len(details['name']) > 80):
        raise PluginError('设备名称最多 80 字。')
    if any(type(details[key]) is not bool for key in ('favorite', 'resident', 'ignored') if key in details):
        raise PluginError('favorite、resident、ignored 必须为布尔值。')
    if 'tags' in details:
        tags = details['tags']
        if not isinstance(tags, list) or len(tags) > 20 or any(not isinstance(t, str) or not 1 <= len(t.strip()) <= 32 for t in tags):
            raise PluginError('标签最多 20 项，每项 1～32 字。')
    return details


class Management:
    async def refresh_managed(self):
        rows = await self.client.management_devices()
        _, memories = await self.memories()
        self.managed_devices = [{**row, **self.enrich(row, memories), 'ignored': bool(row.get('ignored')),
                                 'tags_text': ', '.join(row.get('tags', []))} for row in rows]
        self.last_devices = [row for row in self.managed_devices if not row['ignored']]
        return self.managed_devices

    async def manage_remote(self, data):
        if data['action'] == 'command' and data.get('command') == 'refresh':
            return await self.refresh_managed()
        if data['action'] != 'save': raise PluginError('设备管理操作无效。')
        value = dict(data['value'])
        mac = normalize_mac(value.pop('mac', ''))
        if not mac: raise PluginError('请输入有效的设备 MAC。')
        key = normalize_mac(data.get('key', ''))
        if data.get('key') and mac != key: raise PluginError('已有设备的 MAC 不可修改。')
        tags = value.pop('tags_text', '')
        if not isinstance(tags, str): raise PluginError('标签须为逗号分隔的字符串。')
        value['tags'] = [t.strip() for t in tags.replace('，', ',').split(',') if t.strip()]
        result = await self.client.save_device(mac, validate_details(value), create=not bool(data.get('key')))
        # Preserve the successful write result even if the subsequent list refresh is unavailable.
        self.managed_devices = [row for row in self.managed_devices if row['mac'] != mac]
        _, memories = await self.memories()
        self.managed_devices.append({**result, **self.enrich(result, memories), 'ignored': bool(result.get('ignored')),
                                     'tags_text': ', '.join(result.get('tags', []))})
        self.last_devices = [row for row in self.managed_devices if not row.get('ignored')]
        return {'saved': True, 'device': result}

    async def device_manage(self, action: str='list', device: str='', details: dict=None, limit: int=50, offset: int=0) -> R_scanelf_device_manage:
        """管理 ScanElf 上游设备，直接修改 ScanElf，而非 SakuBot 本地别名。支持新增、改名、标签、收藏、常驻、忽略和恢复。list 明确返回全部设备（包括忽略），get 查询单设备。add 只创建离线档案，不伪造扫描状态或历史；update 仅更新提供的字段，ignored=false 恢复设备。无删除历史功能。只有用户提供或确认的信息才写入，不猜 MAC、设备归属或标签。网络中断可能已写入，先 get 确认再决定重试。设备描述仍用 scanelf_device_memory。

        Args:
            action(string): list/get/add/update。
            device(string): add 必须为完整 MAC；get/update 可用实际名称、本地别名或 MAC，重名时使用 MAC。
            limit(int): list 每页1～100条。
            offset(int): list 非负分页偏移。
            details(object): add/update 可含 name（最多80字）、tags（最多20项，每项1～32字）、favorite/resident/ignored（布尔值）；update 省略字段保留。空名称/空 tags 清空对应字段。
        """
        if action not in ('list', 'get', 'add', 'update'): raise PluginError('action 必须为 list/get/add/update。')
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise PluginError('limit 必须为1～100，offset 必须非负。')
        if action == 'list':
            rows = await self.refresh_managed()
            return {'items': rows[offset:offset+limit], 'total': len(rows), 'includes_ignored': True, 'offset': offset, 'has_more': offset+limit < len(rows)}
        mac = normalize_mac(device)
        if action == 'add':
            if not mac: raise PluginError('新增设备必须提供有效 MAC。')
        else:
            if not mac:
                rows = await self.client.management_devices()
                _, memories = await self.memories()
                mac = self.resolve(device, rows, memories)['mac']
            current = await self.client.device(mac)
            if action == 'get':
                _, memories = await self.memories()
                return {**current, **self.enrich(current, memories), 'ignored': bool(current.get('ignored'))}
        result = await self.client.save_device(mac, validate_details(details or ({'name': ''} if action == 'add' else {})), create=action == 'add')
        self.managed_devices = []
        self.last_devices = [row for row in self.last_devices if row['mac'] != mac]
        return {'saved': True, 'device': result}
