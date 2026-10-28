# SakuBot 0.21.1

[插件开发文档](docs/plugin-development.md)：外部插件安装、工具、事件、Agent 单例、消息订阅、管理页面及当前实现边界。

## 启动

```sh
docker compose up -d
```

| 项目 | 地址 / 文件 |
| --- | --- |
| 管理入口 | http://localhost:6190 |
| 监听 | 0.0.0.0:6190 |
| 令牌 | data/admin_token |
| 配置 | data/config.json |
| QQ 配置 | data/plugin_data/qq/config.json |
| 数据库 | data/sakubot.sqlite3 |
| 外部插件 | data/plugins/名字.py 或 data/plugins/名字/__init__.py |
| 部署 | Docker Compose |
| 基础镜像 | python:3.13-slim / node:alpine3.23 |

Compose 使用 Docker 卷 `sakubot_data` 持久化容器内的 `/data`。首次启动后可用 `docker compose exec sakubot cat /data/admin_token` 查看管理令牌。当前发布的镜像支持 Linux ARM64。

下文 `data/` 指容器内的 `/data/`。

## 配置

| 页面 | 字段 |
| --- | --- |
| 模型 · 供应商 | 名称、API 地址、Key |
| 模型 · 模型 | 模型 ID、能力、请求参数、上下文窗口 |
| 运行设置 | 执行参数、全局压缩、管理令牌 |
| 活动中心 | 事件、日志、工具调用、运行记录、消息投递 |
| QQ 插件 · NapCat | WebSocket、Token、QQ 主私聊、消息处理 |
| 主对话 | 同一主上下文、正文流、实时工具过程 |
| Agent 管理 | 默认人格、默认模型、Agent 人格与模型、主 Agent 开关 |
| 人格 | 名称、提示词、可见插件 |
| 插件管理 | 插件开关 |

## Agent

| 项目 | 规则 |
| --- | --- |
| 主 Agent ID | main |
| 插件 Agent ID | 插件名:本地ID |
| 人格 / 模型 | 页面指定 → 插件默认 → 全局默认 |
| 配置保存 | 即时 |
| 人格 visible_plugins=null | 全部插件 |
| 人格 visible_plugins=[] | 无插件 |
| 人格 visible_plugins=["qq","memory"] | 指定插件 |
| 主 Agent / 协作 Agent | 相同函数机制 |
| 当前运行 | 固定启动时的人格、模型与可见插件；插件启用和可用状态实时检查 |
| 主 Agent 开关 | 控制主队列；插件、连接、协作任务独立运行；网页不依赖 QQ |

## 插件 SDK

```python
from pathlib import Path
from sakubot.plugin import Plugin, object_schema

class Extension(Plugin):
    name = "example"

    def setup(self):
        self.tool("example_status", "读取状态", object_schema(), self.status)
        self.page("manage", "示例", Path(__file__).parent / "web" / "dist", icon="plugins")
        self.api("records", self.records)
        self.agent("researcher", "研究员", "调查资料", persona_id="", model_id="")

    async def status(self, invocation, arguments):
        return {"online": True}

    async def records(self, request):
        return {"items": []}
```

| 接口 | 参数 / 返回 |
| --- | --- |
| self.tool | name, description, parameters, handler |
| self.page | id, title, directory, icon, order, aliases |
| self.api | path, handler, methods |
| self.agent | id, name, description, persona_id, model_id |
| self.set_agents | 完整声明列表 |
| self.remove_agent | 本地 ID |
| self.get_agent | 本地或完整 ID；获取同一声明的单例句柄 |
| self.clear_agent_context | id；清空非主 Agent 上下文 |
| self.reset_agent | id；异步中断并重置非主 Agent |
| self.run_agent | id, goal, invocation, context, run_id |
| self.emit | context / wake / notify；text, target, actor, label, meta, uid, priority, expires |
| self.background | 生命周期后台任务 |
| self.personas | list / get / save / delete / resolve |
| self.personas.save | name, prompt, identifier, visible_plugins |
| invocation | run_id, target, actor, task_id, call_id, persona_id, agent_id, model_id, origin, metadata |

