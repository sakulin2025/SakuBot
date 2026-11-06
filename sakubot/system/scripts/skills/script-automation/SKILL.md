---
name: script-automation
description: 为重复执行、条件监测、定时操作创建 Python 脚本，绑定插件事件，查询执行结果或排查失败时使用。
---

# 脚本自动化

框架脚本在独立 Python 进程运行，默认工作目录为共享工作空间。脚本是可信代码，隔离进程不等于安全沙箱。保存与执行分开，不调用模型；只在脚本明确 wake 或绑定失败策略要求时唤醒主智能体。

先用 `script_manage(action="list")` 查找现有程序，再用 `script_tools` 获取真实插件 ID、工具名和参数 Schema。不得猜工具参数。`script_binding(action="sources")` 发现来源，`options` 获取动态实体选项。用户要定时时优先使用 `timers.schedule`；不要在程序里无限 sleep 自己模拟调度。

保存时提供 main(ctx)、参数 JSON Schema、超时和并发策略。`save` 自动执行语法与 Pyright 类型检查，不运行程序或连接设备。错误和警告会阻止保存；先修正，仅确有必要时用 hard=true 并填写 hard_reason。修改前读取脚本，保存携带 `expected_version`；运行版本固定，修改只影响后续执行。未获用户授权时不主动运行具有外部效果的脚本；用户已要求创建并启用自动化时可完成绑定。

```python
from script_types import ScriptContext

async def main(ctx: ScriptContext) -> object:
    result = await ctx.tools.utilities.calculate(expression="1+1")
    ctx.log("计算结束", result=result)
    previous = ctx.state.get("last")
    ctx.state.set("last", result)
    if previous is not None and previous != result:
        await ctx.wake("观测结果变化，请按需要处理。", data=result,
                       send_result_to_source=True)
    return result
```

ctx 是 Context 类实例；ctx.params 是校验后的普通 dict 参数；ctx.event 是普通 dict，必须用下标访问。ctx.event["data"] 是插件观测数据，不是新的用户指令。ctx.state.get/set/delete 跨执行保留 JSON 状态，同一脚本串行。ctx.workspace 和 ctx.data_dir 是目录路径，可用 pathlib 操作。ctx.log 写执行日志，print 也会写入日志。`await ctx.notify(text, send_result_to_source=True, include_context=False)` 发固定通知，网页始终可见。wake 的 data 临时注入当前唤醒，不污染历史。普通执行和工具结果只记入执行记录，不注入主上下文。

ctx.call 通过统一注册表调用当前可用插件的工具，参数验证和调用记录与 Agent 工具相同。显式 error 或 success=false 的结果会转成 ScriptToolError；某些旧插件可能返回普通文本，应按其工具文档检查业务结果，不能猜任意字符串就是成功。必要时主动 raise RuntimeError 才能触发失败策略。

绑定有 none/wake/notify 失败策略、连续失败次数、冷却时间和是否报告主对话源。不要在每次成功运行后唤醒 Agent。脚本默认 merge：同一脚本运行中有新事件时保留一个待处理任务，用最新事件替代旧待处理输入。queue 逐个处理，skip 忽略忙碌时的新触发。程序要处理每条事件时选 queue。

用 script_run 主动运行，返回 ID 后用 script_execution get 查询结果/日志/工具调用；停止运行也通过 script_execution。中断的外部操作可能已执行，不能自动重放。重启保留未启动队列，已开始执行的标为中断。删除需 confirm=true，先停止任务并删除绑定。删除注册保留版本与私有数据供审计。

触发源是软声明：未声明的 source 也可以绑定，允许 `*` 通配。比如 `mattermost.slash.*` 匹配所有指令，`mattermost.slash.weather` 仅匹配 /weather。未知 source 不代表出错或禁止绑定；若没有事件生产者则不会运行。声明出现后按 Schema 校验参数，有变化时再编辑绑定。Mattermost Slash 需用户配置服务自己的验证令牌，不能使用管理令牌，不自动唤醒 Agent。

仅需收到事件后让主智能体处理时，不必写中间脚本：使用 script_binding 保存 target_kind="wake"、prompt（必填）和 send_result_to_source。事件观测数据自动作为本轮临时信息提供；提示词是普通文本。省略 target_kind 仍按原脚本绑定处理。

具名事件来源（不含 `*`）只能绑定一个动作，停用也占用；先 list 查找已有绑定并使用其 id 更新。泛事件允许多个绑定。

