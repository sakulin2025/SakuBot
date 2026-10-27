# SakuBot 插件开发文档

适用版本：0.16.0。本文按当前代码编写；尚未实现的能力列在最后，不作为可用接口。

## 1. 安装位置与当前实现

部署目录 `~/ContainerService/napcat/data/sakubot` 挂载为容器 `/data`，与 `~/KeepCoding/sakubot` 源码分离。下文 `data/` 均指此运行数据目录。外部插件从 `/data/plugins` 读取，支持两种形式：

```text
data/
├── config.json
├── sakubot.sqlite3
└── plugins/
    ├── hello.py                 # 单文件插件
    ├── hello.json               # 单文件插件的可选清单
    └── notebook/                # 包形式插件
        ├── __init__.py          # 必须导出 Extension
        ├── plugin.json          # 可选清单
        └── web/
            └── dist/           # 已构建的页面
                ├── index.html
                └── assets/
```

`plugins` 目录可以手动创建。文件放入后刷新插件管理页，在列表中启用；放入目录不会自行启用。插件启用状态保存到 `config.json`，重启后恢复选中的插件。

插件 ID 必须匹配 `[a-z][a-z0-9_]{0,40}`，例如 `notebook`。单文件名称或包目录名就是 ID，类中的 `name` 也应保持一致。不要同时放置同名文件和包，也不要与内置插件重名；内置实现优先加载。

内置插件位于镜像 `/app/sakubot/plugins`，源码位于 `sakubot/plugins`。它们通过相同的 `Plugin`、工具、Agent、页面和事件接口注册，并未复制到 `/data/plugins`。替换镜像不会删除外部插件文件。

## 2. 最小可用插件

在 `data/plugins/hello.py` 写入：

```python
from sakubot.plugin import Plugin, object_schema, text


class Extension(Plugin):
    name = "hello"

    def setup(self):
        self.tool(
            "hello_greet",
            "向指定名字问好。",
            object_schema({"name": text("对方的名字")}, ("name",)),
            self.greet,
        )

    async def greet(self, invocation, arguments):
        return {"greeting": "你好，" + arguments["name"]}
```

可选的 `data/plugins/hello.json`：

```json
{"name": "hello", "label": "问好", "icon": "plugins"}
```

启用后，在“可用函数”中选择相应 Agent，可以看到函数及来源插件。人格必须允许看见这个插件，模型也必须启用工具使用能力，Agent 才会收到该函数。

清单当前仅用于插件列表展示；`label` 和 `icon` 生效，加载身份取自路径，`name` 不是独立的包管理声明。当前没有依赖、版本或配置表单清单协议。Skill 的独立目录和注册接口见下文。

## 3. 生命周期

| 方法 | 调用时机 | 用途 |
| --- | --- | --- |
| `setup(self)` | 启用时，同步执行 | 注册工具、Agent、页面和 API |
| `async start(self)` | 事件源启动后，或运行期间启用插件时 | 启动轮询、订阅和外部连接 |
| `async stop(self)` | 停用、重载、关闭时 | 关闭插件自己的连接与资源 |
| `background(coroutine)` | 插件自行调用 | 创建由插件生命周期管理的后台任务 |

```python
import asyncio

# 以下方法放入 Extension 类。
async def start(self):
    self.background(self.poll())

async def poll(self):
    while True:
        # 在这里读取外部设备状态。
        await asyncio.sleep(300)

async def stop(self):
    await super().stop()
    # 再关闭插件自己的 HTTP/SSH 等客户端。
```

框架会在卸载时撤销插件的页面、路由、API、工具与 Agent 声明，解绑消息订阅，并取消登记的执行任务。覆盖 `stop()` 时应调用父类方法，让 `background()` 创建的任务被取消并等待结束。不要吞掉 `asyncio.CancelledError`。

`setup()` 不适合网络请求或长任务；异步初始化放在 `start()`。启动尚未完成时，工具应自行返回明确的未就绪错误。

## 4. 工具函数与调用信息

```python
self.tool(name, description, parameters, handler)
```

- `name`：全局唯一，匹配 `[A-Za-z0-9_-]{1,64}`。建议以插件 ID 为前缀。
- `description`：给模型看的功能和参数语义，可以包含自然语言使用场景。
- `parameters`：JSON Schema；框架在调用前校验参数。
- `handler`：`async def handler(invocation, arguments)`，返回可 JSON 序列化的数据。

`object_schema(properties, required=())` 创建不接受额外字段的对象 Schema；`text(description="")` 创建字符串 Schema。可预期的输入错误用 `ValueError("具体原因")` 返回给模型。工具调用的参数、结果和状态会被框架追踪，避免把密钥放入返回值或日志。

| `Invocation` 字段 | 含义 |
| --- | --- |
| `run_id` | 本次运行 ID |
| `agent_id` | `main` 或 `插件ID:本地AgentID` |
| `target` | 事件目标，例如 `private:12345`、`group:12345` |
| `actor` | 事件发起人的 ID，可能为空 |
| `task_id` | 任务 ID，没有时为空 |
| `call_id` | 模型生成的本次工具调用 ID |
| `persona_id` / `model_id` | 运行使用的人格、模型 ID |
| `origin` | 模型调用为 `agent`，插件页面调用为 `dashboard` |
| `metadata` | 运行元数据；协作运行可用 `metadata["data"]` 存放本次结果 |
| `instance` / `control` | 框架提供的运行实例和暂停控制信息；由框架管理 |

函数没有管理员、群聊或协作 Agent 权限层。模型侧可见性按人格的 `visible_plugins` 筛选：`null` 为全部，`[]` 为无插件，其余为插件 ID 列表。页面通过 `call_tool()` 调用时不受人格可见性筛选，但仍有参数校验和追踪。

## 5. 事件：记录、唤醒、通知

```python
await self.emit("context", "设备刚刚上线")
await self.emit("wake", "设备离线，请判断是否需要告知主人", uid="offline:device1:42")
await self.emit("notify", "备份完成", include_context=True)
```