## 内置插件

| 插件 | 页面 | 函数 |
| --- | --- | --- |
| qq | 人物 | qq_send / qq_read / qq_action / qq_recent / qq_api |
| memory | 长期记忆 | memory_search / memory_write / event_search |
| timers | 定时任务 | schedule_manage |
| team | 专业团队 | team_members / team_delegate / team_tasks / team_requests / team_resolve |

| 专业团队 | 功能 |
| --- | --- |
| 成员 | 名称、描述、稳定 ID |
| 声明 | 增删改立即同步 |
| 委派 | 指定成员、目标、资料、资源、超时 |
| 执行 | 各自人格、模型及可见插件；并行队列 |
| 完成 | wake 主 Agent |

## 管理 API

所有 `/api/*`：`Authorization: Bearer 管理令牌`。

| 接口 | 数据 |
| --- | --- |
| GET /api/status | 状态 |
| GET /api/config | 脱敏配置 |
| PATCH /api/config | 配置分区 |
| GET /api/agents | Agent 列表、默认配置、有效配置 |
| PATCH /api/agent-defaults | persona_id / model_id |
| PATCH /api/agents/{id} | persona_id / model_id；空字符串为默认 |
| PATCH /api/agents/main/state | enabled |
| POST /api/agents/{id}/clear-context | 清空非主 Agent 上下文；运行时拒绝 |
| POST /api/agents/{id}/reset | 中断并重置非主 Agent |
| GET / POST /api/personas | 人格列表 / 保存 |
| GET / DELETE /api/personas/{id} | 人格详情 / 删除 |
| GET /api/functions?agent_id=main | 指定 Agent 的函数 |
| GET /api/plugin-registry | 插件、页面、路由 |
| PATCH /api/plugins/{id} | enabled |
| /api/extensions/{plugin}/{path} | 插件 API |
| GET /api/logs | 追踪日志 |
| GET /api/tool-calls | 工具调用 |
| GET /api/runs、runs/{id} | 运行与函数快照 |
| GET /api/deliveries | 投递记录 |
| GET / POST /api/events | 事件列表 / 新事件 |

## 前端

```sh
cd frontend
npm ci
npm run dev
npm run build
```

