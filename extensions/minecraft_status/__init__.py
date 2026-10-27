import asyncio
import json
from pathlib import Path
from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection, settings_section, fields_schema
import time
import re
from uuid import uuid4
from .client import StatusClient, PluginError, address, stamp
from .polling import Polling, KINDS


class Extension(Polling, Plugin):
    name = 'minecraft_status'

    def setup(self):
        self.config=self.configure({'poll_enabled':True,'poll_interval_minutes':5,'offline_confirmations':2})
        self.lock=asyncio.Lock();self.client=StatusClient();self.setup_polling()
        self.fields=[field('poll_enabled','轮询','boolean'),field('poll_interval_minutes','间隔 · 分钟','number',min=1,max=1440),field('offline_confirmations','不可达确认次数','number',min=1,max=10)]
        self.function(self.servers_tool,name='minecraft_servers');self.function(self.status_tool,name='minecraft_status');self.function(self.alerts_tool,name='minecraft_alerts')
        self.management('Minecraft',[collection('servers','服务器',[field('name','名称',required=True),field('address','地址',required=True),field('alias','别名'),field('description','描述','text'),field('edition','版本','select',default='java',options=[{'value':'java','label':'Java'},{'value':'bedrock','label':'基岩版'}])],columns=[field('name','名称'),field('address','地址'),field('alias','别名'),field('edition','版本'),field('status','最近观测')],row_commands=[{'id':'query','label':'查询'}],commands=[{'id':'query','label':'查询全部'}]),collection('alerts','提醒',[field('server_id','服务器','select',options_from='servers'),field('kind','类型','select',options=[{'value':k,'label':v} for k,v in KINDS.items()]),field('threshold','人数阈值','number',default=1,min=1),field('target','目的地',default='main'),field('enabled','启用','boolean',default=True)]),collection('history','事件',[field('at','时间'),field('server_name','服务器'),field('text','事件'),field('status','状态')],create=False,edit=False,remove=False),settings_section(self.fields,label='轮询设置')],self.view,self.manage)
    async def start(self): self.background(self.poll_loop())
    def prompt_context(self,invocation):
        return 'Minecraft 服务器目录按需使用 minecraft_servers 查询，实时状态使用 minecraft_status；不可达不等于确定关服，玩家样本可能不完整。只有配置的监控规则触发时才主动提醒。'
    async def view(self):
        state=await self.management_state()
        for entry in state['notification_history']:
            event=self.event_status('minecraft-event:'+str(entry.get('event_id','')))
            entry['status']=event['status'] if event else '已迁移'
        return {'data':{'servers':state['items'],'alerts':state['alerts'],'history':state['notification_history'],'config':self.config.public([f['key'] for f in self.fields])}}
    async def manage(self,data):
        section,key,value=data['section'],data.get('key',''),dict(data.get('value',{}))
        if section=='config':
            self.config.patch(value,fields_schema(self.fields));self.poll_wakeup.set();return {'saved':True}
        if section=='servers':
            if data['action']=='command':return await self.query_servers(reference=key,refresh=True)
            return await self.manage_records('remove' if data['action']=='remove' else 'update' if key else 'add',key,value)
        if section=='alerts':
            server=value.pop('server_id','')
            return await self.manage_alerts('remove' if data['action']=='remove' else 'update' if key else 'add',server,key,value,default_target='main')
        raise ValueError('操作无效')

    async def records(self):
        records = self.state.get('servers', {})
        if not isinstance(records, dict):
            raise PluginError('服务器存储格式错误，请检查插件数据，不会自动清空记录。')
        return records

    @staticmethod
    def resolve(records, reference):
        if not isinstance(reference, str) or not reference.strip():
            raise PluginError('请指定服务器 ID、名称、别名或保存的地址。')
        reference = reference.strip()
        if reference in records:
            return records[reference]
        matches = [r for r in records.values() if reference.casefold() in {str(r.get(key, '')).casefold() for key in ('name', 'alias', 'address')}]
        if not matches:
            raise PluginError('没有找到该服务器，请先列出条目；临时地址查询请使用 address 参数。')
        if len(matches) != 1:
            raise PluginError('匹配到多个条目，请使用列表中的准确 ID。')
        return matches[0]

    @staticmethod
    def public(record):
        return {**record, 'display_name': record.get('alias') or record['name']}

    async def manage_records(self, action, reference='', details=None):
        async with self.lock:
            records = await self.records()
            if action == 'list':
                return {'items': [self.public(r) for r in records.values()], 'total': len(records)}
            if action == 'get':
                return self.public(self.resolve(records, reference))
            if action not in ('add', 'update', 'remove'):
                raise PluginError('action 只能为 list/get/add/update/remove。')
            previous = None if action == 'add' else self.resolve(records, reference)
            updated = dict(records)
            if action == 'remove':
                updated.pop(previous['id'])
                self.state.set('servers', updated)
                self.client.forget(previous)
                await self.clear_polling_record(previous['id'], remove_rules=True)
                return {'removed': previous['id']}
            if not isinstance(details, dict) or not details or set(details) - {'name', 'address', 'ip', 'alias', 'description', 'edition'}:
                raise PluginError('details 可填写 name、address（或 ip）、alias、description、edition。')
            if any((not isinstance(value, str) for value in details.values())):
                raise PluginError('条目字段必须为文本。')
            details = {key: value.strip() for key, value in details.items()}
            if 'ip' in details:
                if 'address' in details and details['address'] != details['ip']:
                    raise PluginError('ip 与 address 不一致，请只提供一个地址。')
                details['address'] = details.pop('ip')
            item = dict(previous) if previous else {'id': uuid4().hex[:12], 'created_at': stamp(), 'alias': '', 'description': '', 'edition': 'java'}
            item.update(details)
            if not item.get('name') or len(item['name']) > 100:
                raise PluginError('请填写服务器名称，最多100字。')
            item['address'] = address(item.get('address'))
            if item.get('edition') not in ('java', 'bedrock'):
                raise PluginError('edition 请选择 java 或 bedrock。')
            if len(item['alias']) > 100 or len(item['description']) > 8000:
                raise PluginError('别名最多100字，描述最多8000字。')
            identities = {item['name'].casefold(), item['alias'].casefold()} - {''}
            if any((other['id'] != item['id'] and identities.intersection({other['name'].casefold(), other.get('alias', '').casefold()} - {''}) for other in records.values())):
                raise PluginError('名称或别名已被其他服务器使用，请换一个名称。')
            item['updated_at'] = stamp()
            updated[item['id']] = item
            self.state.set('servers', updated)
            if previous and self.client.key(previous) != self.client.key(item):
                self.client.forget(previous)
                await self.clear_polling_record(item['id'])
            return {'saved': True, 'server': self.public(item)}

    async def query_servers(self, reference='', references=None, direct_address='', edition='java', refresh=False):
        if not isinstance(refresh, bool):
            raise PluginError('refresh 必须为布尔值。')
        records = await self.records()
        if direct_address:
            if reference or references:
                raise PluginError('临时地址查询与已保存条目查询请分开调用。')
            if edition not in ('java', 'bedrock'):
                raise PluginError('edition 请选择 java 或 bedrock。')
            host = address(direct_address)
            targets = [{'id': '', 'name': host, 'address': host, 'edition': edition, 'alias': '', 'description': ''}]
        else:
            if references is not None and (not isinstance(references, list) or any((not isinstance(r, str) or not r.strip() for r in references))):
                raise PluginError('servers 必须是服务器 ID、名称或别名的文本列表。')
            refs = list(dict.fromkeys(([reference] if reference else []) + (references or [])))
            targets = list({r['id']: r for r in (self.resolve(records, ref) for ref in refs)}.values()) if refs else list(records.values())
        if len(targets) > 100:
            raise PluginError('单次最多查询100台服务器，请指定要查询的条目。')
        probes = {}

        async def query(record):
            key = self.client.key(record)
            if key not in probes:
                probes[key] = asyncio.create_task(self.client.query(record, refresh))
            return {'server': self.public(record), **await probes[key]}
        return {'items': await asyncio.gather(*(query(record) for record in targets)), 'total': len(targets), 'note': '状态由服务器自报，查询失败不能直接断言关服；玩家样本可能不完整。'}

    async def management_state(self):
        records = await self.records()
        polls = await self.poll_data()

        def status(record):
            cached = self.client.peek(record)
            observation = polls['observations'].get(record['id'], {})
            return cached or (observation.get('result') if observation.get('signature') == list(self.client.key(record)) else None)
        return {'items': [{**self.public(r), 'status': status(r)} for r in records.values()], **await self.alert_state(records=records, polls=polls)}

    async def servers_tool(self, action: str='list', server: str='', details: dict=None):
        """用户管理 Minecraft 服务器的持久条目，与可视化页面共用。保存和编辑不查询服务器。用户提供或确认的信息才记入条目。查询结果始终带名称、别名、描述和地址。

                Args:
                    action(string): list/get/add/update/remove。
                    server(string): get/update/remove 的条目 ID、准确名称、别名或已保存地址；list/add 留空。
                    details(object): add 需要 name 与 address（或 ip，可含端口）；可填 alias、description、edition（java/bedrock，默认java）。update 仅传要改的字段；别名、描述空文本清空。Java 默认25565，基岩版默认19132；IPv6 带端口写 [IPv6]:端口。
                """
        try:
            return await self.manage_records(action, server, details)
        except PluginError as exc:
            return str(exc)

    async def alerts_tool(self, action: str='list', server: str='', rule_id: str='', details: dict=None):
        """用户设置 Minecraft 后台轮询和主动事件。默认每5分钟检查所有已保存条目；首次采样建立基线，规则只在变化时触发，持续满足不会重复触发。命中后唤起主 Agent，在统一主上下文中生成回复。规则与基线持久保存。关服默认连续2轮不可达才提醒，可能是网络异常。新规则不填 target 默认 main，不猜其他群号。保存规则不立即查询或唤起 AI。

                Args:
                    action(string): list/settings/add/update/remove。
                    server(string): add 的已保存服务器 ID、名称或别名；update 可改目标服务器，其他动作留空。
                    rule_id(string): update/remove 使用 list 中的准确提醒规则ID，其他动作留空。
                    details(object): settings 支持 enabled、interval_minutes（1到1440，默认5）、offline_confirmations（1到10，默认2）。add/update 支持 kind、enabled、target（main 或 private:QQ号/group:群号）、threshold。kind 为 players_joined（0变为有人）、players_reached（从低于threshold变为达到）、players_below（降至threshold以下）、players_increase、players_decrease、server_online、server_offline。threshold 为正整数，仅人数阈值类型使用。update 省略字段保留；新规则 target 省略则使用 main。
                """
        try:
            result = await self.manage_alerts(action, server, rule_id, details, default_target='main')
            return result
        except PluginError as exc:
            return str(exc)

    async def status_tool(self, server: str='', servers: list=None, address: str='', edition: str='java', refresh: bool=False):
        """用户按需主动查询 Minecraft 服务器基本信息：在线响应、版本、MOTD、在线/最大人数、延迟及服务器自报玩家样本；基岩版还可能返回地图、游戏模式。按目录中的名称和别名识别目标，不猜地址。结果始终带本地名称、别名和描述。只读状态查询，不登录玩家、不执行指令。状态缓存30秒，checked_at 是实际查询时间；不可达不能直接断言已关服，玩家样本可能不完整或为自定义文字。

                Args:
                    server(string): 单个已保存条目的 ID、名称、别名或地址；与 servers 都留空时查询全部已保存条目。
                    servers(array[string]): 多台已保存服务器的 ID、名称或别名，最多100台，结果分别返回。
                    address(string): 临时查询未保存的 IP/域名，可带端口；填写时 server/servers 留空，不自动保存条目。
                    edition(string): 仅临时地址使用，java/bedrock；已保存条目沿用自身的版本类型。
                    refresh(bool): true 跳过30秒缓存，立即查询。
                """
        try:
            return await self.query_servers(server, servers, address, edition, refresh)
        except PluginError as exc:
            return str(exc)

    def settings_saved(self):
        self.poll_wakeup.set()