| 类型 | 行为 |
| --- | --- |
| `context` | 记录上下文，不触发模型 |
| `wake` | 加入主 Agent 队列，由主 Agent 处理 |
| `notify` | 排队发送固定文字；不调用模型，可选加入上下文 |

`emit(kind, content, **kwargs)` 支持：

| 参数 | 默认值 / 含义 |
| --- | --- |
| `target` | 空、`owner` 或 `main` 时使用主上下文；也可指定 `private:QQ号`、`group:群号` |
| `actor` / `label` | 发起人 ID / 展示名称 |
| `meta` | JSON 可序列化元数据 |
| `uid` | 事件唯一 ID；同一个来源事件用稳定 ID 去重，不同事件必须不同 |
| `priority` | 默认 20；较大的值先处理 |
| `expires` | 默认 0；事件过期的 Unix 时间戳，非持续秒数 |
| `include_context` | 默认 `False`；用于 `notify` 成功投递后的上下文记录 |

事件目标不会创建另一个主 Agent 上下文。主 Agent 仍然只有一份主上下文，网页与 QQ 共用；发往其他会话的事件需要在正文和元数据中带上必要来源信息。主 Agent 关闭时 `wake` 不会执行，插件和协作 Agent 可继续运行。

## 6. 声明与复用 Agent

```python
# setup 中声明并获取实例。
self.agent("analyst", "分析员", "分析设备状态")
agent = self.get_agent("analyst")
agent.on("completed", self.on_completed)

# 异步处理函数中调用。
result = await agent.wake(
    "分析这份记录",
    context="记录正文",
    instructions="输出结论和依据",
    invocation=invocation,
    timeout=300,
)
```

每个声明是一个单例，完整 ID 为 `插件ID:analyst`。同一插件反复 `get_agent()` 获得同一句柄；不同插件持有各自受生命周期管理的句柄，但指向同一声明实例。同一实例的任务串行，不同实例按全局并发设置并行。

普通人格、模型按“Agent 管理中的指定值 → 插件声明默认值 → 全局默认值”解析。插件可在声明时提供 `persona_id`、`model_id`。自管理人格单独通过实例方法设置，核心没有人格覆盖入口；模型覆盖仍适用。

### 动态声明

```python
self.set_agents([
    {"id": "analyst", "name": "分析员", "description": "分析设备状态"},
    {"id": "writer", "name": "整理员", "description": "整理报告"},
])
self.remove_agent("writer")
```

`set_agents()` 替换当前插件的完整声明列表。保留的 ID 继续使用原单例；被移除的声明终止运行并使旧句柄失效。新增、编辑、删除可以在运行期间调用，管理页面会同步声明列表。

### 实例接口

| 接口 | 行为 |
| --- | --- |
| `agent.id` | 完整声明 ID |
| `agent.instance_id` | 当前实例标识；重置不会改变，卸载后重新加载会改变 |
| `agent.tool(name, description, parameters, handler)` | 为这个实例添加临时工具；同一插件再次注册同名工具会更新 |
| `agent.inject(content, role="user", temporary=False)` | 暂存下一次调用的上下文；temporary=True 仅该次 wake 有效，不保存为历史或摘要；role 只支持 user / assistant |
| `agent.on(event, callback)` | 注册同步或异步回调，返回解绑函数 |
| `agent.wake(goal, ...)` | 立即返回可等待的 asyncio Task |
| `agent.clear_context()` | 空闲时清除历史和待注入内容 |
| `await agent.reset()` | 中断当前及排队运行并清空上下文 |
| `await agent.wait_for(future, invocation=inv)` | 在当前协作运行中等待外部结果 |

`wake()` 还支持 `persist=True`、`run_id`、`target`、`metadata`、`temporary_context=""`。临时上下文只参与该次 wake 内的模型请求，下一次 wake 不再携带；不会写入 Agent 历史或压缩摘要，但会留在本次追踪记录中。结果包含 `run_id`、`agent_id`、`instance_id`、`result`、`usage`、`data`。`metadata` 的副本成为 `invocation.metadata["data"]`，工具可更新它，结果通过 `data` 返回。

`persist=True` 会读取并保存成功运行的历史；`persist=False` 不读写历史，适合判断、总结。历史保存在 SQLite，跨容器重建保留；运行中的 Python Task、Future 和回调不能跨重启恢复。工具和回调需要每次加载时注册。

同一插件在 `wake()` 前暂存的注入内容会在调用时取走，归属该次排队任务。并发派发时优先用 `wake(context=...)`，避免多个调用方先后 `inject()` 混用资料。

清空与重置只支持非主 Agent。两者都保留工具、回调和配置，重置也保留原句柄；不能在 Agent 自己的工具或回调里等待重置自身。插件另提供 `clear_agent_context(id)` 和 `await reset_agent(id)` 快捷接口。

撤销声明、停用或卸载插件后，相关旧句柄再操作会抛出 `AgentInvalidatedError`。取消和重置不会撤销已经发生的外部操作。

`get_agent("main").wake(...)` 只是提交主队列事件，返回提交结果，不等待主 Agent 完成；不要把它当作同步主 Agent RPC。

### 生命周期回调

```python
async def on_completed(self, event):
    await self.emit("wake", "分析完成：" + event["result"])
```

事件包括 `started`、`model_request`、`tool_call`、`tool_round`、`completed`、`failed`、`cancelled`、`compressed`、`waiting`、`resumed`、`reset`。参数始终含 `agent_id`，其他字段随事件不同：

- 工具：`phase=before/after/error`，以及 `name`、`arguments/result/error`、`invocation`、`run_id`。
- 完成：`result`、`usage`、`invocation`、`run_id`；协作实例另有 `data`、`instance_id`。
- 失败或取消：`error`、`invocation`、`run_id`。
- 模型请求：`step`、`invocation`、`run_id`。
- 整轮工具结束：`tool_round` 在一次模型返回的全部工具调用（包括失败调用）处理后触发，带 `step`、`calls`、`invocation`、`run_id`；不会在每个工具之间打断本轮。

仅下一次模型请求有效的提醒使用 `event["invocation"].inject_temporary("提醒")`。每次请求前取走，不加入历史、摘要或下一次请求。可在 `tool_round` 或 `model_request` 中调用。

