from pathlib import Path
import asyncio

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    name = 'scripts'

    def setup(self):
        self.page('manage','事件与脚本',Path(__file__).parent/'web'/'dist',icon='code',order=35,group_id='system')
        self.api('catalog',self.catalog_api)
        self.api('manage',self.manage_api,methods=('POST',))
        self.tool('script_manage','管理持久 Python 脚本：list/get/save/delete/revisions。保存仅做语法与参数校验，不运行。脚本须定义 main(ctx)，更新须提供 expected_version；删除须 confirm=true 且先解除绑定。',
            object_schema({'action':{'type':'string','enum':['list','get','save','delete','revisions']},'id':text(),'version':text(),
                'name':text(),'description':text(),'code':text(),'parameters':{'type':'object'},'expected_version':text(),
                'timeout':{'type':'integer','minimum':1,'maximum':86400},'enabled':{'type':'boolean'},
                'concurrency':{'type':'string','enum':['queue','merge','skip']},
                'on_failure':{'type':'string','enum':['none','wake','notify']},'failure_threshold':{'type':'integer','minimum':1,'maximum':100},
                'cooldown_seconds':{'type':'integer','minimum':30},'send_result_to_source':{'type':'boolean'},'confirm':{'type':'boolean'}},('action',)),self.manage_tool)
        self.tool('script_run','排队运行某个脚本，返回执行 ID。运行器本身不调用模型，程序可按需唤醒主 Agent；使用 script_execution 查询结果。不会自动重放中断任务。',
            object_schema({'id':text('脚本 ID'),'params':{'type':'object'}},('id',)),self.run_tool)
        self.tool('script_execution','查看脚本执行、日志、返回值与工具调用；或停止运行。action=list/get/stop。',
            object_schema({'action':{'type':'string','enum':['list','get','stop']},'id':text('执行 ID'),'script_id':text()},('action',)),self.execution_tool)
        self.tool('script_binding','管理软触发绑定；具名 source 只能保存一个动作（停用绑定也占用），应编辑原绑定而非重复创建；泛事件 source 可多次绑定。source 可填尚未声明的 ID 或 * 通配模式，例如 mattermost.slash.*，不存在时仍可保存。sources 列出已声明的参数与事件定义；options 获取动态实体/设备选项；save 校验参数，不执行。target_kind=script 绑定脚本；target_kind=wake 直接唤醒主智能体，须提供 prompt 提示词，无需 script_id。事件观测数据只注入本轮临时上下文。失败策略 none/wake/notify，支持连续失败阈值与冷却。',
            object_schema({'action':{'type':'string','enum':['sources','options','list','save','delete']},'id':text(),'source':text(),
                'target_kind':{'type':'string','enum':['script','wake']},'prompt':text('唤醒主智能体的提示词'),'script_id':text(),'name':text(),'source_params':{'type':'object'},'params':{'type':'object'},'enabled':{'type':'boolean'},
                'on_failure':{'type':'string','enum':['none','wake','notify']},'failure_threshold':{'type':'integer','minimum':1,'maximum':100},
                'cooldown_seconds':{'type':'integer','minimum':30},'send_result_to_source':{'type':'boolean'},'confirm':{'type':'boolean'}},('action',)),self.binding_tool)
        self.tool('script_tools','查询脚本可以调用的插件工具及参数定义。按 plugin 或关键词筛选；只列出当前可用插件，不调用工具。',
            object_schema({'plugin':text(),'query':text()}),self.tools_tool)

    def prompt_context(self, invocation):
        return '重复、规则明确的工作可使用脚本执行，不必每次唤醒模型。编写前读 script-automation 技能，查看 script_tools 和触发源定义；保存不会执行。'

    def catalog(self):
        service=self.runtime.scripts
        return {'scripts':service.repo.list('scripts'),'bindings':service.bindings(),'sources':service.source_manifest(),'runs':service.runs()}

    async def catalog_api(self,request):
        return self.catalog()

    async def manage_api(self,request):
        data=await request.json()
        operation=data.pop('operation','')
        if operation=='script': return await self.manage_tool(None,data)
        if operation=='binding': return await self.binding_tool(None,data)
        if operation=='run': return await self.run_tool(None,data)
        if operation=='execution': return await self.execution_tool(None,data)
        raise ValueError('操作无效')

    async def manage_tool(self,inv,args):
        service=self.runtime.scripts
        action=args['action']; key=args.get('id','')
        if action=='list': return service.repo.list('scripts')
        if action=='get': return service.repo.read(key,args.get('version',''))
        if action=='save':
            result=service.repo.save(args)
            service.spawn(service.sources.reconcile())
            return result
        if action=='revisions': return service.repo.revisions(key)
        if action=='delete': return service.delete('script',key,args.get('confirm',False))
        raise ValueError('操作无效')

    async def run_tool(self,inv,args):
        from sakubot.automation.service import current_chain
        token=current_chain.set(inv.metadata.get('script_chain',[]) if inv else [])
        try:
            return self.runtime.scripts.enqueue(args['id'],params=args.get('params',{}))
        finally:
            current_chain.reset(token)

    async def execution_tool(self,inv,args):
        service=self.runtime.scripts
        if args['action']=='list': return service.runs(args.get('script_id',''))
        if args['action']=='get': return service.detail(args['id'])
        if args['action']=='stop': return await service.cancel(args['id'])
        raise ValueError('操作无效')

    async def binding_tool(self,inv,args):
        service=self.runtime.scripts
        if args['action']=='sources': return service.source_manifest()
        if args['action']=='options': return await service.sources.options(args['source'])
        if args['action']=='list': return service.bindings()
        if args['action']=='save': return service.save_binding({k:v for k,v in args.items() if k!='action'})
        if args['action']=='delete': return service.delete('binding',args['id'],args.get('confirm',False))
        raise ValueError('操作无效')

    async def tools_tool(self,inv,args):
        return [{'plugin':tool.plugin_id,**tool.schema()['function']} for tool in self.runtime.registry.tools.values()
            if (not args.get('plugin') or tool.plugin_id==args['plugin']) and (not args.get('query') or args['query'].casefold() in (tool.name+' '+tool.description).casefold())
            and self.runtime.registry.availability(tool.plugin_id)['available']]
