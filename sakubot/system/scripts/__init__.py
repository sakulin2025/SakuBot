from .tool_arguments import ARGUMENTS
from .tool_types import R_script_binding, R_script_development, R_script_execution, R_script_manage, R_script_run, R_script_tools
from .tool_types import RESULTS
from pathlib import Path
import asyncio

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    tool_result_types = RESULTS
    tool_argument_types = ARGUMENTS
    name = 'scripts'

    def setup(self):
        self.page('manage','事件与脚本',Path(__file__).parent/'web'/'dist',icon='code',order=35,group_id='system')
        self.api('catalog',self.catalog_api)
        self.api('manage',self.manage_api,methods=('POST',))
        self.tool('script_manage','管理持久 Python 脚本：list/get/check/save/delete/revisions。保存自动做 Python 语法和 Pyright 类型检查，不执行脚本。有错误或警告不保存；仅类型诊断可用 hard=true 加 hard_reason 强制保存。先调用 script_development 取得准确 SDK 与例子。脚本须定义 main(ctx)，更新须提供 expected_version；删除须 confirm=true 且先解除绑定。',
            None,self.manage_tool)
        self.tool('script_development', '编写或修改脚本前获取准确 Python SDK、事件泛型、参数类型、工具方法签名与示例。ctx 是 Context 实例，ctx.event 和 ctx.params 是普通 dict；使用 ["data"] 而不是 .data。sources 决定事件类型，tool_plugins 可限制返回的工具接口以减少输出；SDK 分页返回，next_offset 非空时继续读取并携带 sdk_hash。仅生成类型与文档，不运行脚本。',
            None, self.development_tool)
        self.tool('script_run','排队运行某个脚本，返回执行 ID。运行器本身不调用模型，程序可按需唤醒主 Agent；使用 script_execution 查询结果。不会自动重放中断任务。',
            None,self.run_tool)
        self.tool('script_execution','查看脚本执行、日志、返回值与工具调用；或停止运行。action=list/get/stop。',
            None,self.execution_tool)
        self.tool('script_binding','管理软触发绑定；具名 source 只能保存一个动作（停用绑定也占用），应编辑原绑定而非重复创建；泛事件 source 可多次绑定。source 可填尚未声明的 ID 或 * 通配模式，例如 mattermost.slash.*，不存在时仍可保存。sources 列出事件含义（可传 source 聚焦单个声明）、泛 ID 规则、绑定参数说明、递归字段类型与说明及完整 payload 示例；业务字段使用 ctx.event["data"] 字典访问，source/at/id 也用字典下标；options 获取动态实体/设备选项；save 校验参数，不执行。target_kind=script 绑定脚本；target_kind=wake 直接唤醒主智能体，须提供 prompt 提示词，无需 script_id。事件观测数据只注入本轮临时上下文。失败策略 none/wake/notify，支持连续失败阈值与冷却。',
            None,self.binding_tool)
        self.tool('script_tools','查询脚本可以调用的插件工具及参数定义。按 plugin 或关键词筛选；只列出当前可用插件，不调用工具。',
            None,self.tools_tool)

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
        if operation=='development': return await self.development_tool(None,data)
        if operation=='binding': return await self.binding_tool(None,data)
        if operation=='run': return await self.run_tool(None,data)
        if operation=='execution': return await self.execution_tool(None,data)
        raise ValueError('操作无效')

    async def manage_tool(self,inv,args) -> R_script_manage:
        service=self.runtime.scripts
        action=args['action']; key=args.get('id','')
        if action=='list': return service.repo.list('scripts')
        if action=='get': return service.repo.read(key,args.get('version',''))
        if action=='check':
            from sakubot.automation.script_check import check
            old=service.repo.read(key) if key else {}
            report=await check(self.runtime,args.get('code',old.get('code','')),sources=args.get('event_sources',old.get('event_sources',[])),
                parameters=args.get('parameters',old.get('parameters')),tool_plugins=args.get('tool_plugins',old.get('tool_plugins')))
            return {k:v for k,v in report.items() if k not in ('sdk','event_contracts')}
        if action=='save':
            from sakubot.automation.script_check import ScriptDiagnosticsError
            try:
                result=await service.repo.save(args)
            except ScriptDiagnosticsError as exc:
                report=exc.report
                return {'saved':False,'error':str(exc),'can_force':bool(report.get('syntax_ok') and report.get('checker_available')),
                    'diagnostics':report['diagnostics']}
            service.spawn(service.sources.reconcile())
            return {**result,'saved':True}
        if action=='revisions': return service.repo.revisions(key)
        if action=='delete': return service.delete('script',key,args.get('confirm',False))
        raise ValueError('操作无效')

    async def development_tool(self, inv, args) -> R_script_development:
        from sakubot.automation.script_contracts import development
        old=self.runtime.scripts.repo.get(args['id']) if args.get('id') else {}
        if old and 'event_sources' not in old:
            old['event_sources']=list(dict.fromkeys(row['source'] for row in self.runtime.scripts.repo.list('bindings') if row.get('script_id')==old['id']))
        result=development(self.runtime,sources=args.get('sources',old.get('event_sources',[])),
            parameters=args.get('parameters',old.get('parameters')),tool_plugins=args.get('tool_plugins',old.get('tool_plugins')))
        import hashlib
        digest=hashlib.sha256(result['sdk'].encode()).hexdigest()
        if args.get('sdk_hash') and args['sdk_hash']!=digest:
            raise ValueError('SDK 定义已变化，请从第一页重新读取')
        offset, limit=args.get('offset',0),args.get('limit',10000)
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1000<=limit<=12000:
            raise ValueError('SDK 分页参数无效')
        full=result.pop('sdk')
        result.pop('event_contracts',None)
        result['unknown_results']=result['unknown_results'][:50]
        return {**result,'sdk':full[offset:offset+limit],'sdk_hash':digest,'total':len(full),
            'next_offset':offset+limit if offset+limit<len(full) else None}

    async def run_tool(self,inv,args) -> R_script_run:
        from sakubot.automation.service import current_chain
        token=current_chain.set(inv.metadata.get('script_chain',[]) if inv else [])
        try:
            return self.runtime.scripts.enqueue(args['id'],params=args.get('params',{}),event=args.get('event'))
        finally:
            current_chain.reset(token)

    async def execution_tool(self,inv,args) -> R_script_execution:
        service=self.runtime.scripts
        if args['action']=='list': return service.runs(args.get('script_id',''))
        if args['action']=='get': return service.detail(args['id'])
        if args['action']=='stop': return await service.cancel(args['id'])
        raise ValueError('操作无效')

    async def binding_tool(self,inv,args) -> R_script_binding:
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

    async def tools_tool(self,inv,args) -> R_script_tools:
        from sakubot.contracts.schema import contract_kind
        return [{'plugin':tool.plugin_id,**tool.schema()['function'],'result_schema':tool.result_schema,'result_typed':bool(tool.result_schema),'result_contract_kind':contract_kind(tool.result_schema)} for tool in self.runtime.registry.tools.values()
            if (not args.get('plugin') or tool.plugin_id==args['plugin']) and (not args.get('query') or args['query'].casefold() in (tool.name+' '+tool.description).casefold())
            and self.runtime.registry.availability(tool.plugin_id)['available']]
