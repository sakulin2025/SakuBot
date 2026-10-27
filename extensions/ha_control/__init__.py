import asyncio
import json
from pathlib import Path
from sakubot.plugin import Plugin
from sakubot.plugin_support import field, collection, settings_section, fields_schema
from .client import HomeAssistant, PluginError


class Extension(Plugin):
    name = 'ha_control'

    def setup(self):
        self.config = self.configure({'base_url':'','token':'','timeout':30,'initialized':False,'rooms':[],'entities':[],'operation_manual':''},secrets=('token',))
        self.client = HomeAssistant(self.config,self.data_dir,self.config.save)
        self.lock=asyncio.Lock()
        self.fields=[field('base_url','URL',required=True),field('token','Token','secret'),field('timeout','超时 · 秒','number',min=1,max=300)]
        for name, method in [('ha_initialize',self.initialize_tool),('ha_query',self.query),('ha_control',self.control),('ha_manual',self.operation_manual)]:self.function(method,name=name)
        policies=[{'value':x,'label':y} for x,y in [('controllable','可控制'),('readonly','只读'),('ignore','忽略')]]
        self.management('Home Assistant',[collection('entities','实体',[field('entity_id','实体 ID',readonly=True),field('name','名称',readonly=True),field('area','房间',readonly=True),field('alias','别名'),field('group','分组'),field('policy','策略','select',options=policies)],key='entity_id',create=False,remove=False),collection('rooms','房间',[field('area','ID',readonly=True),field('name','名称',readonly=True),field('enabled','启用','boolean')],key='area',create=False,remove=False),settings_section([field('content','用户要求与操作手册','text')],label='操作手册',id='manual'),settings_section(self.fields)],self.view,self.manage)
    def availability(self):
        ok=bool(self.config.get('base_url') and self.config.get('token'))
        return {'available':ok,'reason':'' if ok else '尚未配置 HA 连接'}
    def prompt_context(self, invocation):
        return 'HA 名称、别名和用途优先于技术类型，switch 也可能是灯。设备目录和当前状态按需调用 ha_query；习惯拿不准先用 ha_manual 读操作手册，明确的日常操作不重复确认。'
    def view(self):return {'data':{'config':self.config.public([f['key'] for f in self.fields]),'manual':{'content':self.client.manual()},'rooms':self.config.get('rooms',[]),'entities':self.config.get('entities',[])}}
    async def manage(self,data):
        async with self.lock:
            section=data['section']; value=data['value']
            if section=='config':self.config.patch(value,fields_schema(self.fields));return {'saved':True}
            if section=='manual':
                if data.get('expected',{}).get('content') != self.client.manual():raise RuntimeError('手册已变化，请重新读取后合并')
                return self.client.update_manual('write',value['content'])
            key='entity_id' if section=='entities' else 'area'
            item=next((x for x in self.config[section] if x[key]==data['key']),None)
            if item is None:raise ValueError('条目已不存在')
            allowed={'alias','group','policy'} if section=='entities' else {'enabled'}
            if set(value)-allowed:raise ValueError('字段无效')
            if section=='entities' and value.get('policy') not in ('controllable','readonly','ignore'):raise ValueError('实体策略无效')
            item.update(value);self.config.save();return {'saved':True}

    async def initialize_tool(self, action: str='status', area: str='', enabled: bool=False, entity_id: str='', policy: str='', alias: str='', group: str='', confirmed: bool=False):
        """仅用户可用的 HA 初始化向导。配置好 URL/token 后用户说“开始HA初始化”即可调用。按房间逐步询问，禁止自动决定权限。scan→rooms→room→entities→policy/review_room→build。结果保存到插件配置页面。

                Args:
                    action(string): status/scan/rooms/entities/room/policy/review_room/build/reset。
                    area(string): 房间标识，未分配区域为 __unassigned__。
                    enabled(bool): room 操作是否启用房间。
                    entity_id(string): policy 操作的完整实体ID。
                    policy(string): controllable/readonly/ignore。
                    alias(string): policy 操作的别名，多个用 / 分隔，空字符串清空。
                    group(string): policy 操作的分组，空字符串清空。
                    confirmed(bool): 用户确认覆盖草稿、采纳本房间建议、发布或重置后才可为 true。
                """
        try:
            async with self.lock:
                result = await asyncio.to_thread(self.client.initialize, action, area, enabled, entity_id, policy, alias, group, confirmed)
            return result
        except PluginError as exc:
            return str(exc)

    async def query(self, entity_id: str='', match: str='', domain: str='', summary: bool=False):
        """查询已授权 HA 设备的实时状态，同时返回原名、HA friendly_name、别名、display_name、分组及实际技术类型 domain。按名称和用途识别设备：灯可能通过 switch 或 input_boolean 接入，并不一定是 light。问“灯有没有开”优先 match="灯" 且 domain 留空，不能只查 light 就断言没有灯。指定 light 时 related_entities 会补充名称、别名或分组含照明含义的授权开关。summary=true 也返回设备名字和状态。忽略或未启用房间中的实体完全不可见；未初始化拒绝查询。

                Args:
                    entity_id(string): 完整实体ID，留空列出允许的实体。
                    match(string): 原名、HA friendly_name、别名、区域、分组或ID关键词，例如 灯、左灯、顶灯。
                    domain(string): 可选的 HA 技术类型，多个用逗号分隔；按设备用途查询时优先留空，灯也可能属于 switch。
                    summary(bool): 返回按技术类型统计并保留设备名字、别名和状态，省略详细 attributes。
                """
        try:
            result = await asyncio.to_thread(self.client.query, entity_id, match, domain, summary)
            return result
        except PluginError as exc:
            return str(exc)

    async def control(self, entity_id: str='', action: str='', params: dict=None, entity_ids: list=None, preview: bool=False, force: bool=False):
        """按用户当前要求控制 HA 设备，支持一次操作多台。用户在任意平台、群聊和私聊均可使用，不绑定会话、不要求预览或二次确认。设备称呼、集体操作和习惯拿不准时先看 ha-user-manual 技能及 ha_manual；例如手册写明“开灯/关灯=实验室两盏顶灯一起操作”，就用 entity_ids 操作两台，不再问哪一盏。只记忆要求时调用 ha_manual，不要调用本工具。仅在用户主动要求预览时使用 preview=true。仍遵守已启用房间和实体的可控制策略，不从手册推断实时状态。

                Args:
                    entity_id(string): 单台设备的实际完整实体ID；批量操作可留空。
                    action(string): on/off/set。
                    params(object): set参数，brightness百分比/音量、temperature温度、mode模式、option选项、position位置、value数值；无参数用空对象。
                    entity_ids(array[string]): 多台设备的实际实体ID，使用相同动作和参数；可一次打开或关闭多盏灯，不要猜ID。
                    preview(bool): true 只返回计划、不操作设备；默认 false 按当前指令直接执行，无强制确认步骤。
                    force(bool): 用户明确要求控制诊断实体时为 true。
                """
        params = {} if params is None else params
        if not isinstance(params, dict):
            return 'params 必须是对象。'
        params = {k: v for k, v in params.items() if v is not None}
        try:
            targets = [] if entity_ids is None else entity_ids
            if not isinstance(targets, list) or any((not isinstance(eid, str) for eid in targets)):
                raise PluginError('entity_ids 必须是完整实体 ID 的列表。')
            targets = list(dict.fromkeys(([entity_id] if entity_id else []) + targets))
            if not targets:
                raise PluginError('请先根据设备目录和操作手册确定实际 entity_id 或 entity_ids。')
            async with self.lock:
                plans = [self.client.plan(eid, action, params, force) for eid in targets]
                if preview:
                    return {'preview': True, 'plans': plans}
                results = []
                for eid, plan in zip(targets, plans):
                    device = self.client.entity_metadata(self.client.entity(eid, control=True))
                    try:
                        result = await asyncio.to_thread(self.client.execute, plan)
                    except PluginError as exc:
                        result = {'success': False, 'error': str(exc), **plan}
                    results.append({**result, 'device': device})
            return {'success': all((item['success'] for item in results)), 'results': results}
        except (PluginError, TypeError, ValueError) as exc:
            return str(exc) if isinstance(exc, PluginError) else '控制参数无效，请检查数值类型。'

    async def operation_manual(self, action: str='read', content: str=''):
        """用户读取和维护《用户要求记忆和操作手册》，这是跨会话共用的文字文档，不是权限匹配表。记录用户的设备称呼、集体操作含义、默认设置、习惯、例外和操作方法。拿不准当前要求时先读手册，避免重复问已明确过的问题。read 读取，append 追加，write 整理或纠正整篇，clear 按用户要求清空。只记录用户实际提供或确认的要求，不凭空编造习惯。修改手册只保存文字，绝不读取或控制 HA 设备；无需先执行操作，也不需要会话ID、参数精确匹配、有效期或次数限制。所有用户在任何平台、群聊和私聊共用，插件配置页也能查看和编辑。

                Args:
                    action(string): read/append/write/clear。用户说“记住”时直接保存；纠正或删除某条要求可先 read 再 write。
                    content(string): append 的新增要求，或 write 的完整更新文档；read/clear 留空。write 时保留仍有效的其他要求。
                """
        async with self.lock:
            try:
                return self.client.update_manual(action, content)
            except PluginError as exc:
                return str(exc)
