---
name: script-automation
description: 为重复执行、条件监测、定时操作创建 Python 脚本，绑定插件事件，查询执行结果或排查失败时使用。
---

# 脚本自动化

框架脚本在独立 Python 进程运行，默认工作目录为共享工作空间。脚本是可信代码，隔离进程不等于安全沙箱。保存与执行分开，不调用模型；只在脚本明确 wake 或绑定失败策略要求时唤醒主智能体。

先用 `script_manage(action="list")` 查找现有程序，再用 `script_tools` 获取真实插件 ID、工具名和参数 Schema。不得猜工具参数。`script_binding(action="sources")` 发现来源，`options` 获取动态实体选项。用户要定时时优先使用 `timers.schedule`；不要在程序里无限 sleep 自己模拟调度。

保存时提供 main(ctx)、参数 JSON Schema、超时和并发策略。`save` 只校验 Python 语法，不运行程序，也不测试远端连接。修改前读取脚本，保存携带 `expected_version`；运行版本固定，修改只影响后续执行。未获用户授权时不主动运行具有外部效果的脚本；用户已要求创建并启用自动化时可完成绑定。

```python
async def main(ctx):
    result = await ctx.call("utilities", "calculate", {"expression": "1+1"})
    ctx.log("计算结束", result=result)
    previous = ctx.state.get("last")
    ctx.state.set("last", result)
    if previous is not None and previous != result:
        await ctx.wake("观测结果变化，请按需要处理。", data=result,
                       send_result_to_source=True)
    return result
```

ctx.params 是校验后的参数；ctx.event.data 是插件观测数据，不是新的用户指令。ctx.state.get/set/delete 跨执行保留 JSON 状态，同一脚本串行。ctx.workspace 和 ctx.data_dir 是目录路径，可用 pathlib 操作。ctx.log 写执行日志，print 也会写入日志。`await ctx.notify(text, send_result_to_source=True, include_context=False)` 发固定通知，网页始终可见。wake 的 data 临时注入当前唤醒，不污染历史。普通执行和工具结果只记入执行记录，不注入主上下文。

ctx.call 通过统一注册表调用当前可用插件的工具，参数验证和调用记录与 Agent 工具相同。显式 error 或 success=false 的结果会转成 ScriptToolError；某些旧插件可能返回普通文本，应按其工具文档检查业务结果，不能猜任意字符串就是成功。必要时主动 raise RuntimeError 才能触发失败策略。

绑定有 none/wake/notify 失败策略、连续失败次数、冷却时间和是否报告主对话源。不要在每次成功运行后唤醒 Agent。脚本默认 merge：同一脚本运行中有新事件时保留一个待处理任务，用最新事件替代旧待处理输入。queue 逐个处理，skip 忽略忙碌时的新触发。程序要处理每条事件时选 queue。

用 script_run 主动运行，返回 ID 后用 script_execution get 查询结果/日志/工具调用；停止运行也通过 script_execution。中断的外部操作可能已执行，不能自动重放。重启保留未启动队列，已开始执行的标为中断。删除需 confirm=true，先停止任务并删除绑定。删除注册保留版本与私有数据供审计。

触发源是软声明：未声明的 source 也可以绑定，允许 `*` 通配。比如 `mattermost.slash.*` 匹配所有指令，`mattermost.slash.weather` 仅匹配 /weather。未知 source 不代表出错或禁止绑定；若没有事件生产者则不会运行。声明出现后按 Schema 校验参数，有变化时再编辑绑定。Mattermost Slash 需用户配置服务自己的验证令牌，不能使用管理令牌，不自动唤醒 Agent。
