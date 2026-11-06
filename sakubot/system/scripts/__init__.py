from pathlib import Path
import asyncio

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    
    
    name = 'scripts'

    def setup(self):
        self.page('manage','事件与脚本',Path(__file__).parent/'web'/'dist',icon='code',order=35,group_id='system')
        self.api('catalog',self.catalog_api)
        self.api('manage',self.manage_api,methods=('POST',))
        self.tool('script_manage','管理持久 Python 脚本：list/get/check/save/delete/revisions。保存只检查 Python 语法与入口，不执行脚本。每次开发或修改前必须重新调用 script_development 查阅相关插件当前文档，不能凭记忆猜接口。脚本须定义 main(ctx, event, tools)，更新须提供 expected_version；删除须 confirm=true 且先解除绑定。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'get', 'check', 'save', 'delete', 'revisions'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '脚本 ID；新建可省略由框架分配'}, 'version': {'type': 'string', 'description': 'get 时可选的历史版本哈希'}, 'name': {'type': 'string', 'description': '脚本名称，1至100字'}, 'description': {'type': 'string', 'description': '脚本用途，最多4000字'}, 'code': {'type': 'string', 'description': '完整 Python 源代码，不是文件路径'}, 'parameters': {'type': 'object', 'additionalProperties': True, 'description': '脚本参数的 JSON Schema，根节点为 object；动态字段由该脚本定义'}, 'expected_version': {'type': 'string', 'description': '修改前读取的当前版本；版本不一致时拒绝覆盖'}, 'event_sources': {'type': 'array', 'items': {'type': 'string', 'description': '事件 ID 或泛 ID，决定 event["data"] 的类型'}, 'description': '脚本接受的事件 ID 或泛事件模式；决定 event["data"] 的类型'}, 'tool_plugins': {'type': 'array', 'items': {'type': 'string', 'description': '需要的工具插件 ID；省略时包含全部可用脚本工具'}, 'description': '生成 文档 时包含的工具插件 ID 列表；省略包含全部可用工具'}, 'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 86400, 'description': '执行超时秒数；允许范围见类型约束'}, 'enabled': {'type': 'boolean', 'description': '是否启用本对象，true 启用，false 停用'}, 'concurrency': {'type': 'string', 'enum': ['queue', 'merge', 'skip'], 'description': '脚本忙碌时的新触发策略：merge 合并待执行事件，queue 排队，skip 忽略'}, 'on_failure': {'type': 'string', 'enum': ['none', 'wake', 'notify'], 'description': '失败处理：none 仅记日志，wake 唤醒主智能体，notify 直接通知'}, 'failure_threshold': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'description': '触发失败策略前需要连续失败的次数'}, 'cooldown_seconds': {'type': 'integer', 'minimum': 30, 'description': '重复失败通知的冷却秒数'}, 'send_result_to_source': {'type': 'boolean', 'description': '是否把本次唤醒结果或通知投递到当前主会话源；网页始终同步'}, 'confirm': {'type': 'boolean', 'description': '仅在用户已明确确认本次删除或危险操作时为true'}}, 'required': ['action'], 'additionalProperties': False},self.manage_tool)
        self.tool('script_development', '每次编写或修改脚本前必须重新查阅当前插件文档、工具说明、返回说明及事件示例，不能凭记忆或经验猜测。tools 是方法名映射到可调用函数的普通 dict，调用 await tools["方法名"](...)，无需插件ID。ctx、event 也是普通 dict。按 tool_plugins、sources 聚焦所需插件；文档分页返回，后续页携带 documentation_hash。',
            {'type': 'object', 'properties': {'id': {'type': 'string', 'description': '可选已存在的脚本 ID'}, 'sources': {'type': 'array', 'items': {'type': 'string', 'description': '完整或泛事件来源 ID'}, 'description': '需要查阅文档的完整事件 ID 或泛事件模式'}, 'parameters': {'type': 'object', 'additionalProperties': True, 'description': '脚本参数的 JSON Schema，根节点为 object；动态字段由该脚本定义'}, 'tool_plugins': {'type': 'array', 'items': {'type': 'string', 'description': '需要的工具插件 ID'}, 'description': '生成 文档 时包含的工具插件 ID 列表；省略包含全部可用工具'}, 'offset': {'type': 'integer', 'minimum': 0, 'description': '文档 文本字符偏移，首次0；下一页使用 next_offset'}, 'limit': {'type': 'integer', 'minimum': 1000, 'maximum': 12000, 'description': '本页 文档 字符数，1000至12000，默认10000'}, 'documentation_hash': {'type': 'string', 'description': '后续页携带首轮返回的 documentation_hash，避免混用不同版本文档'}}, 'required': [], 'additionalProperties': False}, self.development_tool)
        self.tool('script_run','排队运行某个脚本，返回执行 ID。运行器本身不调用模型，程序可按需唤醒主 Agent；使用 script_execution 查询结果。不会自动重放中断任务。',
            {'type': 'object', 'properties': {'id': {'type': 'string', 'description': '脚本 ID'}, 'params': {'type': 'object', 'additionalProperties': True, 'description': '该动作所需的参数对象；具体键和值依动作定义，不猜测字段'}, 'event': {'type': 'object', 'properties': {'id': {'type': 'string', 'description': '生产者去重 ID'}, 'source': {'type': 'string', 'description': '实际完整事件 ID，不含星号'}, 'at': {'type': 'number', 'description': '事件分发 Unix 秒'}, 'data': {'type': 'object', 'additionalProperties': True, 'description': '插件提供的业务字典；按当前插件文档读取'}}, 'required': ['id', 'source', 'at', 'data'], 'additionalProperties': False, 'description': '可选完整事件样本 {id,source,at,data}；省略时生成空的 manual 事件'}}, 'required': ['id'], 'additionalProperties': False},self.run_tool)
        self.tool('script_execution','查看脚本执行、日志、返回值与工具调用；或停止运行。action=list/get/stop。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'get', 'stop'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '执行 ID'}, 'script_id': {'type': 'string', 'description': 'list 时按脚本 ID 筛选；留空不限'}}, 'required': ['action'], 'additionalProperties': False},self.execution_tool)
        self.tool('script_binding','管理软触发绑定；具名 source 只能保存一个动作（停用绑定也占用），应编辑原绑定而非重复创建；泛事件 source 可多次绑定。source 可填尚未声明的 ID 或 * 通配模式，例如 mattermost.slash.*，不存在时仍可保存。sources 列出事件含义（可传 source 聚焦单个声明）、泛 ID 规则、绑定参数说明、递归字段类型与说明及完整 payload 示例；业务字段使用 event["data"] 字典访问，source/at/id 也用字典下标；options 获取动态实体/设备选项；save 校验参数，不执行。target_kind=script 绑定脚本；target_kind=wake 直接唤醒主智能体，须提供 prompt 提示词，无需 script_id。事件观测数据只注入本轮临时上下文。失败策略 none/wake/notify，支持连续失败阈值与冷却。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['sources', 'options', 'list', 'save', 'delete'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '已有绑定 ID；新建省略'}, 'source': {'type': 'string', 'description': '插件声明的完整或泛事件 ID，也允许尚未声明的软来源'}, 'target_kind': {'type': 'string', 'enum': ['script', 'wake'], 'description': '动作类型：wake 直接唤醒主智能体，script 执行脚本'}, 'prompt': {'type': 'string', 'description': '唤醒主智能体的提示词'}, 'script_id': {'type': 'string', 'description': '已保存脚本的唯一 ID，先查询脚本列表'}, 'name': {'type': 'string', 'description': '绑定显示名称'}, 'source_params': {'type': 'object', 'additionalProperties': True, 'description': '事件筛选参数，严格按所选来源的参数定义提供，不是脚本执行参数'}, 'params': {'type': 'object', 'additionalProperties': True, 'description': '该动作所需的参数对象；具体键和值依动作定义，不猜测字段'}, 'enabled': {'type': 'boolean', 'description': '是否启用本对象，true 启用，false 停用'}, 'on_failure': {'type': 'string', 'enum': ['none', 'wake', 'notify'], 'description': '失败处理：none 仅记日志，wake 唤醒主智能体，notify 直接通知'}, 'failure_threshold': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'description': '触发失败策略前需要连续失败的次数'}, 'cooldown_seconds': {'type': 'integer', 'minimum': 30, 'description': '重复失败通知的冷却秒数'}, 'send_result_to_source': {'type': 'boolean', 'description': '是否把本次唤醒结果或通知投递到当前主会话源；网页始终同步'}, 'confirm': {'type': 'boolean', 'description': '仅在用户已明确确认本次删除或危险操作时为true'}}, 'required': ['action'], 'additionalProperties': False},self.binding_tool)
        self.tool('script_tools','查询脚本可以调用的插件工具及参数定义。按 plugin 或关键词筛选；只列出当前可用插件，不调用工具。',
            {'type': 'object', 'properties': {'plugin': {'type': 'string', 'description': '可选插件 ID，只列该插件的工具'}, 'query': {'type': 'string', 'description': '工具名或描述的关键词'}}, 'required': [], 'additionalProperties': False},self.tools_tool)

    def prompt_context(self, invocation):
        return '重复、规则明确的工作可使用脚本执行，不必每次唤醒模型。每次新建或修改前必须重新读取 script-automation 技能，并用 script_development 查阅相关插件当前文档和事件定义；禁止凭记忆经验猜测，保存不会执行。'

    def catalog(self):
        service=self.runtime.scripts
        return {'scripts':service.repo.list('scripts'),'bindings':service.bindings(),'sources':service.source_manifest(),'runs':service.runs()}

    async def catalog_api(self,request):
        return self.catalog()

    async def manage_api(self,request):
        data=await request.json()
        operation=data.pop('operation','')
        if operation=='script': return await self.manage_tool(None,data)
        if operation=='development': return await self.development_tool(None,data)
        if operation=='binding': return await self.binding_tool(None,data)
        if operation=='run': return await self.run_tool(None,data)
        if operation=='execution': return await self.execution_tool(None,data)
        raise ValueError('操作无效')

    async def manage_tool(self,inv,args) :
        service=self.runtime.scripts
        action=args['action']; key=args.get('id','')
        if action=='list': return service.repo.list('scripts')
        if action=='get': return service.repo.read(key,args.get('version',''))
        if action=='check':
            from sakubot.automation.script_check import check
            old=service.repo.read(key) if key else {}
            return check(args.get('code',old.get('code','')))
        if action=='save':
            result=await service.repo.save(args)
            service.spawn(service.sources.reconcile())
            return {**result,'saved':True}
        if action=='revisions': return service.repo.revisions(key)
        if action=='delete': return service.delete('script',key,args.get('confirm',False))
        raise ValueError('操作无效')

    async def development_tool(self, inv, args):
        from sakubot.automation.documentation import development
        import hashlib, json
        old=self.runtime.scripts.repo.get(args['id']) if args.get('id') else {}
        result=development(self.runtime,sources=args.get('sources',old.get('event_sources',[])),
            parameters=args.get('parameters',old.get('parameters')),tool_plugins=args.get('tool_plugins',old.get('tool_plugins')))
        full=json.dumps(result,ensure_ascii=False,indent=2)
        digest=hashlib.sha256(full.encode()).hexdigest()
        if args.get('documentation_hash') and args['documentation_hash']!=digest:
            raise ValueError('文档已变化，请从第一页重新读取')
        offset, limit=args.get('offset',0),args.get('limit',10000)
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1000<=limit<=12000:
            raise ValueError('文档分页参数无效')
        return {'documentation':full[offset:offset+limit],'documentation_hash':digest,'total':len(full),
            'next_offset':offset+limit if offset+limit<len(full) else None}

    async def run_tool(self,inv,args) :
        from sakubot.automation.service import current_chain
        token=current_chain.set(inv.metadata.get('script_chain',[]) if inv else [])
        try:
            return self.runtime.scripts.enqueue(args['id'],params=args.get('params',{}),event=args.get('event'))
        finally:
            current_chain.reset(token)

    async def execution_tool(self,inv,args) :
        service=self.runtime.scripts
        if args['action']=='list': return service.runs(args.get('script_id',''))
        if args['action']=='get': return service.detail(args['id'])
        if args['action']=='stop': return await service.cancel(args['id'])
        raise ValueError('操作无效')

    async def binding_tool(self,inv,args) :
        service=self.runtime.scripts
        if args['action']=='sources':
            items=service.source_manifest()
            if args.get('source'):
                resolved=service.sources.resolve(args['source'])
                return [row for row in items if resolved and row['id']==resolved['id']]
            return items
        if args['action']=='options': return await service.sources.options(args['source'])
        if args['action']=='list': return service.bindings()
        if args['action']=='save': return service.save_binding({k:v for k,v in args.items() if k!='action'})
        if args['action']=='delete': return service.delete('binding',args['id'],args.get('confirm',False))
        raise ValueError('操作无效')

    async def tools_tool(self, inv, args):
        from sakubot.automation.documentation import tools
        return tools(self.runtime,plugin=args.get('plugin',''),query=args.get('query',''))