```python
# 仅这次 wake 有效，后续复用实例不会带上提醒。
await agent.wake("分析", temporary_context="这次只检查变化，不操作设备")

# 每轮工具结束时决定要给下一次模型请求的提醒。
agent.on("tool_round", lambda event: event["invocation"].inject_temporary("判断是否需要更新进度"))
```

### 取消排队 wake

```python
queued = await self.emit("wake", "任务完成", uid="result:" + task_id,
    temporary_context="仅本轮参考这条提醒")
# 可传 emit 返回的整数 id，或唯一字符串 uid。
state = self.cancel_wake(queued["id"])
# state: {id, uid, cancelled, status}
```

`cancel_wake` 只取消状态为 pending 的 wake；运行中、已完成或重复取消时返回 `cancelled=False` 及当前状态，不中断 Agent。不存在时 status=missing。取消后的事件不参与后续上下文。管理接口 `POST /api/events/{id}/cancel` 使用同一实现；`POST /api/events` 支持 temporary_context。

专业团队成员每轮工具后收到一次临时进度提示，由成员用 `team_update_progress` 决定性更新；`team_tasks` 与任务页面返回 progress、progress_at、tool_rounds。仅主 Agent 经工具查询到终态结果时取消相应 pending 完成通知，并标记已知；若通知尚未入队，后续也不会再排入。网页轮询和其他成员查询不改变主 Agent 的通知状态。
- 暂停或恢复：`invocation`、`run_id`。
- 重置：`instance_id`。

回调异常会记录到 `agent.callback.failed`；回调不应长期阻塞。回调中的失败不会成为原任务的自动重试指令。

## 7. 待确认与暂停恢复

专业团队已经使用此机制，参考 `sakubot/plugins/team/confirmations.py`：

1. 给成员实例注册 `team_wait_confirmation` 临时工具。
2. 工具创建 Future，持久化请求，`emit("wake", ...)` 唤醒主 Agent。
3. 工具通过 `await agent.wait_for(future, invocation=inv)` 等待。
4. 主 Agent 自行判断或询问主人，再调用 `team_resolve`；页面也能答复。
5. 解析函数写入结果并 `future.set_result(...)`，原工具调用返回，成员继续原任务。

等待期间暂停执行超时，释放全局并发名额；同一单例的串行锁仍被占用，后续任务继续排队。计时在重新获取执行名额后恢复。插件自身持有的资源锁不会被框架自动释放。

通用插件需要自己维护请求 ID、Future 与答复接口，并在取消时清理。不能在主 Agent 某个工具里等待“主 Agent 下轮答复”，那会阻塞自己的事件队列。重启后原协作执行不能从 Python 栈恢复，应结束旧等待并展示中断状态。

## 8. 消息订阅与历史

```python
async def start(self):
    self.subscribe_messages(["Group:12345", "Private:67890"], self.on_message)

async def on_message(self, message):
    history = self.get_messages(message["session_id"], limit=20)
    # 由插件自己的条件判断是否需要唤醒。
    if "备份失败" in message["text"]:
        await self.emit(
            "wake",
            "请处理备份失败消息：" + message["text"],
            uid="notebook:backup:" + message["uid"],
        )
```

- `subscribe_messages(sessions, callback)` 增加订阅，返回解绑函数。
- `set_message_subscriptions(sessions, callback)` 先清除当前插件全部订阅再注册，适用于动态配置。
- 会话格式为 `Group:群号`、`Private:QQ号`，大小写会规范化。
- `get_messages(session, limit=20, before=None)` 返回时间正序，条数范围 1～500。
- `before` 为框架消息 ID，不含该条。并发消息可能已到达，若需精确截至触发消息，可用 `before=message["id"]` 取此前记录，再按条数补入触发消息。
- 框架不会回放订阅前的历史事件；订阅处理串行执行，回调过慢会积压。
- 停用、删除或重载会自动解绑订阅。

消息包含 `id`、`uid`、`at`、`session_id`、`message_id`、`sender_id`、`sender_name`、`text`、`mentions`、`reply_to`、`parts`、`is_self`。`id` 是框架序号，`message_id` 是 QQ 消息 ID，不能混用。

消息订阅接收框架预处理的入站消息；机器人自己的发送记录可通过历史接口读取，不会作为入站订阅再次分发。图片使用“消息处理”中指定的模型转为文字，语音当前只有占位，识别接口尚未实现。通过这个接口不会拿到原始 NapCat 包。

## 9. 插件状态和配置持久化

优先使用 `self.state.get/set` 自动管理插件命名空间。也可使用框架 Store 的 JSON KV，手动访问时键必须带插件前缀：

```python
def records(self):
    return self.runtime.store.kv_get(self.id + ":records", [])

def save_records(self, records):
    self.runtime.store.kv_set(self.id + ":records", records)
```

较大文件可自行创建 `self.runtime.config.root / "plugin_data" / self.id`，该基础目录由框架启动时建立，插件自己的子目录由插件创建。容器内镜像目录不可作为持久化位置。

不需要修改框架 Settings 才能增加插件配置：可用 KV 保存并通过插件 API 与页面编辑。当前不会根据 Schema 自动生成配置表单，也不会替插件安装 requirements。附加 Python 依赖需要事先进入镜像环境。

插件删除 API 删除插件程序文件和启用记录，不会自动清理插件在共享数据库里的 KV 或其他自建数据目录。

可选的同步 `context(self, invocation)` 能返回主 Agent 提示词中的插件上下文。它按人格可见插件筛选，整体有长度截断，应保持短小；不要返回协程或大列表。协作 Agent 的 `wake()` 不会自动调用此钩子，需要显式 `context=` 或 `inject()`。

普通外部消息使用 `publish_message()` 归档和分发订阅，不要额外 emit context。平台通知和过程状态保留在插件状态或日志，通过查询工具按需读取。`context()`、`prompt_context()` 不应自动请求远端、注入设备目录、天气观测或后台历史；只放简短能力提示及用户明确要求常驻的内容。`emit('context', ...)` 本身就是显式写入主上下文，不能用作普通日志；`wake` 只用于用户配置的触发条件或当前任务确需处理的结果、求助。通知默认 `include_context=False`。已标记 `exclude_main` 或 `exclude_context` 的历史记录不进入主模型提示词或压缩摘要，仍可通过查询工具主动检索。

