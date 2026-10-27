# 基础内置插件（0.18.0）

> 0.20.0 更新：基础能力改由系统自动提供；PDF、Word、表格现合并为一个 office 文档处理插件。当前架构见 [系统能力与扩展](system-and-extensions.md)。

参照当前 AstrBot 的 web_search_tools、message_tools 与已有电脑/定时能力划分；采用 SakuBot 的公共 Plugin API 实现，无 AstrBot 运行依赖，不复制管理员/会话权限控制。

| 插件 | 工具 | 配置 |
| --- | --- | --- |
| 联网 web | web_search、web_fetch | Tavily/SearXNG、服务 URL、API Key |
| 时间与计算 utilities | time_info、time_difference、calculate | 无 |
| 消息发送 messaging | message_sources、message_send | 无，沿用框架主对话路由 |

已有 workspace、memory、timers、skills、team、qq 保持职责，不重复添加文件、记忆、定时、团队或平台接口。

## 联网

管理页由 web 插件声明，位于插件分区；停用自动移除页面、工具与 Skill。配置保存在 data/plugin_data/web/config.json，Key 经公共配置接口脱敏。

- Tavily：选择 Tavily 并填写 API Key；URL 留空使用官方接口，填自有网关时支持根地址或以 /search 结尾的完整端点。
- SearXNG：填写实例地址或 /search 端点，服务需开启 JSON；API Key 为可选 Bearer Token。
- 没有搜索服务配置时，web_fetch 仍可使用；web_search 返回未配置提示，不伪造空搜索结果。
- 搜索使用 basic 深度，最多8条摘要，不请求 AI 答案或完整正文；不自动重试，不自动调用付费服务、不导入旧 Key。
- 静态网页/文本单次响应上限2 MiB；工具正文分页，单页最多12000字符。进程内缓存最多16页、5分钟，插件卸载即清除。不会执行 JavaScript，不解析 PDF 或登录页面。
- 结果保留 URL、抓取时间和缓存状态，Skill 提醒模型将外部内容作为资料而非指令；不强制聊天附带来源。

接口依据：[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、[SearXNG Search API](https://docs.searxng.org/dev/search_api.html)。

## 时间与计算

默认 Asia/Shanghai，支持 IANA 时区、ISO8601、Unix 秒及实际时间差。缺失偏移的夏令时歧义/不存在时间要求显式偏移。数值表达式通过 AST 运算，不执行代码；浮点计算仍有舍入误差。

## 消息发送

支持 text、image、audio、video、file 和工作空间附件。通过 respond_main 接口提交，网页同步，其余目标由框架统一路由。仅主 Agent 输出主对话；子 Agent 交回产物。不调用或内置 NapCat API，不创建平台连接或第二份聊天上下文。

受理结果不等于所有平台送达，实际结果在消息投递记录查看。现有 workspace_publish 和 qq_send 保持可用，各自负责工作空间单文件和 QQ 指定目标。

## 启用

新安装默认启用这三个插件；既有安装可从插件页立即开关。人格若显式限制了可见插件，需要在该人格中选择对应插件；不自动改写用户的可见性列表。所有插件各自附带只读 Skill。

按本会话要求不运行测试；仅执行构建及部署状态确认。
