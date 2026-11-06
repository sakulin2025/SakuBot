# 事件与脚本

系统功能 → 事件与脚本。运行器随框架启动，不依赖主智能体是否启用。

## 开发和入口

Agent 每次新建或修改脚本前，必须重新读取 script-automation 技能，并调用 script_development 查阅相关插件的当前文档、方法说明、返回资料及事件示例。不能凭记忆经验猜接口；缺少文档时先读插件源码或询问。tool_plugins、sources 可缩小资料范围；返回 next_offset 时继续分页，并携带 documentation_hash。

```python
async def main(ctx, event, tools):
    result = await tools["calculate"](expression="1+1")
    tools["script_log"]("完成", result=result)
    old = tools["script_state_get"]("last")
    tools["script_state_set"]("last", result)
    if old is not None and old != result:
        await tools["script_wake"]("结果变化", data=result)
    return result
```

ctx、event、tools 均为普通 dict，不支持属性命名空间。ctx 含 run_id、script_id、workspace、data_dir、params；event 含 id、source、at（Unix秒）、data（普通dict）；tools 按完整方法名索引可调用函数，无需插件 ID。插件工具为异步调用。

运行器本地同步方法：script_log(message, **data)、script_state_get(key, default=None)、script_state_set(key, value)、script_state_delete(key)。异步方法：script_wake(content, data=None, send_result_to_source=True)、script_notify(content, send_result_to_source=True, include_context=False)。这些方法同样通过 tools 字典调用。

保存只检查语法和 main(ctx,event,tools) 入口，无类型检查、SDK生成或强制保存。更新须携带 expected_version。工具失败抛异常；返回对象里的 error/success 仅为业务数据，不自动改判调用失败。

## 软事件

```python
self.trigger_source("temperature_changed.*", "温度变化",
    event_schema={"description":"温度变化", "examples":[{"temperature":28}]},
    id_description="temperature_changed.<entity_id>")
await self.emit_trigger("temperature_changed.sensor.lab", {"temperature":28})
```

parameters、event_schema、说明和示例可选；不会因缺少字段描述、完整示例或声明而拒绝加载。不会根据文档校验触发 payload。事件 data 必须是可JSON通信的 dict。泛来源与尚未声明来源都可以绑定；具名来源只能绑定一个动作，动作可为脚本或 wake 提示词。

插件可提供 subscribe、options、match、validate 回调，实现监听、选项和业务筛选；subscribe 返回清理函数，停用或重载插件时解除订阅。既有轮询与去重不变。

## 存储与执行

data/scripts/<id> 保存源码、版本和 manifest；data/script_data/<id>/state.json 保存私有状态；数据库保存注册、绑定和日志。状态上限256 KiB。升级为旧单参数脚本创建新版本，绑定和历史保留；旧版本执行前进行单向源码迁移，不恢复旧SDK。

同脚本串行，不同脚本最多并行8个。merge 保留一个待执行任务并替换最新输入；queue 逐条执行；skip 忽略忙碌时的新事件。重启后排队任务可以继续，运行中任务标记中断，不自动重放。删除需解除绑定并停止任务，历史和产物保留。

失败策略支持仅记录、wake、notify、连续失败阈值和冷却。进程隔离不是安全沙箱，取消和超时不能撤销外部动作。