## 10. 管理 API 与可视化页面

以下示例位于 `data/plugins/notebook/__init__.py` 的类中：

```python
from pathlib import Path
from sakubot.plugin import Plugin


class Extension(Plugin):
    name = "notebook"

    def setup(self):
        self.page("manage", "记录本", Path(__file__).parent / "web" / "dist")
        self.api("records", self.list_records)
        self.api("records", self.write_records, methods=("POST",))

    async def list_records(self, request):
        return self.runtime.store.kv_get(self.id + ":records", [])

    async def write_records(self, request):
        records = await request.json()
        if not isinstance(records, list):
            raise ValueError("记录必须为列表")
        self.runtime.store.kv_set(self.id + ":records", records)
        return {"saved": True}
```

`api(path, handler, methods=("GET",))` 支持路径参数，比如 `records/{identifier}`，在 `request.path_params` 读取。返回 JSON 可序列化值。完整地址为 `/api/extensions/notebook/records`，由框架统一检查管理令牌。需要复用已注册工具及追踪时，处理函数可用 `await self.call_tool("notebook_write", payload)`。

`page(id, title, directory, icon="plugins", order=50, aliases=())` 动态声明菜单和页面。页面 ID 匹配 `[a-z][a-z0-9_-]{0,40}`；`aliases` 是可选的绝对路由列表。每个插件最多声明一个页面；内置页面位于“系统”，第三方页面位于最下面的“插件”分区。停用时框架撤销声明，不需要在核心路由里硬编码。

### Vue 页面

`web/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head><meta charset="UTF-8"><title>记录本</title></head>
  <body><div id="app"></div><script type="module" src="/src/main.ts"></script></body>
</html>
```

`web/src/main.ts`：

```ts
import { mountPlugin } from '@sakubot/ui'
import App from './App.vue'
mountPlugin(App)
```

`web/src/App.vue`：

```vue
<script setup lang="ts">
import { ref, onMounted, usePluginHost, UiEmpty } from '@sakubot/ui'
const host = usePluginHost()
const rows = ref<string[]>([])
onMounted(async () => { rows.value = await host.api<string[]>('records') })
</script>

<template>
  <h1>记录本</h1>
  <ul><li v-for="(row, index) in rows" :key="index">{{ row }}</li></ul>
  <UiEmpty v-if="!rows.length" label="暂无记录" />
</template>
```

[Saku UI 组件文档](ui-components.md)记录公共组件的属性、插槽、事件及示例。所有 S 前缀组件在核心与插件页面中均已全局注册。

`@sakubot/ui` 当前是仓库内源码别名，不是可从 npm 安装的独立发布包。它提供 Vue 常用函数、`UiIcon`、`UiBadge`、`UiModal`、`UiEmpty`、`formatDate`、`parseJson` 和宿主桥接：

| 接口 | 行为 |
| --- | --- |
| `mountPlugin(App)` | 等待宿主握手再挂载到 `#app` |
| `host.api(path, body?, method?)` | 插件 API；无 body 默认 GET，有 body 默认 POST |
| `host.coreApi(path, body?, method?)` | 框架 `/api/` 接口 |
| `host.refresh()` | 请求宿主刷新配置与动态路由 |
| `host.navigate(path)` | 导航到宿主路由 |
| `host.toast(text, error=false)` | 状态通知 |
| `host.context()` | 握手后可读取插件、页面、主会话等宿主信息 |

令牌由宿主桥接注入，不应写进前端产物。页面资源当前可直接访问，管理 API 才检查令牌，因此静态文件不能包含私密配置。插件代码属于受信任本地代码，没有进程或权限沙箱。

### 外部页面构建

`frontend/build-plugins.mjs` 默认扫描源码 `sakubot/plugins/*/web`；可指定目录，例如 `node frontend/build-plugins.mjs extensions`，不会自动扫描 volume。外部插件发布时需要自行构建并带上 `web/dist`。在本项目中可用以下 Vite 配置，放到 `frontend/vite.external-plugin.config.ts`，仅作为开发示例：

```ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const here = fileURLToPath(new URL('.', import.meta.url))
export default defineConfig({
  root: resolve(process.env.SAKUBOT_RUNTIME_DATA || '/Users/sakulin/ContainerService/napcat/data/sakubot', 'plugins/notebook/web'),
  base: './',
  plugins: [vue()],
  resolve: {
    alias: {
      vue: resolve(here, 'node_modules/vue/dist/vue.runtime.esm-bundler.js'),
      '@sakubot/ui': resolve(here, 'src/plugin-sdk/index.ts'),
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
```

从 `frontend` 执行 `npx --no-install vite build --config vite.external-plugin.config.ts` 生成外部页面；构建完成后，插件后端直接提供这些文件。此命令是文档示例，本次未执行。

页面遵循当前项目约定：使用 Vue 和公共组件，弹窗通过显式按钮关闭，不允许点击遮罩或按 Esc 丢失编辑；界面使用标题、字段、状态和操作按钮，不增加描述、解释性文案。

## 11. 插件管理与诊断

| 管理接口 | 用途 |
| --- | --- |
| `GET /api/plugin-registry` | 发现内置及外部插件、已声明页面 |
| `PATCH /api/plugins/{id}`，body `{"enabled": true}` | 启用，false 停用；立即生效并持久化 |
| `POST /api/plugins/{id}/reload` | 重载已启用插件 |
| `DELETE /api/plugins/{id}` | 停用并删除外部插件文件；内置插件不可删除 |
| `GET /api/functions?agent_id=main` | 查看 Agent 的可用函数及来源 |
| `GET /api/agents` | 查看动态 Agent 声明和有效配置 |
| `GET /api/logs?source=notebook` | 插件相关追踪日志 |
| `GET /api/tool-calls?plugin_id=notebook` | 插件工具调用记录 |

