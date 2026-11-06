---
name: script-automation
description: 创建、修改和绑定事件脚本，查询插件当前文档与工具说明。
---

# 每次开发必须重新查阅

每次新建或修改脚本，都必须重新读取本技能，并调用 script_development 查阅本次涉及插件的当前文档、工具说明、参数、返回说明及事件示例。传入相关 tool_plugins 和 sources；next_offset 非空时继续读取并携带 documentation_hash，直到读完。

禁止凭记忆、经验、上次开发结果猜方法名、参数、字段、返回形式或事件结构。缺少文档时先读取插件源码或询问用户，不能编造字段、用一堆猜测性兼容分支替代查阅。script_tools 可补充查询最新方法目录。

# 接口

入口为 main(ctx,event,tools)，可以同步或异步。三个参数都是真正的普通 dict，不导入 SDK、不依赖类型快照或强制注解。

- ctx：run_id、script_id、workspace、data_dir、params；params 为普通 dict。
- event：id、source、at（Unix秒）、data（插件提供的普通 dict）。业务字段须查看当前插件文档。
- tools：完整方法名到可调用函数。插件方法使用 await tools["方法名"](参数名=值)，无需插件 ID，不使用点式命名空间。

```python
async def main(ctx, event, tools):
    tools["script_log"]("事件到达", source=event["source"])
    return {"id": event["id"], "data": event["data"]}
```

# 运行方法

- await tools["script_wake"](content, data=None, send_result_to_source=True)：唤醒主智能体。
- await tools["script_notify"](content, send_result_to_source=True, include_context=False)：固定通知。
- tools["script_log"](message, **data)：同步写执行日志，也可 print。
- tools["script_state_get"](key, default=None)：同步读取该脚本持久状态。
- tools["script_state_set"](key, value)：同步保存 JSON 状态。
- tools["script_state_delete"](key)：同步删除状态。

插件工具执行失败会抛异常；仅明确可恢复时捕获。不能仅根据结果有 error 或 success=false 推断整个调用没有执行，要按照当前工具文档解释业务结果。写入结果不确定时先查询，不盲目重试。

# 保存与绑定

修改前读取现有脚本，保存携带 expected_version。保存仅检查 Python 语法和三参数入口，不执行代码，不做类型检查，没有 hard 或强制保存流程。script_manage(action="check") 可检查语法，但不验证业务正确。

每次用 script_binding(action="sources") 重新读取事件说明；options 获取动态选项。事件为软声明，未声明来源和通配来源也可绑定。具名来源只能绑定一个动作，已有绑定应编辑。动作可为脚本或 wake 提示词。

运行固定代码版本。超时或中断不能撤销外部操作；未获授权时不试运行有外部效果的脚本。脚本是可信本地代码，独立进程不是安全沙箱。