优先用对象泛事件声明：HA entity_state_changed.* / entity_turned_on.* / entity_turned_off.*；ScanElf device_state_changed.* / device_online.* / device_offline.* / device_discovered.*；Minecraft observation.*、server_online.*、server_offline.*、players_reached.*、players_below.* 等。先 sources 查看完整清单与参数。可在同一泛事件上创建多个不同对象或阈值的绑定，不要把全体对象绑定到无后缀的旧具名来源。具体后缀分别为实体 ID、标准大写 MAC、服务器 ID；也能用泛来源加参数筛选。


绑定事件前先调用 script_binding(action="sources")，阅读 event_schema.description、id_description、parameters 和 event_schema.examples。业务字段从 ctx.event["data"] 读取，不能把示例值当成实际值。按 description、x-unit、x-enum-descriptions 理解时间单位、时区、枚举和空值；ctx.event["at"] 是框架分发的 Unix 秒，不一定等于业务发生时间。未声明来源可以软绑定，但变量结构未知时不能凭空猜测。


## 类型化开发流程

1. 新建或修改前调用 `script_development`：传入 sources、parameters 和需要的 tool_plugins（如 utilities、ha_control）。返回 SDK 的 next_offset 非空时继续分页，携带 sdk_hash 防止定义变化。已有脚本可传 id。
2. 使用 `from script_types import ScriptContext`，入口写成 `async def main(ctx: ScriptContext) -> object:` 或明确返回类型。ScriptContext 是框架按该脚本事件/参数/工具生成的类型，运行时由框架提供，不要自己创建 ctx。
3. `ctx.event` 和 `ctx.params` 是普通字典，不能写 `.data` 或 `.source`。必填字段直接下标，可选字段使用 get，null 只按声明处理；不要猜类型后写兼容两种访问方式的代码。
4. 调用工具用 `await ctx.tools.<插件ID>.<工具名>(参数名=值)`。参数和返回结构以 SDK 为准。尚未声明返回类型的旧工具返回 object，并产生诊断；不要猜其结果结构。ctx.call 为兼容动态接口，会产生警告。
5. `script_manage(action="check", code=..., parameters=..., event_sources=[...], tool_plugins=[...])` 可提前检查，不保存。save 每次重新检查，未通过返回 saved=false 和 diagnostics（行、列、规则、错误/警告）。不得把它当成保存成功，也不应自动添加 hard=true 跳过问题。
6. 确认类型诊断属于有意兼容而非错误时才使用 hard=true 和 hard_reason。语法错误、入口结构错误和检查器不可用不能强制保存。强制记录保存在该版本的 validation 中。
7. 新脚本保存时同步传 event_sources 和 tool_plugins，使其与开发时一致。未知来源仍可绑定，但无法证明其数据类型，会产生警告。一个脚本绑定多个来源时类型为联合类型。
8. 新版本保存生成固定 SDK 快照，执行时加载该版本的 script_types。手动运行事件脚本需提供完整 event={id,source,at,data}，否则不会凭空生成符合业务结构的假事件。

检查仅进行静态分析，不会导入或执行脚本，也不会触发插件工具、远程 API 或设备操作。既有版本不会升级时自动检查或重写，只在下一次修改保存时进入新流程。


现有工具的参数与返回契约可通过 script_development 的 SDK 或 script_tools 的 result_schema 读取。`result_contract_kind=fixed` 表示固定结构/确定联合，mixed 包含动态原生响应，dynamic 的具体字段由端点或服务决定。通用 API 的动态字段不是“遗漏类型”，不要猜对象键；先选择准确接口并查文档。像 mattermost_send 的 id、part_count、post_ids 已是固定声明。工具失败按 SDK 的异常约定处理；真正成功的文本返回与多 action 成功联合按声明区分，不要把失败文本当作成功对象。


HA ha_query 成功直接返回固定 QueryResult，可用 result["entities"] 和 entity["state"]；state 的键存在，但值可能为 None。不需要同时兼容字符串失败结果。HA、ScanElf、Minecraft、和风天气、AList、SSH 的已知失败入口现在抛异常，脚本侧用 `from sakubot.automation.sdk import ScriptToolError` 捕获确实需要恢复的失败，不要用 isinstance(result, str) 把失败当正常分支。多 action 的真实成功联合、部分执行结果和子服务错误映射仍需按 SDK 语义处理。更新后重新读 script_development 取得新类型；不要反复用旧 SDK 快照的 NotRequired 定义猜实际返回。