上述 `/api/` 请求需要 `Authorization: Bearer 管理令牌`。当前插件管理页提供开关和重载按钮，删除需使用 API。修改插件文件后需要重载或重启，不会自动监听文件变化。

`self.runtime.store.log("info", self.id, "notebook.saved", run_id=invocation.run_id, data={...})` 可写追踪记录。工具异常、回调失败和订阅失败也有框架日志。

外部插件重载会重新执行入口，但当前没有递归刷新已导入 Python 子模块的机制。修改包中已缓存的辅助模块时，应重启容器以确保完整加载；不要把入口重载描述为任意模块热替换。

## 12. 当前边界

已实现的是外部 Python 插件发现与加载、公共插件 API、动态工具与 Agent、消息订阅、预构建页面、即时启停、入口重载和外部插件删除。

以下能力尚未实现：

- 插件市场、上传安装、Git 安装和依赖自动安装。
- 外部插件前端自动构建、独立发布的 Python / npm SDK。
- 插件配置 Schema 和自动生成配置页面。
- 本地模型文件管理与统一模型目录。
- 运行任务与待确认 Future 跨进程恢复。
- 插件隔离沙箱；插件 Python 代码与框架在同一进程。

目前内置插件全部在镜像中，volume 中的 plugins 目录由框架建立，用于外部插件。开发者可按本文件创建外部插件，无需为纯 Python 插件重建镜像；增加未安装依赖或变更框架本身仍需要调整镜像。


## 工作空间与 Skill（0.10）

公共文件服务为 `self.workspace`，与文件管理页和 workspace_* 工具共用实现。文件方法：`list(path='', offset=0, limit=100, query='')`、`read(path, offset=0, limit=200)`、`document(path)`、`write(path, content, version='')`、`write_bytes(path, content, version='')`、`edit(path, old, new, version)`、`mkdir(path)`、`move(path, destination, version)`、`remove(path, version, recursive=False)`。这些方法同步执行，调用方无需另外加锁。

```python
record = self.workspace.read("notes/example.md")
self.workspace.edit("notes/example.md", "原文", "新文", record["version"])
self.skill("example", Path(__file__).parent / "skills" / "example")
self.remove_skill("example")
```

包插件 `skills/*/SKILL.md` 在加载时自动发现；显式注册优先。单文件插件可通过 self.skill 显式注册目录。插件卸载后自动撤销，重新加载会重新发现；运行中可显式增删声明。技能描述沿用人格对所属插件的可见性，独立 local 技能在 Skills 插件可见时可用。

Skills 插件的工具让模型按需读取正文与参考文件。主 Agent 与协作 Agent 每次模型请求前刷新工作空间约定和技能索引；Skill 正文不会全部常驻上下文。管理页只提供查看，没有编辑或删除接口。

SDK 新增 `host.upload(path, file)`（PUT 原始文件）与 `host.download(path, filename)`，自动带宿主管理凭据。详见 [工作空间和 Skill](workspace-skills.md)。


### Shell（0.10.1）

`await self.workspace.shell(command, cwd='', timeout=60)` 与 workspace_shell 工具共用执行器，命令运行在 SakuBot 容器中。默认工作目录 /data/workspace，初始 cwd 为其相对目录；命令本身没有目录沙箱。返回合并输出、退出码、超时与截断标志。调用是独立进程，结束时清理进程组，不维持后台服务。Shell 写入不使用文件版本保护。skill_read 结果新增 directory，表示技能实际目录，供明确使用 Shell 的脚本操作定位。


## 插件可用性（0.11）

插件可覆盖同步方法 `availability()`，返回 `{"available": bool, "reason": str}`。默认可用。注册表在生成函数列表和执行函数时实时检查；不可用时不提供函数、上下文贡献或技能索引，但保留已加载插件的页面和管理 API。管理列表区分 disabled（未启用）、enabled（已启用且可用）、unavailable（已启用但不可用）。状态变化后更新 `self.runtime.registry.revision` 让客户端刷新声明。

```python
def availability(self):
    return {"available": self.client_connected, "reason": "" if self.client_connected else "设备未连接"}
```

QQ 已采用此接口，断线时从全部 Agent 的工具列表撤下。QQ 不再是必需插件，插件无需绑定 QQ 就可启动。框架 `self.runtime.main_target()` 返回 main；默认事件目标、协作任务、团队回报与待确认都使用该主上下文。

网页主对话 `/chat` 使用框架 Store.events，不创建独立 Agent。`self.emit` 的事件和工具过程可实时出现在网页，插件无需直接操作 WebSocket。QQ 投递与主对话保存解耦；网页在 QQ 离线或停用时仍可使用。

## 主对话源

主对话仍只有一份上下文，网页始终同步。插件可以声明多个主对话源；普通消息订阅不会自动成为主对话输入。对话源卸载时由框架撤销声明并取消其投递任务。当前选择仍被保留，不会自动改选其他源。

```python
from sakubot.plugin import Plugin

class Extension(Plugin):
    name = 'example'

    def setup(self):
        self.conversation_source('owner', '设备终端', handlers={
            'text': self.send_text,
            'image': self.send_image,
            # 可选：video、file、audio、stream、tool、lifecycle
        }, availability=lambda: {'available': True, 'reason': ''})

    async def incoming(self, message_id, content):
        await self.receive_main('owner', content, uid=str(message_id),
                                actor='owner', label='主人')

    async def send_text(self, packet):
        await self.client.send(packet['text'])

    async def send_image(self, packet):
        await self.client.send_image(packet['url'])

    async def tool_result(self, invocation, args):
        # 已有工具处理器中输出附件；声明何种工具、是否调用由插件决定。
        response_id = await self.respond_main([
            {'type': 'text', 'text': '生成结果'},
            {'type': 'image', 'url': 'https://example.com/image.png', 'name': '结果'},
        ], invocation=invocation)
        return {'response_id': response_id, 'sent': True}
```

