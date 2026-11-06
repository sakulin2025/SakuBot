"""Opt-in main-Agent interface to the core administration service."""


from pathlib import Path

from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    
    
    name = 'system_control'

    def setup(self):
        self.page('manage','系统管理',Path(__file__).parent/'web/dist',icon='settings',group_id='system',order=90)
        self.api('status', self.status)
        self.api('operations', self.operate, methods=('POST',))
        self.api('projects', self.project_api, methods=('POST',))
        self.tool('system_status','查看框架、插件、主智能体、重启支持和管理操作的状态；配置密钥被隐藏。',{'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},self.status_tool,audience='main')
        self.tool('system_plugins','扫描发现插件（不会自动执行）、查询状态，或排队启用、停用、重载、删除、导入与导出插件。变更在本轮唤醒结束后执行，立即返回 operation_id，请勿在当前轮循环等待。重载默认等待插件任务结束，force=true 才中断任务。删除须 confirm=true；仅可删除第三方插件。导入 ZIP 默认不启用。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'scan', 'enable', 'disable', 'reload', 'delete', 'import', 'export'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '插件 ID'}, 'path': {'type': 'string', 'description': '导入 ZIP 的容器内路径'}, 'force': {'type': 'boolean', 'description': '仅在已明确允许中断运行任务时为true；不能当作绕过业务校验的通用开关'}, 'purge': {'type': 'boolean', 'description': '删除时是否同时删除插件配置与业务数据，默认false'}, 'confirm': {'type': 'boolean', 'description': '仅在用户已明确确认本次删除或危险操作时为true'}, 'include_data': {'type': 'boolean', 'description': '导入/导出时是否包含配置和业务数据，默认false'}}, 'required': ['action'], 'additionalProperties': False},self.plugins_tool,audience='main')
        self.tool('system_config','读取或排队更新框架运行配置。使用框架 Settings 字段，模型和供应商配置在此统一管理；不会重启所有插件，正在运行的请求保留启动时模型配置。更新在本轮结束后应用。不要输出密钥。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['read', 'patch'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'values': {'type': 'object', 'additionalProperties': True, 'description': '框架配置补丁，严格按 Settings 模型字段；密钥只用于设置，不应对外报告'}}, 'required': ['action'], 'additionalProperties': False},self.config_tool,audience='main')
        self.tool('plugin_project','创建或签出第三方插件开发项目，列出、读取、精确版本写入文件，静态检查 Python/清单与依赖，构建 Vue 管理页，发布或回滚。项目放在 plugin_projects，发布到 plugins，旧版保存在 plugin_revisions。修改文件需 file_version，发布需 check 返回的 version。build/publish/rollback 在本轮结束后执行，不是即时成功。没有执行测试。依赖清单只检查，不会自动安装依赖。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'create', 'checkout', 'inspect', 'read', 'write', 'check', 'build', 'publish', 'versions', 'rollback', 'sdk'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '第三方插件 ID，不能与内置能力重名'}, 'label': {'type': 'string', 'description': '显示名称或标签'}, 'with_page': {'type': 'boolean', 'description': '创建插件项目时是否包含管理页面'}, 'path': {'type': 'string', 'description': '项目内相对路径'}, 'content': {'type': 'string', 'description': '写入开发项目文件的完整 UTF-8 正文'}, 'file_version': {'type': 'string', 'description': '读取文件时返回的内容版本哈希；修改时必须原样提供'}, 'version': {'type': 'string', 'description': 'check 返回的项目版本'}, 'revision': {'type': 'string', 'description': 'versions 返回的历史版本'}, 'enable': {'type': 'boolean', 'description': '发布完成后是否启用插件'}, 'force': {'type': 'boolean', 'description': '仅在已明确允许中断运行任务时为true；不能当作绕过业务校验的通用开关'}}, 'required': ['action'], 'additionalProperties': False},self.projects_tool,audience='main')
        self.tool('system_operations','查询或取消持久化的系统管理操作。取消仅对未执行的操作有效。本轮提交的操作要等本轮结束才执行，不要循环查询等待。',
            {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['list', 'get', 'cancel'], 'description': '本工具要执行的动作；仅接受枚举列出的操作'}, 'id': {'type': 'string', 'description': '持久系统操作 ID，使用提交操作返回的 operation_id'}}, 'required': ['action'], 'additionalProperties': False},self.operations_tool,audience='main')
        self.tool('system_restart','安排本轮结束后重启 SakuBot 工作进程，不依赖 Docker socket。提供 resume 则重启后提交一次全新的主智能体唤醒，结合 progress 继续目标；不会恢复旧工具调用。不要在同一轮等待重启结果。send_result_to_source 默认继承当前轮，网页始终可见。',
            {'type': 'object', 'properties': {'reason': {'type': 'string', 'description': '本次受监督重启的原因'}, 'progress': {'type': 'string', 'description': '已完成动作、结果未知的动作、待处理事项'}, 'resume': {'type': 'string', 'description': '重启后继续的明确目标；留空不唤醒'}, 'send_result_to_source': {'type': 'boolean', 'description': '是否把本次唤醒结果或通知投递到当前主会话源；网页始终同步'}}, 'required': ['reason'], 'additionalProperties': False},self.restart_tool,audience='main')

    @property
    def control_service(self):
        return self.runtime.control

    async def status(self, request):
        return {**self.control_service.status(),'projects':self.control_service.projects.list()}

    async def status_tool(self, inv, args) :
        return self.control_service.status()

    async def operate(self, request):
        data=await request.json()
        return self.control_service.submit(data.get('action'),data.get('payload',{}))

    async def project_api(self, request):
        return self.project_action(await request.json())

    async def plugins_tool(self, inv, args) :
        action=args['action']
        if action=='list': return self.runtime.registry.installed_catalog()
        if action=='scan': return self.control_service.plugins.scan()
        allowed={'enable':('id','force'),'disable':('id','force'),'reload':('id','force'),'delete':('id','purge','confirm','force'),'import':('path','include_data'),'export':('id','include_data')}[action]
        payload={key:value for key,value in args.items() if key in allowed}
        if action in ('enable','disable'):
            payload['enabled']=action=='enable'
            action='toggle'
        return self.control_service.submit('plugin.'+action,payload,invocation=inv)

    async def config_tool(self, inv, args) :
        if args['action']=='read': return self.runtime.config.public()
        return self.control_service.submit('config.patch',args.get('values',{}),invocation=inv)

    def project_action(self,args):
        action=args['action']; project=self.control_service.projects
        name=args.get('id','')
        if action=='list': return project.list()
        if action=='sdk':
            from sakubot.control.projects import SDK
            return {'directory':str(SDK),'guide':str(SDK/'docs/plugin-development.md'),
                'build_script':str(SDK/'build-page.mjs'),'example':str(SDK/'docs/system-control.md')}
        if action=='create': return project.create(name,args.get('label',''),args.get('with_page',True))
        if action=='checkout': return project.checkout(name)
        if action=='inspect': return project.inspect(name)
        if action=='read': return project.read(name,args['path'])
        if action=='write': return project.write(name,args['path'],args['content'],args.get('file_version'))
        if action=='check': return project.check(name)
        if action=='versions': return project.versions(name)
        raise ValueError('项目操作无效')

    async def projects_tool(self,inv,args) :
        if args['action'] in ('build','publish','rollback'):
            return self.control_service.submit('project.'+args['action'],{key:value for key,value in args.items() if key in {'build':('id',),'publish':('id','version','enable','force'),'rollback':('id','revision','enable','force')}[args['action']]},invocation=inv)
        return self.project_action(args)

    async def operations_tool(self,inv,args) :
        service=self.control_service.operations
        if args['action']=='list': return service.list()
        if args['action']=='cancel': return service.cancel(args['id'])
        return service.get(args['id'])

    async def restart_tool(self,inv,args) :
        return self.control_service.submit('system.restart',args,invocation=inv)
