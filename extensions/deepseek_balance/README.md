# DeepSeek 余额轮询

插件设置默认启用轮询，间隔 120 分钟，预警值 10（支持小数）。供应商 ID 留空查询全部 DeepSeek 官方供应商，也可指定单个 ID；复用框架 Key。

首次成功查询只建立基线，此后仅在余额从大于阈值变成小于或等于时触发。持续低于不重复触发，恢复后再次跌破可重新触发。币种分别判断，基线持久保存。账号或阈值变动后重新建立基线；查询失败保留原基线，手动查询不改变基线。启用、重载、保存设置后等待一个间隔再查询。

## 触发源

`deepseek_balance.balance_low.*`（余额跌至预警值）。绑定参数 `provider_id`、`currency` 均可留空匹配全部。

事件 data：`provider_id`、`provider_name`、`currency`、`previous_balance`、`balance`、`threshold`、`fetched_at`。金额为十进制字符串，不包含密钥。

在脚本页面绑定此触发源，由脚本决定直接处理或唤醒主 Agent。插件不会自行发送通知或注入上下文。示例：

```python
async def main(ctx):
    data = ctx.event['data']
    await ctx.wake(
        f"DeepSeek 余额预警：{data['provider_name']}，"
        f"{data['previous_balance']} → {data['balance']} {data['currency']}，"
        f"预警值 {data['threshold']}。请按需提醒主人。",
        data=data,
    )
```

停用插件自动停止轮询、撤销触发源，已有绑定保留。