声明 ID 为 `<plugin_id>.<identifier>`。`receive_main()` 会以 `wake` 进入主对话，UID 在该源内去重。只应将用户希望交给主 Agent 的输入送入此接口；普通群消息继续用消息订阅。来源下线不会阻止网页发言或主 Agent 运行。可在运行时调用 `remove_conversation_source(identifier)` 撤销本插件的单个源，重新声明即可恢复。

运行设置 → 主对话：

- 智能：源收到新输入时立即持久化切换当前响应源。不等任务结束；排队任务、正在执行的后续输出、定时任务、网页发言和团队回调都使用当前源。重复输入不会再次切换。首次尚未选择来源时，仅网页接收。
- 广播：所有源均可输入，只有勾选源接收主响应。来源输入不会改动勾选列表。
- 网页：两种模式下均同步，不参与响应源切换，也不受勾选影响。
- 工具调用过程：控制源的 `tool` 接口，网页过程面板始终保留。

切换不撤回已发送内容；已经开始的网络请求也不能转向。尚未发出的最终消息在智能模式下会转向当前源，旧源积压的流式片段和过程事件丢弃。源不可用或缺少接口时不补发、不自动切换来源。

所有处理器接收一个字典，公共字段是 `type`、`response_id`、`run_id`、`delivery_id`。处理器可以同步或异步，异步投递超时 30 秒，每个源串行，各源并行。请使用 `async def` 进行网络 IO，避免阻塞框架。

| 接口 | 内容 |
| --- | --- |
| text | `text`、`part_index`、`final=True` |
| image/video/file/audio | `url`、可选 `name`、`part_index`、`final=True` |
| stream | `event=model.started/model.delta/model.completed/model.failed`、`request_id`；delta 含 `text` |
| tool | `event=tool.started/tool.completed/tool.failed`、`call_id`、`name`，以及对应 `arguments/output/error` |
| lifecycle | `event=run.started/run.completed/run.failed`、`event_id` |

同一个模型请求的流式事件和最终内容使用相同 `response_id`；`model.completed` 仅代表当前模型请求结束，后面仍可能有工具调用。实现流式展示的源应在最终 `text` 到来时替换对应的临时内容，避免重复展示。一次任务可能有多个模型请求，来源也可能在过程中改变，因此处理器应允许在没有收到 `model.started` 时直接收到 delta 或最终内容。对话源不应自行重新触发 Agent。

附件输出不依赖源支持情况，先保存到统一历史，再逐项投递；没有实现的接口记录为 `unsupported`，不会使 Agent 失败。远端异常或超时记录 `uncertain`，不自动重试。网页直接呈现 HTTP(S) 图片、视频、语音和文件；URL 需分别可被浏览器和目标服务访问，不会隐式上传本地路径。QQ 源实现文字、图片、视频、文件、语音，未实现流式和工具过程。

`respond_main()` 默认生成响应 ID，也可提供 `response_id` 做幂等输出；同一 ID 不重复发送。传入 `invocation` 时仅接受主 Agent；协作 Agent 应返回结果，由主 Agent 决定输出。框架普通最终文本仍正常投递，工具输出附件后应告知 Agent 避免重复输出相同内容。

管理接口：`GET /api/conversation-sources` 返回动态声明、能力、可用性和持久化当前源；`PUT /api/conversation-sources/current` 接收 `{"id":"example.owner"}` 可手动选择；`PATCH /api/config` 的 `conversation` 分区保存 `conversation={mode,targets,tool_events}`，即时生效且不重启 Agent。

## 自管理人格与运行时 Agent 声明

自管理是 Agent 声明的标记，配置内容由插件自行持久化，不放进框架声明、人格库或 Agent 管理接口。

```python
self.agent('reviewer', '审阅助手', '审阅项目变更', persona_mode='managed')
agent = self.get_agent('reviewer')
agent.set_persona('你负责审阅项目变更，核对事实、说明依据并提出可执行意见。')
agent.with_plugins(['workspace', 'skills'])
# 也可以逐个添加：agent.with_plugin('team')
```

| 实例方法 | 作用 |
| --- | --- |
| `set_persona(prompt)` | 设置插件提供的运行提示词 |
| `with_plugins(ids)` | 替换插件可见性列表，`None` 为全部，`[]` 为无插件 |
| `with_plugin(id)` | 添加一个可见插件；首次从默认全部模式切换为指定列表 |

方法均返回原句柄，可链式调用，仅用于声明为 managed 的 Agent。尚未设置提示词时 Agent 未就绪，框架不会为它回落到默认人格。句柄失效后再调用会抛出异常。

`persona_mode` 的 default 和 library 仍用于框架管理人格：默认使用框架默认人格，引用人格库时指定 persona_id。未填写 mode 时，有 persona_id 使用人格库，否则默认人格。managed 不接收内嵌 persona 内容，插件先声明再通过实例方法提供运行参数。

`set_agents()` 同样只传声明元数据。插件加载时从自己的持久化存储中恢复配置，再逐一设置实例；卸载后实例配置被撤销，下次加载需重新设置。清空上下文、重置实例不会清除这些插件提供的运行配置。专业团队把正文和可见插件存放在 `team:members` 中，其页面与 AI 工具编辑这些内容，核心 Agent 管理的人格列仅显示“自管理”，没有人格查看、编辑或覆盖入口。框架模型设置仍可覆盖插件默认模型。

每次任务实际启动时，框架从实例取得插件提供的提示词和可见插件快照交给模型执行；人格正文不作为 Agent 声明或管理数据返回。实际模型请求追踪仍反映发送给模型的提示词。运行中的任务保持原快照，后续修改只影响下一次启动的任务，包括排队任务。插件启用和可用状态仍实时检查。

对同一 ID 再次 `agent()` 是更新声明，保留实例、临时工具、回调、上下文、运行中和排队任务；新增 ID 不重载插件。`set_agents()` 是全量替换，遗漏的旧 ID 会被移除并中断。专业团队的成员创建、编辑使用增量声明和实例设置接口，删除只撤销对应成员。

专业团队提供 `team_create_member`、`team_get_member`、`team_update_member` 和 `team.create-agent` Skill；人格正文的查看与编辑属于专业团队自身的 API，不是框架的人格管理 API。

## 定时目标与目录列表版本

