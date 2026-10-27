---
name: 工作空间与 Shell
description: 创建或维护项目、笔记、草稿、报告，执行容器命令或脚本时使用；说明直接 Shell、共享文件协作及文件 API 的版本检查。
---
# 工作空间与 Shell

所有 Agent 共用 /data/workspace。可用 workspace_shell 直接执行 /bin/sh 命令，支持管道、重定向、文件操作和 Python。

1. 默认 cwd 是 /data/workspace；后续调用可传相对子目录。每次都是独立进程，cd、变量和虚拟环境激活不跨调用保留，在同一 command 中完成有关操作。
2. 命令在 SakuBot 容器中运行，使用容器当前用户的文件及网络访问能力。初始目录不是沙箱边界，容器没有挂载的宿主机文件不会自动可见。
3. 项目资料放 projects/项目名，持续资料放 notes/，完成产物放 artifacts/，临时内容放 tmp/。先查看目录及相关文件，再修改。
4. 读取大文件时限制输出，例如 sed、head、tail；也可用 Python。工具输出最多保留约64 KiB，返回 truncated、exit_code 和 timed_out。
5. timeout 默认60秒、最多600秒，还受当前 Agent 剩余执行预算影响。超时、取消或停用会清理调用的进程组；普通调用不能保留后台进程，耗时工作改用 workspace_shell_start。
6. 执行脚本前先阅读并理解内容。skill_read 返回技能的 directory，可据此找到附属脚本。读取技能不会自动运行脚本。
7. 多名成员同时工作时明确各自的输入和产物路径，避免同时写同一个文件。Shell 写入不提供文件 API 的 version 检查。
8. 局部修改使用 workspace_patch(path, hunks=[{start_line, old, new}]) 或 workspace_edit(path, old, new)，不必提供 version。old 是带必要上下文的唯一原文，不带行号前缀；行号漂移不拦截，目标原文已变或不唯一才报冲突。整文件覆盖可提供 base_content 比较原正文，或继续提供 version；移动删除仍用版本保护。
9. 文件持久保留，重置 Agent 不会清理文件。Python 等程序仅限镜像中已安装的工具和依赖，缺失时先检查环境，不能假定程序存在。

目录版本：`workspace_list(path="tmp/example")` 返回的顶层 `version` 属于 tmp/example 目录本身，`items[*].version` 属于各子项。移动或删除 tmp/example 时直接使用顶层版本，不需要绕到父目录获取。`mkdir` 的版本仅对应创建时状态；目录内新增、删除或重命名条目后，先重新 list 再操作。分页或搜索不改变顶层 version 的含义。目录版本基于目录元数据，不是整棵子树内容的快照；递归删除前仍需检查目标范围。版本冲突后重新查看并判断，不要绕过版本检查。

## 后台任务

镜像已内置 curl（HTTP 请求和下载）、git（代码仓库）、jq（JSON 处理）、rg（快速搜索文件内容）、node 和 npm（JavaScript 与依赖管理）、ffmpeg 和 ffprobe（音视频处理和媒体信息）、sqlite3（SQLite 数据库命令行）。

- workspace_shell_start(command, cwd='', description='', timeout=3600, notify=true)：立即返回任务 id，进程继续运行。直接传命令，不添加 &、nohup，不自行 daemonize。默认1小时、最长7天，同时最多16个任务。
- workspace_shell_status(id, wait_seconds=0)：查看状态、实时合并输出和退出码；可等待最多30秒。任务未结束返回 running，避免频繁轮询。
- workspace_shell_list()：查看所有共享任务及用途，最近的在前。
- workspace_shell_stop(id)：结束任务及其进程组，保留输出。

适合构建、下载、批处理、临时开发服务。后台任务独立于当前 Agent 回合和重置；结束后默认以主动事件唤醒主 Agent，附上发起 Agent、任务 ID、退出码和输出，无需轮询；notify=false 可关闭主动唤醒。不要在任务启动后声称已经完成。stdin 仍为 EOF，不提供交互终端。

插件停用、重载或容器正常关闭会停止任务；异常重启后未完成任务标为 interrupted，不自动重跑。任务记录和有限输出保存在 /data/shell_jobs，最多保留100条，每条最多保留前48KiB和后16KiB。持续输出约每秒保存一次，异常退出可能丢失最后一段输出。所有 Agent 共用任务，停止前确认用途。

## 带行号的内容补丁

workspace_read 同时提供 content 原文与 numbered_content 行号视图（行号从1开始）。用原文构造修改块，例如：

```json
{"path":"projects/example/app.py","hunks":[{"start_line":12,"old":"timeout = 30\n","new":"timeout = 60\n"}]}
```

所有修改块相对于同一份文件；框架在当前文件唯一匹配每个 old，支持其他位置变化和行号漂移。验证所有修改块无冲突、无重叠后一次写入，返回 matched_line、shifted 和新版本。添加内容时把相邻原文包含在 old/new 中作为锚点；删除内容时 new 为空。多处匹配请扩大 old 的上下文，不根据过期行号猜测。

附件交付：workspace_publish(path, kind="auto", send=true) 发布共享工作空间文件；主 Agent 默认同时发送到主对话，协作 Agent 返回附件元数据交给主 Agent，URL有效7天，不删除原文件。不要把容器本地路径当 NapCat 或浏览器可访问的 URL。
