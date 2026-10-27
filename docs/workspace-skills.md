# 工作空间与 Skill

版本：0.10.1。

## 持久化目录

```text
data/
├── workspace/
│   ├── AGENTS.md
│   ├── notes/
│   ├── projects/
│   ├── artifacts/
│   └── tmp/
├── skills/
├── plugins/
└── plugin_data/
```

框架自动创建这些基础目录。AGENTS.md 仅在缺少时建立默认内容，不覆盖用户修改。目录在宿主机是 ~/ContainerService/napcat/data/sakubot，容器中是 /data。内置插件仍随镜像分发，外部插件保存在 data/plugins。

工作空间由框架提供持久文件服务，通过内置 workspace 插件暴露 AI 工具和页面；插件页面和路由来自插件声明，停用即撤销。Skills 索引由框架提供，读取工具由 skills 插件注册。插件使用公共 API。

## 文件管理

页面在左侧“插件 / 工作空间”。支持目录、搜索和分页、创建目录或文本文件、UTF-8 文本编辑、上传下载、移动重命名、删除。上传重名文件先显示覆盖确认。符号链接显示为不可操作条目。

文本编辑上限 1 MiB，超过上限和二进制文件可以下载；单次上传上限 20 MiB。页面没有自动保存，只有显式保存。弹窗不因点击遮罩或 Esc 关闭。

文件工具：workspace_list、workspace_read、workspace_write、workspace_edit、workspace_patch、workspace_mkdir、workspace_move、workspace_remove。所有路径相对于工作空间，禁止绝对路径、路径穿越和符号链接。默认删除仅处理空目录；recursive=true 才递归删除。

list 返回 path、items、total、offset、has_more。条目包含 name、path、type、size、modified、version。read 返回带行号的 numbered_content、原文 content、version、size、binary、offset、next_offset、total_lines、has_more；offset 从 0 开始，limit 最大 500 行，单次文本最多约 60000 字符。超过页长度使用 next_offset，不按固定行数猜测下一页位置。超长单行使用文件下载。

局部修改不再要求 version 相同。workspace_edit 按 old 唯一匹配，workspace_patch 接受 hunks=[{start_line,old,new}]，按原文重新定位漂移的行号，所有修改块验证通过后一次写入。原文变化、不唯一或修改块重叠才报冲突。整文件覆盖可传 base_content 比较完整正文，或继续提供 version；移动删除和页面覆盖保留版本保护。版本根据 inode、大小、纳秒修改时间和状态时间生成。新文件可省略 version，已存在时拒绝直接覆盖。

冲突会返回 HTTP 409，重新读取并合并后再保存。文件页保留当前编辑内容，提供“重新读取”操作。目录版本用于检测目录自身和直接条目的变化，不代表整个子树的内容快照。显式递归删除仍会删除选定目录的完整子树。

所有 Agent 共用文件，单例上下文各自独立。重置不清理文件，tmp 不自动清理。框架文件操作使用进程内锁及原子替换；外部程序直接改文件不参与该锁，版本检测降低无意覆盖，工作空间不是进程沙箱。

## Skill 文件

独立安装：`data/skills/example/SKILL.md`。
包插件内置：`插件目录/skills/example/SKILL.md`。

```markdown
---
name: 示例技能
description: 需要某类操作流程或资料时使用。
---
# 示例技能

按需读取 references/guide.md，再使用对应工具完成工作。
```

YAML 元数据要求 name 和 description 为非空字符串，支持标准 YAML 多行语法。SKILL.md 最大 128 KiB。附属资料可放 references、scripts 等子目录；读取不会执行脚本。

完整 ID：`插件ID.技能目录名` 或 `local.技能目录名`。目录 ID 支持字母、数字、下划线和连字符。中文展示名放在 name。插件自带目录名以外也可显式注册：

```python
self.skill("example", Path(__file__).parent / "guides" / "example")
self.remove_skill("example")
```

加载包插件时自动扫描 skills 的直接子目录，显式同 ID 声明优先。插件停用、删除或重载时自动撤销声明，重新启用再注册。加载后新增目录需要重载插件或显式调用 self.skill；现有 SKILL.md 的修改在后续读取时生效。独立技能目录按需扫描，无需重启。

内置工作空间插件附带 workspace.files；专业团队插件附带 team.collaboration。管理页“能力 / 技能”列出当前已启用插件声明的技能和独立技能；只提供正文和附属文件查看，无写入、编辑、删除或开关操作。

## 模型加载

每次模型请求前，框架为所有 Agent 刷新人格可见的工作空间约定和 Skill 索引。工作空间约定最多读取 AGENTS.md 前 8000 字符。技能索引最多约 16000 字符，描述各截取前 400 字符；数量较大时用 skill_list 搜索分页。

- skill_list(query?, offset=0, limit=50)：当前人格可见技能，最多 100 条一页。
- skill_read(id)：完整 SKILL.md、元数据与附属文件索引（最多 500 项）。
- skill_read_file(id, path, offset=0, limit=200)：读取指定参考文件，按行分页。

Skills 插件关闭或人格隐藏该插件时，不注入索引或提供读取工具。插件内置技能还需要其所属插件对该人格可见。不存在新的管理员或会话权限层。

