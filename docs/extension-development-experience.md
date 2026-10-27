# 外部插件移植与框架开发体验（0.16.0）

这轮移植实际完成九个外部插件，源码在 `extensions`，运行包在 `data/plugins`；核心没有按插件名字新增工具、页面或菜单分支。未运行测试；部署记录以生产构建与实际启动日志为准。

## 开发中遇到的问题与已修正项

| 问题 | 实际影响 | 本轮修正 |
| --- | --- | --- |
| 工具注册需要把签名再抄成一份 JSON Schema | 移植时重复维护默认值、类型、文档，容易不一致 | `Plugin.function()` 从类型标注、默认值和 Args 文档生成工具定义；保留原始 tool() 处理复杂 Schema |
| 插件直接访问 runtime.store、自己拼 KV 前缀 | 容易写错命名空间，与核心存储实现耦合 | `Plugin.state.get/set` 统一按插件 ID 隔离键；迁移工具在停机时导入相同命名空间 |
| 每个插件重复配置文件读写与密钥脱敏 | 客户端持有旧 dict、页面保存后重载、空密码覆盖已有凭据 | `configure()` 返回保持引用的 PluginConfig，提供原子 save、受 Schema 校验的 patch、public 脱敏；空密钥表示保留 |
| 外部页面缺少统一构建入口 | 只能复制内置目录或自己拼 Vite 配置 | `node frontend/build-plugins.mjs <目录>` 支持独立插件根目录；不扫描或打包 volume |
| 多个管理页重复表格、编辑弹窗、配置表单 | 样式与交互分裂，开发量不必要增加 | 公共 PluginWorkbench + management() 协议，字段、栏目与动作由插件声明；复用 Saku UI，保持动态插件路由 |
| SDK 丢弃 API 错误正文 | 插件页面只显示“失败”，看不出配置或状态冲突 | 保留 ApiError.status，同时显示服务端安全错误内容 |
| 只重载包入口，Python 子模块留在 sys.modules | 修改 client.py 后仍运行旧实现 | 外部插件加载前清理自身完整模块前缀并失效导入缓存；先按生命周期停用旧实例 |
| 一项插件导入/启动失败会使整个主 Agent 暂停 | 外部插件缺依赖或配置错误影响所有能力 | 启动时按插件隔离失败并记录 plugin.failed，目录显示不可用状态；其他插件继续启动 |
| prompt_context 仅同步，且无异常边界 | 异步感知不得不轮询缓存，闲置也耗配额；一个配置错误还可能中断模型请求 | 支持 async prompt_context 并等待结果，天气/ScanElf 按请求复用客户端缓存；每个钩子单独记录错误，不中断其他插件 |
| background() 长期保存已完成 Task，异常可能无人读取 | 事件触发插件运行越久积累越多 | 完成后移除句柄、读取异常并记录 plugin.background.failed；停用仍取消所有活跃任务 |
| 自定义 ValueError 子类被隐藏成异常类名 | 移植客户端返回 PluginError，模型看不到可操作错误 | 工具与 Agent 错误边界接受 ValueError/RuntimeError 子类，保留受限长度业务错误 |
| 本地路径不能直接作为 QQ/网页都可接收的附件 | SSH 下载和图库取图无法完成统一交付 | `Plugin.artifact()` 发布不可变副本，返回框架附件 URL；QQ 将相对附件 URL 转成容器内 HTTP 地址，网页同源读取 |
| 提交主动事件不等于 AI 已处理 | MC 事件页面容易过早声称“已处理” | `Plugin.event_status(uid)` 查询持久状态；MC 页面区分 pending/running/done/failed 与历史迁移记录 |

## 容器本地用户兼容（0.16.1）

Compose 通过宿主机数值 UID/GID 运行，UID 不一定存在于镜像 passwd 数据库中。AsyncSSH 在处理显式远端 username 之前也会获取本地用户名；Python 3.13 在缺少环境变量和 passwd 条目时抛出 OSError。镜像与 Compose 显式设置 USER、LOGNAME 为 sakubot，提供应用身份标识；实际文件权限仍由数值 UID/GID 决定，不改变远端 SSH 用户，也不修改依赖或替换密钥。

## 保持的架构边界

所有工具仍受人格的插件可见性与插件运行可用状态控制，没有引入管理员、会话、角色权限。HA 的房间实体策略、AList 的目录策略属于原有业务配置，不是框架授权层。框架没有 SSH、天气、HA 或 MC 业务分支。

MC 轮询复用既有状态查询、连续失败确认、人数阈值跨越与基线算法，只把 AstrBot 的私有 cron 唤醒替换为公开 emit('wake')。main 采用主对话设置；显式私聊/群聊经 reply_target 固定投递，仍只有一份主上下文。定时、轮询和后台任务完成事件不会伪装成用户新消息。

程序、配置、业务数据、依赖、工作空间产物分别位于 data/plugins、data/plugin_data、框架插件 KV、data/plugin_dependencies、data/workspace。附件副本位于 data/artifacts，7天后过期并由框架定期清理；随机能力 URL 相当于临时下载凭据，插件静态资源不含这些地址或密钥。附件每个最多20MiB。

## 仍有的局限

- `@sakubot/ui` 仍是本仓库的源码 SDK，不是独立发布的 npm 包；外部插件页面构建需要同版前端 SDK。
- 插件依赖保存在 volume，但使用同一 Python 进程，不构成依赖隔离。冲突版本仍需人工统一；框架不会在启用插件时静默执行 pip。
- function() 适用于常见参数。复杂嵌套对象、条件字段和严格枚举仍应使用显式 tool() Schema 或在业务客户端校验。
- 当前 JSON/KV 没有独立的自动 schema 迁移系统，插件版本升级仍应提供自己的迁移步骤；本轮迁移是有备份和一次性标记的离线脚本。
- 当前后台连接与 Python 调用栈不能跨重启恢复。SSH只保留密钥、指纹和会话记录，断线后不自动重放命令。
- 通用表格可以快速建立一致的管理页面；复杂终端、拓扑图或历史图表仍应由插件提供专门 Vue 页面，不能靠字段 Schema 完全替代。
