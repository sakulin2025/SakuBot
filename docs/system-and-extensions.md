# 系统能力与扩展（0.20.0）

## 所有权与生命周期

基础能力放在 sakubot/system：workspace、memory、skills、utilities、messaging。它们使用统一注册接口，但由系统独立发现和加载，不依赖 settings.plugins 的可选启用列表。基础能力无法停用、删除或单独重载，基础加载失败会暂停运行并显示错误。函数保留原名、工具追踪来源保留内部模块 ID，能力页面显示“系统”来源。

系统内置标签列出基础能力（锁定勾选）及可选内置插件 qq、team、timers、web、office。第三方标签只列出 data/plugins 中的扩展；第三方可以即时启停、重载、导入、导出和确认删除。新部署不预先选择可选插件，基础网页聊天能力自动可用。

人格可见性只管理可选扩展，基础函数总是可用。系统声明的管理页面放“系统”，第三方声明的管理页面放“插件”；分组在后端页面声明时依据代码归属确定，前端按 manifest 分组，不写插件 ID 路由开关判断。

每个组件/插件最多声明一个管理页面；多功能在该页面中用标签组织。第二次声明页面直接报错，注册失败会清理已注册资源。插件卡片有页面时提供“页面”跳转，不显示页面数量。停用、删除后路由随声明解除。

## 文档处理归并

office 内部组合原 PDF、documents、spreadsheets 实现，保持16个函数名。一个可选开关，三个 Skill：office.pdf、office.documents、office.spreadsheets。旧 pdf.pdf、documents.documents、spreadsheets.spreadsheets 读取请求自动映射。

原启用列表中 pdf/documents/spreadsheets 自动合并为 office；人格和团队自管理人格中的引用同步映射，移除不再需要的基础能力开关引用。已有工作空间文件、配置和业务数据保留，原技能程序不再作为三个独立插件注册。

## 插件包

导出：GET /api/plugins/{id}/export?include_data=false。默认只含程序、清单和静态资源，跳过 .git、node_modules、.venv、__pycache__、.env；勾选“包含配置与数据”时加入 plugin_data/{id} 和该 ID 前缀的 KV。配置数据可能包含 Token、SSH 密钥等敏感信息，用户选择后下载到本机；不上传到第三方。不会打包框架模型供应商、全局人格、全局数据库、运行中的 Task 或依赖目录。

导入：POST /api/plugin-packages/import?include_data=false，原始请求体为 ZIP。支持上述导出格式，或只有一个 plugin.json 与 __init__.py 的目录包（可带单层外目录）。包 ID 必须与清单一致且不与系统能力重名；同名程序存在时拒绝覆盖。默认不导入状态，选择“导入配置与数据”后才恢复包内数据；已有状态被替换前备份到 data 外的 backups。程序先暂存再发布，校验路径、符号链接、重复文件、入口语法和体积。

导入后处于未启用状态，由用户开关启用。程序包不携带 Python 运行环境，也不自动执行 pip/安装脚本；第三方依赖仍需通过镜像或 data/plugin_dependencies 提供。启用失败会显示不可用状态及日志，不伪造加载成功。

格式：sakubot-plugin.json（format=sakubot-plugin, version=1, id, state_included）、plugin/ 程序、可选 plugin_data/ 与 state.json。压缩包上限50 MiB，展开上限150 MiB，最多5000项，导出使用相同上限。

删除：先点击删除，再在显式关闭的确认框中确认（DELETE 接口同时要求 confirm=true）；默认只删除程序，勾选“清除配置与数据”才删除插件目录数据及其 KV、Agent 历史/待注入上下文。删除时停止插件，解除工具/页面/订阅/Agent，取消该插件仍在排队的 wake。框架审计记录和插件自建的未知共享 SQL 表保留，不推测它们可以删除。

## 本次交付

按会话要求不运行测试，不导入/导出/删除真实插件作为试验；仅执行构建与部署加载确认。升级前完整备份 data 与旧运行程序到 data 外 backups。
