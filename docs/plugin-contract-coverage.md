# 插件工具与事件契约核对表

日期：2026-11-06。范围：仓库中的系统能力、内置插件、第三方扩展，以及持久卷中的 Bark/Clash Verge；旧 Mattermost 运行卷副本由同名内置插件覆盖，不重复统计。

覆盖140个常规工具（含源码中未安装的3个上下文提醒工具）、5个临时工具、9个插件提供的30类事件声明。核对方式为源码声明/返回分支与函数目录元数据阅读，没有执行插件工具、脚本、远端 API 或设备测试。

参数：原有约束迁入插件自己的 tool_arguments.py（或原生 typed_tool 类型），补齐字段说明；结果：tool_types.py 的 RESULTS 与函数返回注解共用。固定封装与真正动态原生数据明确区分，不把动态字段宣称为全量固定模型。

| 插件 | 工具数 | 参数/返回实现 | 事件定义 |
|---|---:|---|---|
| 时间、计算与图片描述 | 4 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 工作空间 | 14 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 技能 | 3 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 主对话消息 | 4 + 2临时 | 4个常规工具及2个主智能体临时投递开关已补 | 无触发源声明 |
| 长期记忆 | 3 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 事件与脚本 | 6 | 脚本/诊断/执行/绑定/SDK 结构已补；用户脚本 output 和 JSON Schema 内容动态 | 无触发源声明 |
| QQ | 7 | 归档与通知结构已补；OneBot 原生结果保持动态 | 无触发源声明 |
| Mattermost | 7 | 发送固定结构；查询/动作按联合返回，原生 REST 数据动态 | 1类，TypedDict＋说明＋示例 |
| 专业团队 | 8 + 3临时 | 8个常规工具及3个成员临时工具的参数/返回契约已补 | 无触发源声明 |
| 定时任务 | 1 | 参数、返回契约及已知嵌套字段已补齐 | 1类，TypedDict＋说明＋示例 |
| 网络搜索 | 2 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 文档处理 | 16 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 系统管理 | 6 | 操作/项目/状态结构已补；框架配置和插件清单扩展字段动态 | 无触发源声明 |
| DeepSeek 余额查询 | 1 | 参数、返回契约及已知嵌套字段已补齐 | 1类，TypedDict＋说明＋示例 |
| 图库 | 3 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| 热量日历 | 3 | 参数、返回契约及已知嵌套字段已补齐 | 2类，TypedDict＋说明＋示例 |
| Home Assistant | 6 | 实体身份、实时状态、历史记录已分离；查询字段按实际必填；REST data 动态；失败抛异常 | 6类，TypedDict＋说明＋示例 |
| ScanElf | 4 | 设备/本地记忆/分页历史/管理结构已补；游标为整数 | 4类，TypedDict＋说明＋示例 |
| 和风天气 | 2 | 城市与缓存封装已补；天气服务 data 按上游接口变化 | 无触发源声明 |
| AList | 3 | 文件元数据/预览已补；原生文件操作数据动态；失败抛框架异常 | 无触发源声明 |
| SSH 设备 | 6 | 密钥/设备/会话/终端/文件/并行结果已补；失败抛框架异常 | 无触发源声明 |
| 我的世界服务器状态 | 3 | 条目/可达性/人数/查询封装已补；不可达 online=null | 10类，TypedDict＋说明＋示例 |
| FreeReps | 7 | 训练列表/详情/报告封装已补；指标/睡眠等原始服务数据动态 | 1类，TypedDict＋说明＋示例 |
| 音频终端 | 6 | 列表/控制/播放/事件封装已补；固件 status/data 动态 | 4类，TypedDict＋说明＋示例 |
| 上下文提醒（源码中，未安装） | 3 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| Bark 推送（仅运行卷） | 3 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |
| Clash Verge（仅运行卷） | 9 | 参数、返回契约及已知嵌套字段已补齐 | 无触发源声明 |

部署后读取的函数目录包含137个当前可见常规工具，137个均提供返回Schema；mattermost_send 标为 fixed。参数字段说明核对无遗漏。此处仅读取声明元数据，未执行工具。

## 每个插件的工具清单

### 时间、计算与图片描述

`image_describe`、`time_info`、`time_difference`、`calculate`。

### 工作空间

`workspace_list`、`workspace_read`、`workspace_write`、`workspace_edit`、`workspace_patch`、`workspace_mkdir`、`workspace_move`、`workspace_remove`、`workspace_shell`、`workspace_shell_start`、`workspace_shell_status`、`workspace_shell_stop`、`workspace_shell_list`、`workspace_publish`。

### 技能

`skill_list`、`skill_read`、`skill_read_file`。

### 主对话消息

`message_sources`、`message_select_source`、`message_set_source_trust`、`message_send`；临时：`message_enable_delivery`、`message_disable_delivery`。