| 项目 | 实现 |
| --- | --- |
| 核心页面 | Vue 3 / TypeScript / Pinia / Vue Router |
| 插件页面 | 插件自身 web/src，独立构建至 web/dist |
| 插件 UI SDK | @sakubot/ui |
| 页面接入 | mountPlugin / usePluginHost |
| 左侧分区 | 插件，固定最下方 |
| 构建 | 自动发现 plugins/*/web/index.html |
| 插件停用 | 撤销页面、路由、API、函数、Agent 声明 |
| 弹窗关闭 | 显式关闭按钮 |

## Agent 单例 API（0.8）

```python
self.agent("worker", "协作成员", "整理资料")
agent = self.get_agent("worker")
agent.tool("record_result", "记录成果", object_schema({"text": text()}, ("text",)), self.record_result)
agent.inject("本次任务背景")
agent.on("tool_call", self.on_tool_call)
agent.on("completed", self.on_completed)
result = await agent.wake("完成任务", timeout=300)
agent.clear_context()
await agent.reset()
```

| 实例方法 | 参数 / 返回 |
| --- | --- |
| tool | name, description, parameters, handler |
| inject | content, role=user/assistant |
| on | started / model_request / tool_call / completed / failed / cancelled / compressed / waiting / resumed / reset；返回解绑函数 |
| wake | goal, invocation, context, instructions, persist, timeout, run_id, target, metadata；返回可等待的 Task |
| clear_context | 非主 Agent 空闲时清除历史与待注入内容，保留工具与回调 |
| reset | 异步取消当前及排队执行，清除上下文；保留声明、配置、工具、回调与句柄 |
| wait_for | future, invocation；等待外部答复，暂停超时并释放执行名额 |
| wake 返回 | run_id, agent_id, instance_id, result, usage, data |
| 单例 | 同一声明唯一实例；同一插件反复获取返回同一句柄 |
| 执行队列 | 同一 Agent 串行，不同 Agent 受全局并发数控制 |
| 超时 | 从获取执行名额后开始，排队及待确认期间不计时 |
| persist=False | 本次不读取或更新持久上下文 |
| 撤销声明 / 卸载 | 取消执行并使旧句柄失效，再操作抛出异常 |
| 临时调用数据 | invocation.metadata["data"] |
| 主 Agent wake | 加入主事件队列 |
| 实例历史 | SQLite KV，跨重启保留 |
| 实例生命周期 | 插件卸载时自动撤销临时函数、回调、待注入内容及运行任务 |

## 消息 API（0.7）

```python
self.subscribe_messages(["Group:12345", "Private:12345"], self.on_message)
self.set_message_subscriptions(["Group:67890"], self.on_message)
messages = self.get_messages("Group:67890", limit=20)
```

| 接口 / 字段 | 定义 |
| --- | --- |
| subscribe_messages | sessions, async callback；返回解绑函数 |
| set_message_subscriptions | 替换插件当前全部消息订阅 |
| get_messages | session, limit=20, before=None；时间正序 |
| before | 框架消息 ID，不含该条 |
| 消息字段 | id, uid, at, session_id, message_id, sender_id, sender_name, text, mentions, reply_to, parts, is_self |
| parts | 预处理后的文字、提及、图片解读、音频占位及附件标记 |
| 图片 | 消息处理页面选择支持图片的模型 |
| 语音接口 | Messages.transcribe_audio；暂未实现 |
| 停用 / 删除 / 重载 | 自动解绑消息订阅 |
| 插件热重载 | POST /api/plugins/{id}/reload |
| 外部插件删除 | DELETE /api/plugins/{id} |

## 上下文压缩（0.7）

| 项目 | 设置 |
| --- | --- |
| 默认 | 自动开启，80% |
| 设置入口 | 运行设置；开关和阈值全局生效 |
| 模型窗口未知 | 使用全局上下文字符预算估算 |
| 压缩模型 | Agent 当前模型 |
| 压缩内容 | 旧上下文及已闭合工具回合 |
| 保留 | 系统提示词、当前目标、最新工具回合 |
| 主 Agent 摘要 | SQLite KV，记录事件截止位置 |
| 压缩轨迹 | 运行详情 compressions、context.compressed 日志 |

## 外部消息回应（0.7）

| 项目 | 设置 |
| --- | --- |
| 固定 Agent | 回应判断助手、消息总结助手；人格由 QQ 自管理，不加载插件工具 |
| 会话 | Group:群号 / Private:QQ号，绑定响应模板 |
| 触发条件 | 被 @ / 提及内容 / Agent 判断，多选、或关系 |
| 主人限定 | 被 @、提及内容分别设置 |
| 判断概率 | 默认 0.1；未命中概率直接不判断 |
| 判断时段 | 默认 09:00~23:00，Asia/Shanghai；仅作用于 Agent 判断 |
| 注入模式 | 仅会话 ID / 指定条数消息 / 指定条数消息的 Agent 总结 |
| 会话消息 | 截至触发消息，不包含其后到达的消息 |
| 主人主私聊 | 由主框架接入，不重复生成唤醒 |


## 专业团队待确认（0.8）

成员临时函数 `team_wait_confirmation` 接受 `kind=question/confirmation`、`question`、可选 `context` 和 `options`。调用后暂停当前执行，唤醒主 Agent。主 Agent 可以直接判断，也可以询问主人；再用 `team_resolve(request_id, answer, approved)` 答复。答复作为原工具调用的返回值，成员继续原任务。同一成员后续任务保持排队，其他成员可以并行。

`team_requests` 获取待答复记录。专业团队页面的“待确认”页也可答复。重置、取消或卸载会结束等待；进程重启后等待标记为中断，不自动重放原任务或过期询问。


## 管理界面（0.9）

模型和供应商位于 `/model`，通过页面内标签切换。事件、追踪日志、工具调用、运行记录和消息投递位于 `/activity`。旧地址自动跳转并保留运行 ID。

`/settings` 集中执行参数、全局上下文压缩、消息处理和管理令牌。`PATCH /api/admin-token` 接收 `{"token":"新令牌"}`，写入 `/data/admin_token` 并立即生效。令牌支持 1～256 个可见 ASCII 字符。页面修改后更新当前会话登录凭据；其他客户端需要重新登录。

基础组件及动效见 [Saku UI](docs/ui-components.md)，核心与插件页面共用。


## 工作空间与 Skill（0.10）

`data/workspace` 是全部 Agent 共用的持久目录，含 AGENTS.md、notes、projects、artifacts、tmp。工作空间插件提供文件管理页及 workspace_* 工具，主 Agent 与协作 Agent 都按需访问。文件变更不自动唤醒 Agent，重置不会删除文件。

文件局部修改使用 edit/patch 按原文匹配，支持行号漂移；整文件覆盖可提供 base_content 或 version，移动删除仍使用 version；新文件无需 version。服务使用原子写入和进程内共享锁，过期版本拒绝覆盖。文本编辑上限 1 MiB，工具读取分页，上传上限 20 MiB；下载无需把二进制放入模型上下文。

能力页 `/functions` 包含“函数”和只读“技能”标签。独立技能位于 `data/skills/名字/SKILL.md`；包插件的 `skills/*/SKILL.md` 自动注册，随所属插件启停。插件也可通过 `self.skill(id, directory)` 动态注册和 `self.remove_skill(id)` 撤销。Skills 插件提供 skill_list、skill_read、skill_read_file。工作空间与技能索引在每次模型请求前按人格可见插件刷新，压缩后仍可重新读取。

参见 [插件开发文档](docs/plugin-development.md)与[工作空间和技能](docs/workspace-skills.md)。


0.10.1 新增 workspace_shell：默认在共享工作空间执行容器 /bin/sh 命令，支持 Python、管道与重定向。每次独立执行，超时和取消清理进程组，输出截断；文件管理页保留。详见工作空间文档的直接 Shell 章节。


## 独立主对话与插件状态（0.11）

网页主对话位于 `/chat`，与 QQ 主私聊使用同一事件存储、主队列和上下文。QQ 的主人消息、网页输入、Agent 回复以及插件事件在网页中统一展示。网页输入使用客户端消息 ID 去重，WebSocket 重连获得历史和当前流式内容快照。模型使用 Chat Completions SSE 正文流，经 WebSocket 推送；工具调用开始、完成、错误也实时推送。提供商直接返回普通 JSON 时整段显示，不伪造流式。页面不展示模型的内部 reasoning_content。

QQ 插件可启停，未连接时状态为不可用，不出现在 Agent 可用函数和技能索引中。插件页面和配置声明继续保留。NapCat 连接不作为主 Agent 启动条件；只需模型与人格有效。框架事件默认目标为 main，显式 private/group 目标继续支持。

QQ 持续连接失败按5、10、20、40、80、160、300秒退避，后续每300秒重试。稳定连接60秒后才重置失败计数，避免反复短连接回到5秒。仅真实在线转离线记录 qq.disconnected；连续重试失败日志最多每分钟一条。

普通回复先写入主对话再尝试在线 QQ 投递，QQ 失败不会使生成任务失败。QQ 离线期间不会积压网页普通回复等待补发；显式 QQ notify 仍进入持久投递队列。主目标 notify 在网页可见，include_context 控制是否进入模型历史。旧投递结果不确定时不自动重试。

API：GET /api/chat（before/limit）、POST /api/chat（text/client_id）、WebSocket /api/chat/live。WebSocket 接受后10秒内先发送 {"token":"管理令牌"}，令牌不放 URL。握手后推送 snapshot，后续接收 type=send 的 text/client_id 或使用 HTTP 发送。过慢客户端收到 resync 后重新获取快照。连接保持期间会检查令牌变更。

## 插件边界

QQ 自行管理 NapCat 连接、原生消息解析、配置、人物、身份提示词和页面；停用后页面、主导览建议、工具、对话源与投递适配器均撤销。保存 QQ 连接配置仅重连该连接，不重载 Agent。核心没有 QQ 连接对象或平台配置字段。

框架提供通用的规范化消息、订阅、对话源、显式目标投递、主导览建议和提示词扩展接口。工作空间、技能、长期记忆、定时任务、专业团队与外部消息回应均通过这些公共接口接入，业务数据表和恢复逻辑由所属插件初始化。

QQ 插件管理页统一提供 NapCat、人物、外部消息回应三个标签。回应判断与消息总结 Agent 均由 QQ 声明，模板和会话绑定归 QQ 持有；独立 external_reply 插件已合并移除。

回应判断助手与消息总结助手的人格固定由 QQ 插件设置，Agent 管理中显示“自管理”，仍可分别选择模型。两个助手的可见插件列表为空，不加载插件工具、技能索引或插件上下文。判断仅返回 respond JSON，总结仅返回摘要；每次任务不读取或保存历史。

0.15.5：文件新增带行号的 workspace_patch，workspace_edit 按唯一原文匹配，不因其他位置变化而拒绝。定时目标为 main/private/group，固定目标提供 target_id，owner 只迁移旧数据。后台任务默认结束后通过持久主动事件唤醒主 Agent，不再依赖模型轮询。

## 外部插件（0.16.0）

九个 AstrBot 自建插件已改为通过公共 API 加载的外部包，源码见 [extensions](extensions/README.md)，运行副本位于 data/plugins。开发体验与本轮框架修正见 [文档](docs/extension-development-experience.md)。迁移前备份位于 data 外的 backups/astrbot-migration-*，包含私密配置与 SSH 密钥。

0.16.1：镜像与 Compose 显式设置 USER/LOGNAME=sakubot，支持以宿主机数值 UID 运行时 AsyncSSH 获取本地用户名；不改变实际 UID/GID、设备远端用户名或 SSH 密钥。

0.16.2：修复提醒编辑的 ID 保留及失败原子性、余额查询默认模型选择；图库空安装不预置服务地址。九个外部插件完成只读服务检查与隔离数据检查，检查范围见 docs/extension-checks.md。

0.17.0：Agent 支持单次 wake 与单次模型请求的临时上下文；新增 tool_round 回调和 pending wake 取消接口；专业团队可更新任务进度，主 Agent 查询终态结果后消除重复完成唤醒。

0.18.0：新增内置联网（Tavily/SearXNG 搜索、静态网页读取）、时间与计算、主对话多媒体发送插件；统一公共插件 API、人格可见性与 Skill，联网页面由插件声明。详见 docs/builtin-capabilities.md。

0.19.0：移植 PDF、Word 文档和电子表格 Skill，新增配套读写、转换、重算与页面预览函数；镜像加入 LibreOffice、Poppler、中文字体及 Python 文档库。预览可作为当前模型下一次请求的临时图像观察，原件保持不变。详见 docs/office-skills.md。

0.19.1：QQ 回应支持正则分段、分段内容移除与随机间隔；默认按句号截断并移除句号，段间等待3到5秒。同目标发送保持顺序，分段设置更新不重连 NapCat。对话源/投递适配器支持声明总超时，QQ 分段发送由单次 API 超时约束。

0.19.2：QQ 回应分段新增默认启用的分段后裁剪、连续换行合并，处理顺序为分段→正则移除→换行合并→首尾裁剪。

0.20.0：基础能力移入 system 自动加载并锁定启用；插件管理分系统内置/第三方扩展；PDF、Word、表格合并为文档处理；第三方支持 ZIP 导入导出和确认删除；管理页面按系统/插件归属分组，每个插件最多一个页面。详见 docs/system-and-extensions.md。