定时任务 target 枚举为 main/private/group，private/group 必须提供独立 target_id。main 沿用当前主对话路由；private/group 的 notify 及 wake 后最终响应固定投递到指定目标，不改变智能模式的当前来源。所有 wake 使用统一主上下文，网页始终同步。新配置不接受 owner；旧数据仅迁移为 main。旧 private:号码/group:号码 拆分保存。

`self.workspace.list(path)` 的顶层 version 对应当前目录，可用于该目录的 move/remove；items 中的 version 对应各子项。目录条目变化后重新 list 获取版本，避免复用 mkdir 时的旧版本。移动删除保留版本冲突检查；文件局部修改可使用基于内容唯一匹配的 edit/patch，整文件覆盖可提供 base_content。

## 平台插件与通用扩展接口

平台连接、协议消息解析和配置文件由平台插件持有。`self.data_dir` 指向 `data/plugin_data/<plugin_id>`，可通过 `self.runtime.config.atomic(path, content)` 原子保存插件配置；核心 `/api/config` 不包含平台地址、账号或 token。

`prompt_context(invocation)` 支持同步或异步，返回本插件的提示词扩展，仅在插件启用、可用且对该 Agent 可见时注入；每次模型请求刷新。内置工作空间、技能、QQ 均使用这个接口，核心不按插件 ID 拼接专属提示词。

`onboarding()` 返回可选的主导览建议列表，条目字段为 key、title、icon、path、completed。path 应引用自己通过 `page()` 声明的页面；建议随插件卸载移除。核心只提供模型、Agent 和激活插件的通用主导览步骤。

```python
async def send_notification(self, packet):
    # 交给本插件的实际平台客户端，返回可 JSON 编码的结果。
    return await self.client.send(packet['target'], packet['text'])

# setup 中注册；availability 未填时使用插件的 availability()。
self.delivery_adapter('message', self.send_notification,
    accepts=lambda target: target.startswith('device:'))
```

`emit('notify', ..., target='device:123')` 通过投递适配器发送。适配器随插件卸载撤销，执行中的发送取消后标记为 uncertain，不自动重试。明确目标的通知可在适配器尚未加载或离线时保持 pending，待对应适配器可用后发送；这不同于 main 响应源离线时不补发的策略。`target=main` 仍使用广播或智能响应源设置，网页始终同步。

插件提供原始平台消息的解析器，框架只接收规范化记录：

```python
await self.publish_message({
    'uid': 'device:message:42', 'at': time.time(), 'session_id': 'Device:123',
    'message_id': '42', 'sender_id': '123', 'sender_name': '设备',
    'text': '状态已更新', 'parts': [{'type': 'text', 'text': '状态已更新'}],
    'mentions': [], 'reply_to': '', 'is_self': False,
    'is_owner': False, 'is_main_source': False, 'mentions_self': False,
    'identity': {'self_id': 'bot', 'owner_id': 'owner'},
})
```

`publish_message` 为记录补充插件 source，框架保存并分发经过字段筛选的规范化消息。原始包不传给订阅插件。`is_owner`、`is_main_source`、`mentions_self` 由消息源判断，外部消息回应插件据此工作，无需读取另一个插件的配置或连接对象。图片解读和语音识别接口仍是框架消息处理服务。订阅和查询沿用 `subscribe_messages` / `get_messages`。

一般消息订阅不自动进入主上下文。源应通过 `receive_main` 明确提交主对话输入；平台旁路记录可设置 `meta.exclude_main=true`、`meta.exclude_context=true`，核心不再按平台名筛选。`meta.source_label` 可指定主对话中的来源名称。现有 QQ 历史已通过一次性迁移补充元数据。

数据层只初始化核心表。memory、timers、team、qq 分别初始化自己的业务表，沿用旧表名以保留数据；插件停用后不删除持久化数据。`people_lookup` 归 QQ 插件，长期记忆不依赖 QQ 人物表。工作空间文件服务和技能解析仍是框架通用服务，其工具、页面和模型使用指引由插件提供。


## QQ 管理页与外部消息回应合并（0.15.1）

QQ 只声明一个 manage 页面，内部使用 NapCat、人物、外部消息回应三个标签。原连接和人物路径为该页面的别名，不再产生独立导航条目。

外部消息回应位于 QQ 插件的 `external_reply.py` 模块，使用 `external/*` 插件 API；模板、会话绑定和启用状态保存在 `qq:external_reply`。两个声明 Agent 为 `qq:judge`、`qq:summarizer`。回应总开关即时更新消息订阅，不重载 QQ 连接或其他 Agent。停用整个 QQ 插件则按统一生命周期撤销消息订阅、页面和声明 Agent。

部署迁移脚本 `sakubot/plugins/qq/merge_external.py` 负责移除旧插件选择，迁移模板、会话绑定、Agent 人格与模型覆盖、持久上下文和可见插件引用；保留原功能启用状态。配置和数据库备份在 `data/migrations/before-qq-merge-*`。

## 显式事件响应目标（0.15.5）

插件 emit('wake', ..., target=目的地, meta={'reply_target': 目的地}) 可让本轮最终响应通过公共投递适配器固定发送到该目标。仍使用唯一主上下文，网页同步正文和过程，不向当前主对话源广播本轮过程，不更改当前源。省略 reply_target 沿用主对话设置。定时插件据 main/private/group 生成该参数；核心不依赖 QQ。

投递适配器的 packet 现在可包含 type=text/image/video/file/audio 及相应 text/url/name/mime。现有 enqueue(target,text,uid) 保持不变，enqueue_part(target,part,uid) 可排队单个消息部分。QQ 适配器支持这些消息类型。

## 0.16.0：外部插件开发便捷接口

```python
from sakubot.plugin import Plugin

class Extension(Plugin):
    name = 'example'
    def setup(self):
        self.config = self.configure({'url':'', 'token':''}, secrets=('token',))
        self.function(self.search, name='example_search')
    async def search(self, keyword: str, limit: int = 10):
        """搜索本插件条目。"""
        return self.state.get('records', [])[:limit]
```

