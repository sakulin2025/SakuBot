# 系统管理

SakuBot 0.23.0 增加可选内置插件 `system_control`。默认停用，在插件列表启用“系统管理”后，主智能体获得管理函数与 Skill。协作智能体和脚本不会获得这些函数。普通人格的插件列表不屏蔽这项显式授权，`with_tools(False)` 仍禁止全部工具。

开关控制框架的正式管理接口，不是文件系统沙箱。已有 Shell 和可信 Python 插件仍遵循进程自身的文件访问权限。

## 架构

| 模块 | 职责 |
| --- | --- |
| `control/operations.py` | SQLite 操作队列、状态、脱敏结果、构建日志 |
| `control/plugins.py` | 发现、启停、重载、删除、导入导出 |
| `control/configuration.py` | 配置验证、增量应用，不再全量停止 Runtime |
| `control/projects.py` | 开发项目、版本检查、静态检查、Vue 构建、发布和代码回滚 |
| `control/restart.py` | 重启意图、监督进程通信、恢复唤醒 |
| `control/service.py` | 框架拥有的执行队列和共享管理入口 |
| `supervisor.py` | 父进程托管工作进程，不需要 Docker socket |
| `plugins/system_control` | 主智能体工具、Skill、管理页面 |

管理面板与智能体使用同一套底层服务。队列和操作查询 API 不依赖插件生命周期。插件停用会取消尚未执行的智能体管理请求；正在执行的操作由核心收尾。

## 工具

| 函数 | 功能 |
| --- | --- |
| `system_status` | 版本、平台、运行状态、重启支持、插件和脱敏配置 |
| `system_plugins` | 列表、增量扫描、启用、停用、重载、删除、ZIP 导入导出 |
| `system_config` | 读取或更新框架 Settings |
| `plugin_project` | 创建、签出、编辑、检查、构建页面、发布、历史版本和回滚 |
| `system_operations` | 查询结果、构建日志，取消尚未执行的操作 |
| `system_restart` | 本轮结束后重启，可在新进程中继续目标 |

变更返回持久 `operation_id`，不代表执行成功。主智能体提交的操作等当前 wake 完整结束并保存后执行，不能在当前轮循环等待。操作完成或失败后，会发送一次去重的 wake 告知主智能体，再查询操作详情并继续目标；报告标志沿用提交时的 `send_result_to_source`，网页始终可见。重启本身仅在提供 `resume` 时唤醒。

操作状态：`queued / running / done / failed / cancelled / interrupted / restarting`。进程中断后，已经执行中的操作标为 `interrupted`，不会重放；未开始的操作继续排队。重启意图独立恢复。

## 插件生命周期

`scan` 读取插件清单和程序哈希，返回新增、变更和消失的插件，不自动执行代码。新目录须明确启用。

重载清理目标插件的注册项和 Python 子模块缓存，再执行入口与启动钩子。默认等目标插件的工具与智能体任务结束，最多等待五分钟；`force=true` 才中断任务。基础能力不能单独停用、删除或重载，需要时重启系统。

代码回滚仅恢复程序，不回滚数据迁移、已发消息、SSH 命令或外部设备操作。Python 依赖的已导入模块不能靠单插件重载可靠替换，依赖变化后应重启。

## 开发目录与流程

```text
/data/plugins/              已安装运行程序
/data/plugin_projects/      开发项目，不自动执行
/data/plugin_revisions/     发布前保存的旧版程序
/data/plugin_data/          原有配置与业务文件
/data/workspace/artifacts/  导出的 ZIP
/app/plugin-sdk/src/        公共 Vue 组件、主题和插件 SDK
/app/plugin-sdk/docs/       开发文档
/app/plugin-sdk/build-page.mjs
```

通过 `plugin_project`：

```json
{"action":"create","id":"example_plugin","label":"示例","with_page":true}
```

`create` 生成使用公共 Plugin API 和 `@sakubot/ui` 的脚手架。修改既有第三方插件使用 `checkout`，不会覆盖已有开发目录。

1. `read` 取得文件内容与 `file_version`。
2. `write` 提供 `path/content/file_version`，并发变更时拒绝覆盖。
3. `check` 检查 Python 语法、JSON 清单和 requirements 依赖。
4. 有页面时提交 `build`；在收到完成唤醒后，再次 `check`。
5. `publish` 传最新 `check` 返回的项目 `version`。旧版保存在 revisions。
6. `versions` 列出版本，`rollback` 传 `revision` 恢复。

页面源码变化后须重新构建。构建是生产打包，不运行测试。依赖检查支持版本与平台条件；缺失或不满足时拒绝发布，不自动安装依赖，不接受外部 URL。Python 依赖由镜像或已有 `/data/plugin_dependencies` 提供。SDK 自带公共 Vue/Vite 依赖，不自动安装插件自定义 npm 依赖。

替换已有插件失败时尝试恢复旧程序并重新加载，首次发布失败时移除失败程序。回滚失败会记录错误，不假报成功。

## 重启与恢复

启动入口为 `python -m sakubot`。监督父进程监听随机本地端口，用每次启动生成的内部凭据接受重启通知，凭据不暴露给模型。收到外部停止信号时停止整个服务。内部重启至少间隔 30 秒，15 分钟最多三次。

重启等当前主轮和其他智能体任务结束，期间不认领新的主队列事件。Shell 后台任务在停机时停止，重启不续跑。参数示例：

```json
{
  "reason":"应用新依赖",
  "progress":"配置已保存，尚未检查依赖导入；没有需重放的设备操作",
  "resume":"查看插件状态并继续整理开发项目",
  "send_result_to_source":false
}
```

新进程将 `resume` 转为带固定去重标识的新 wake，不恢复旧协程、不重放旧工具。主智能体停用或模型未配置时暂缓恢复唤醒，不自动启用。

Compose 建议保留 `init: true`、`stop_grace_period: 60s`。直接启动 `sakubot.web:app` 没有监督父进程，内部重启明确返回不支持。

## 公共接口

```python
receipt = runtime.control.submit('plugin.reload', {'id': 'example_plugin'})
operation = runtime.control.operations.get(receipt['operation_id'])
# 智能体适配器传 invocation=inv，服务会检查主智能体和授权插件状态。
```

可信管理面板沿用原登录：

- `GET /api/system-control`
- `GET /api/system-operations`
- `GET /api/system-operations/{id}`
- `POST /api/system-operations`，正文 `{"action":"...","payload":{...}}`
- `DELETE /api/system-operations/{id}`，仅取消排队项

工具声明支持 `self.tool(..., audience='main')`，仅主智能体的模型调用可见并可执行；页面 `call_tool()`、脚本和协作智能体均不可见。默认 `all` 保留原语义。