索引属于每轮刷新的系统上下文，不被历史压缩永久移除；完整正文作为工具结果按需加载，可能参与后续历史压缩。停用技能不会抹除已经写入历史的工具结果，但后续索引和读取立即撤销。Skill 是操作指导，不会自行执行代码。

## 接口

所有管理接口使用现有管理令牌。

| 接口 | 行为 |
| --- | --- |
| GET /api/skills | 当前已发现技能和无效技能记录 |
| GET /api/skills/{id} | 技能正文和附属文件索引 |
| GET /api/skills/{id}/file?path=... | 附属文件分页正文 |
| GET /api/extensions/workspace/files | path / offset / limit / query |
| GET /api/extensions/workspace/file?path=... | 编辑器文档与版本 |
| POST /api/extensions/workspace/file | path / content / version |
| POST /api/extensions/workspace/mkdir | path |
| POST /api/extensions/workspace/move | path / destination / version |
| POST /api/extensions/workspace/remove | path / version / recursive |
| PUT /api/extensions/workspace/upload?path=...&version=... | 原始二进制请求体 |
| GET /api/extensions/workspace/download?path=... | 附件下载 |

文件的写入、移动和删除记入 workspace 追踪日志；AI 工具调用另有框架调用记录。页面操作与 AI 工具共用版本检查和文件服务。


## 直接 Shell（0.10.1）

workspace_shell(command, cwd='', timeout=60) 在容器内通过 /bin/sh -c 运行命令，支持管道、重定向和已安装程序。初始 cwd 相对于 /data/workspace；命令可通过 cd 或绝对路径访问容器用户可访问的其他位置，不是沙箱，也不授予额外宿主机挂载或权限。默认目录不需要配置。

返回 exit_code、timed_out、output（合并 stdout/stderr）、truncated、output_bytes、cwd、duration_ms。超时范围1～600秒，还受 Agent 运行预算限制。输出持续排空，最多保留前48 KiB和后16 KiB，超出时标记截断。

每次调用是独立非交互进程，stdin 为 EOF，工作目录与环境变量不跨调用保存。调用结束、超时、取消或插件停用时清理其进程组，普通调用不提供持久终端会话或后台服务；长任务使用下面的后台接口。脚本运行能力由该工具提供；Skill 读取自身不会执行代码。

插件可用 `await self.workspace.shell(command, cwd='', timeout=60)` 复用接口。Shell 修改不经过文件 API 的版本检查，Agent 需要协调共同文件。文件页与原有文件工具继续提供版本保护。

### 目录版本

`workspace_list` 和公共 `workspace.list()` 返回顶层 `path`、`version`，代表正在浏览的目录；每个 `items` 条目中的 version 只代表对应子项。可直接列出目标目录取得移动或删除所需的版本，空目录同样适用，无须列出父目录。查询过滤和分页不改变顶层版本的含义。

`mkdir` 返回创建时的版本；目录条目新增、删除、重命名后，应重新 list 该目录。列表构建期间检测到目录版本变化会报错，调用方重新获取即可。目录版本仍为目录自身的元数据版本，不等同于递归内容快照。

## 后台 Shell（0.15.2）

镜像内置 curl、git、jq、ripgrep（rg）、Node.js（node、npm）、ffmpeg（含 ffprobe）、sqlite3 和 CA 证书。工作空间插件提供 workspace_shell_start、workspace_shell_status、workspace_shell_list、workspace_shell_stop。

start(command, cwd='', description='', timeout=3600) 立即返回任务 id，后台执行独立于 Agent 回合和重置。直接传前台命令，不加 &、nohup 或自行 daemonize；stdin 为 EOF。超时范围1～604800秒，同时最多16个任务。status(id, wait_seconds=0) 返回状态和合并输出，可等待0～30秒；结束后由工作空间插件默认以 wake 事件唤醒主 Agent，带上发起 Agent、任务 ID、退出码和输出，无需轮询；工具参数 notify=false 可关闭。list 返回最近100条共享任务（不含输出），stop 终止整个进程组。

状态为 running、completed、failed、timed_out、cancelled、interrupted。输出持续排空，只保留前48KiB和后16KiB。记录保存在 /data/shell_jobs，持续输出约每秒落盘，完成立即保存；异常退出可能丢失最后一段输出。插件停用、重载、正常关机会停止任务。重启把遗留 running 标为 interrupted，不自动恢复命令。记录用于查询，不是服务自启动配置。

插件可通过 self.workspace.shell_runner.start/list_jobs/job/cancel_job 使用相同接口；start/list_jobs 同步，job/cancel_job 异步。

## 后台任务完成事件（0.15.5）

工作空间插件管理通知循环，Shell 服务仅保存完成记录及通知状态。完成、失败、超时、取消和重启恢复为 interrupted 均可触发事件；以 shell-result:任务ID 作为幂等事件 ID，先入持久队列再标记已通知，避免重启重复入队。主 Agent 暂停时事件等待，恢复后处理。插件卸载停止通知循环，重新启用后补入未通知结果。后台任务不自动重跑。

公共 Shell.start 的内部参数 _completion 可记录 agent_id、actor、run_id；插件工具自动填写，不由模型指定。Shell.pending_notifications()/mark_notified(id) 由通知方使用。