### 长期记忆

`memory_search`、`memory_write`、`event_search`。

### 事件与脚本

`script_manage`、`script_development`、`script_run`、`script_execution`、`script_binding`、`script_tools`。

### QQ

`people_lookup`、`qq_send`、`qq_read`、`qq_action`、`qq_recent`、`qq_notices`、`qq_api`。

### Mattermost

`mattermost_send`、`mattermost_lookup`、`mattermost_read_posts`、`mattermost_post_action`、`mattermost_file`、`mattermost_request`、`mattermost_command`。

### 专业团队

`team_members`、`team_delegate`、`team_tasks`、`team_create_member`、`team_get_member`、`team_update_member`、`team_requests`、`team_resolve`、`team_report_result`、`team_update_progress`、`team_wait_confirmation`。

### 定时任务

`schedule_manage`。

### 网络搜索

`web_search`、`web_fetch`。

### 文档处理

`pdf_create`、`pdf_merge`、`document_create`、`document_replace`、`document_convert`、`spreadsheet_create`、`spreadsheet_update`、`spreadsheet_recalculate`、`pdf_render`、`document_render`、`spreadsheet_render`、`pdf_read`、`pdf_form`、`document_read`、`spreadsheet_read`、`spreadsheet_errors`。

### 系统管理

`system_status`、`system_plugins`、`system_config`、`plugin_project`、`system_operations`、`system_restart`。

### DeepSeek 余额查询

`deepseek_balance`。

### 图库

`count_pending_images`、`fetch_anime_image`、`gallery_send`。

### 热量日历

`calorie_record`、`calorie_confirm`、`calorie_report`。

### Home Assistant

`ha_initialize`、`ha_query`、`ha_history`、`ha_control`、`ha_manual`、`ha_api`。

### ScanElf

`scanelf_devices`、`scanelf_device_memory`、`scanelf_device_timeline`、`scanelf_device_manage`。

### 和风天气

`qweather_geo`、`qweather_weather`。

### AList

`alist_scan_folders`、`alist_browse`、`alist_write`。

### SSH 设备

`ssh_public_key`、`ssh_device`、`ssh_session`、`ssh_terminal`、`ssh_parallel`、`ssh_file`。

### 我的世界服务器状态

`minecraft_servers`、`minecraft_status`、`minecraft_alerts`。

### FreeReps

`freereps_workouts`、`freereps_workout_detail`、`freereps_activity`、`freereps_metrics`、`freereps_sleep`、`freereps_status`、`freereps_workout_report`。

### 音频终端

`audio_terminal_devices`、`audio_terminal_status`、`audio_terminal_control`、`audio_terminal_stop`、`audio_terminal_play`、`audio_terminal_events`。

### 上下文提醒（源码中，未安装）

`add_context_reminder`、`list_context_reminders`、`remove_context_reminder`。

### Bark 推送（仅运行卷）

`bark_push`、`bark_ping`、`bark_device_info`。

### Clash Verge（仅运行卷）

`clash_status`、`clash_groups`、`clash_select`、`clash_delay`、`clash_connections`、`clash_rules`、`clash_mode`、`clash_tun`、`clash_provider_update`。

## 边界

- 多 action 工具仍使用真实返回联合类型，不根据某次请求伪造唯一结构；调用方需要按实际返回分支读取。
- 原生 REST/OneBot、固件字段与第三方服务原始载荷保留 DynamicObject/DynamicJSON；固定外层、单位、游标和错误分支有明确类型。
- 新读取的 script_development SDK 使用更新后的契约。旧脚本的版本专属 SDK 快照保留，不偷偷改写既有代码。
- 类型声明存在与静态结构核对不等于设备/接口实测；实际返回仍由运行时结果校验处理。


## 必填性和失败分支修正

HA 的 ha_query 成功结果固定为 QueryResult，entities/total/truncated 必填，QueryEntity 的 state/state_text 必填且可为 null。身份资料、实时查询和历史状态不再共用一个全部可选的模型。attributes 仅在 summary=false 时返回，domains 仅在 summary=true 时返回，按真实条件保留可选。HA 控制的预览与执行返回为明确两类，历史记录使用独立结构。

HA、ScanElf、Minecraft、和风天气、AList 与 SSH 的旧异常字符串入口改为抛异常，由框架记录失败，脚本侧收到 ScriptToolError。AList 扫描等真正成功的文本返回保留；批量 HA 控制的逐项结果和天气概览的子服务 errors 保留，不将部分执行包装成全体未执行。

同时修正了 Minecraft 可达/不可达状态的可辨识联合、服务器列表/保存/删除结构，和风天气概览/单服务/选址三类返回，ScanElf 查询页与本地记忆结构，以及记忆保存/删除两类返回。旧脚本 SDK 快照不改写；重新调用 script_development 并保存新版本后使用新类型。
