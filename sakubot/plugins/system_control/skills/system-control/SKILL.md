---
name: system-control
description: 管理 SakuBot、动态加载或重载插件、开发和发布第三方插件，以及安排重启后继续任务。
---

通过 system_status、system_plugins、system_config、plugin_project、system_operations 和 system_restart 操作框架。只有主智能体可调用这些管理函数。

## 操作与结果

变更通过框架持久化队列执行，返回 operation_id 只代表已接收，不代表成功。主智能体提交的变更在本轮结束且记录保存后执行，不能在当前轮循环等待。操作结束后会自动唤醒主智能体回报操作 ID 与状态，再用 system_operations 查询结果和日志。停用系统管理会取消尚未执行的 Agent 管理请求，当前正在执行的操作仍会收尾。

插件扫描只发现程序，不会执行；明确指定 enable 才启用。重载会清理插件的工具、页面、触发源和声明的智能体。默认等目标插件任务完成，force=true 会中断任务，须有明确理由。基础能力不能单独停用或重载，需要时安排系统重启。

## 开发与发布

1. 先查看现有插件、需求和 SDK 文档，避免重复创建。plugin_project.sdk 返回开发文档位置。
2. create 生成独立开发项目；修改已有第三方插件先 checkout。不要直接修改正在运行的程序。
3. read 获取 file_version；write 带该版本，冲突后重新读取，不强行覆盖。
4. check 进行静态语法、JSON 清单和依赖检查，不运行代码或测试。依赖缺失不会自动安装，需由部署环境提供。
5. 有管理页面时先提交 build，在下一轮查看构建结果。页面使用 @sakubot/ui 公共 Vue 组件和主题。
6. 用最新 check 的 version 提交 publish，运行中的目标插件默认等待空闲；旧版保存在 revisions。加载失败会尝试恢复上一版。
7. versions 与 rollback 可以恢复之前发布的版本。默认保留配置和数据；代码回滚无法撤销插件已执行的数据迁移或外部操作。

开发项目路径为 /data/plugin_projects，发布程序为 /data/plugins，旧版程序为 /data/plugin_revisions。配置和业务数据保持原有位置。

## 重启

system_restart 在主轮结束和其他 Agent 任务结束后通知监督进程重启，无需 Docker 控制权限。提供 reason、progress 和 resume：说明已经完成的操作、结果未知的操作和下一步目标。新进程会以去重的全新 wake 继续目标，不会恢复或重放旧协程、Shell 命令或工具调用。主智能体停用或模型未配置时，恢复唤醒会等待配置就绪。重启之间至少间隔 30 秒，15 分钟最多三次，不要形成自动重启循环。

内置系统管理开关只控制框架正式管理接口，不隔离已有 Shell 或可信 Python 插件对文件系统的访问。
