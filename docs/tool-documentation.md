# 工具文档

工具说明是开发资料，不是返回值验证器或脚本类型系统。每次开发重新读取当前文档；资料不足时读源码或询问，不能凭记忆补全接口。

## 位置和读取

- 模型参数：插件注册函数签名/docstring，或显式注册的 parameters。
- 返回与动作说明：插件目录 tool_documentation.json。
- 使用规则与完整流程：插件 README.md、skills/**/*.md。
- 事件：trigger_source 的可选 event_schema、parameters、id_description、examples。
- 查询入口：script_development 汇总上述当前资料并分页；script_tools 可按方法或插件聚焦。

本轮补齐四个基础工具和六个脚本工具的返回说明，并为 HA、ScanElf、SSH、AList、Minecraft、Mattermost、定时任务和部分系统管理工具补充动作对应关系。

## 文档字段

每个方法名对应一个说明对象，所有字段可选，不参与方法注册校验。

| 字段 | 内容 |
|---|---|
| returns | 返回对象、嵌套字段、类型、是否可省略、null语义、单位和分页方式 |
| actions | 按真实动作值分组的说明；parameters注明条件必填参数，returns注明该动作返回形状 |
| structures | 本方法中多个动作共用的结构说明 |
| variants | 非action分支，例如预览/执行、城市歧义、单服务/概览 |
| example / examples | 调用参数或返回示例；不会执行；占位符不能直接拿去调用 |
| errors | 异常与部分业务失败的区别 |
| notes | 缓存、截断、先决条件、动作副作用等 |

固定字段明确类型；字段存在但可为null与字段可省略分开说明。不要把联合返回理解为所有字段同时存在，先根据action或实际分支读取。

## 动态数据的边界

原生REST/OneBot、HA属性、天气服务data和设备固件扩展字段取决于实际服务版本和所选操作，不能写成虚假的固定结构。已知固定外层和常用字段在各插件文档中说明；其余标为动态并查对应插件实现/服务端API资料。请求失败通常抛异常，但ha_api明确以ok/status/data表示HTTP响应，天气overview保留子服务errors，批量控制保留逐项结果，必须按各自文档解释。

Mattermost原生查询过大可返回truncated/preview/hint；preview是片段而非完整JSON。脚本执行详情的input/output已解析，tool_calls内arguments/output仍为JSON文本，这两层不能混用。

这些资料来自源码阅读，没有设备调用、模型调用或接口实测；不把文档覆盖等同于运行验证。