`configure()` 的返回值是可变字典，客户端可持有同一个引用；`save()` 原子落盘到插件 data_dir/config.json；`public(fields?)` 清空密钥并附 *_configured；`patch(data,schema)` 校验提交字段，空密钥保留原值。尚不存在的配置文件使用默认值，不在包中生成含个人数据的配置。

`state.get(key,default)` / `state.set(key,value)` 自动使用插件命名空间，不删除业务数据。`function()` 从 Python 标注和默认值生成 Schema、提取 Args 文档，保留 invocation 作为框架注入参数；同步函数移入线程，异步函数直接等待，返回对象不再次编码为 JSON 字符串。复杂参数可继续使用 tool()。

`management(title,sections,state_callback,action_callback)` 注册插件拥有的 manage API 和 web/dist 页面。`PluginWorkbench` 是可选的公共 Vue 组件，通过该协议渲染表格、配置表单、图片、业务文本和明确关闭的编辑/删除弹窗；不包含解释段落。字段及操作由插件声明，核心不会按插件ID判断页面。示例见 extensions 下各包。

`artifact(path,name?)` 返回 {url,name,mime,expires}，将最多20MiB文件复制为7天有效的不可变附件；返回 URL 可用于 respond_main 的 image/file 等部分。能力 URL 不应公开写入静态页面，获得 URL 的人可以在有效期内下载。QQ容器访问默认 http://sakubot:6190，可通过 SAKUBOT_INTERNAL_URL 调整。后台定期清除过期附件副本，原工作空间文件不清理。

`event_status(uid)` 返回持久事件的 ID、状态、目的地和错误；emit 返回排队不等于 AI 完成。外部页面构建使用 `node frontend/build-plugins.mjs extensions`。依赖目录 data/plugin_dependencies 由运行 Python 读取，当前仍是受信任共享进程，不是 venv 或插件沙箱。

本轮实践、修正和剩余限制：[外部插件开发体验](extension-development-experience.md)。

`prompt_context(invocation)` 支持同步或 async 方法，框架在模型请求前等待结果，适合使用客户端缓存按需取得只读感知信息；不必为了满足同步钩子而全天轮询。钩子只为可见、可用插件执行，异常单独记录；耗时请求应由插件客户端设置超时。

### 页面图像观察

`plugin.preview_images(invocation, paths, note='页面预览')` 可把最多两张工作空间图片作为下一次模型请求的临时观察，不发送聊天消息。返回 queued/count/scope；当前模型没有图像能力或非 Agent 调用时 queued=false 并给出 reason。图像按当前调用模型判断，不静默切换供应商；不会自动唤醒 Agent。

路径必须在工作空间内，支持 Pillow 可读取的图片。压缩图只用于模型输入，原图保持不变；追踪保存路径，图片内容不写入后续历史或摘要。成功排队只证明提供视觉输入，不能替代模型实际检查。pdf/document/spreadsheet 的 render 工具使用该公共接口。

### 投递处理总超时

`conversation_source(..., timeout=30)` 与 `delivery_adapter(..., timeout=30)` 可声明处理一个完整响应的总超时；`None` 表示由插件内部约束单次 I/O，适合有间隔的分段发送。默认30秒保持不变，停用插件仍会取消处理。不应把排队成功当作真实送达；框架在 handler 完成后记录送达，插件负责记录每段外部调用。

## 系统能力与插件包（0.20.0）

基础实现位于 sakubot/system，由系统自动加载；社区扩展仍使用相同 Plugin API 并保存在 data/plugins。插件只能声明一个页面，多功能使用插件自己的页面标签。侧栏分组由程序来源决定：系统组件/内置插件归系统，外部插件归插件。

第三方 ZIP 清单、可选配置数据、导入导出接口和删除行为见 [系统能力与扩展](system-and-extensions.md)。导入默认不启用、不执行依赖安装。插件须打包可直接使用的 web/dist，不携带 node_modules。基础函数不参与人格可见插件选择；可选插件维持原有可见性机制。

### 组件样式归属

组件库的样式与动效定义在各自 Vue 单文件组件的 `<style>` 中，不依赖额外的 `ui.css`。主题变量位于 `tokens.css`；应用基础样式和页面布局位于 `style.css`。插件通过 `@sakubot/ui` 使用组件，构建时自动打包组件样式，无需单独引入组件库 CSS。加载指示器使用 `SSpinner`。

### 插件设置表单

第三方插件可在 `plugin.json` 声明 `settings.fields`。设置按钮由声明生成，在插件停用时同样可编辑；缺少必填配置时状态为 `pending_configuration`（待配置）。设置与管理页面独立，不占用页面名额。

```json
{"settings":{"fields":[
  {"key":"base_url","label":"服务地址","type":"string","required":true,"format":"http-url","placeholder":"例如 http://192.168.1.10:8080"},
  {"key":"token","label":"Token","type":"secret","required":true,"placeholder":"粘贴访问令牌"}
],"connection":{"path":"/api/status","token_field":"token"}}}
```

`connection` 声明只读 GET 验证：`url_field` 默认 base_url，`token_header` 默认 Authorization，`token_prefix` 默认 Bearer 加空格；可用 `required_paths` 指定响应 JSON 必须包含的字段路径。接口需返回 HTTP 200 与 JSON 对象。验证失败不写入文件。

运行时可用 `self.settings_form(fields, validate=callback, on_saved=callback)` 声明或扩展设置。先通过 `self.configure(defaults, secrets=(...))` 创建配置；自定义 validate 接收合并后的候选配置，可以异步执行，失败抛 ValueError；on_saved 用于刷新缓存。停用时只执行清单中可声明的验证，代码回调在启用后生效。清单字段与运行时字段按 key 合并。已有 `management()` 的 config 表单自动接入该入口，管理页面不重复显示配置标签。

前后端校验字段类型、必填项、整数范围、select 选项与动态引用、长度和 pattern；HTTP 地址拒绝内嵌凭据、查询参数与片段。secret 不回传原值，留空保留已有值。保存成功更新内存配置与插件状态，不重载插件。表单字段支持 placeholder，解释文字不单独占用页面空间。
