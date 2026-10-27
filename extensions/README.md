# SakuBot 外部插件

这些包通过公共 Plugin API 加载，不在核心镜像里。开发源码在本目录，部署副本在 `data/plugins`，状态与配置在 `data/plugin_data` 或框架提供的插件命名空间 KV 中。删除程序不删除业务数据。

| 包 | 页面与能力 |
| --- | --- |
| ssh_devices | SSH 设备、公钥、独立会话、Windows PowerShell/POSIX终端、并行执行、SFTP与共享工作空间文件交付 |
| ha_control | HA连接、初始化草稿、房间、实体、别名分组、实时查询、批量控制、用户操作手册 |
| minecraft_status | Java/基岩服务器目录、状态查询、轮询、人数和在线变化主动事件 |
| scanelf | 原生API设备观测、MAC别名描述、上下线时间线分页 |
| qweather | GeoAPI、默认城市、实时/预报/预警等服务、按需缓存感知 |
| alist_manage | 第一层目录忽略/下载/添加/删除策略、浏览、文件操作 |
| deepseek_balance | 复用框架供应商的官方账户余额主动查询 |
| image_gallery | 审核通过图片、图片ID、附件URL、待审核计数与发送 |
| context_reminders | 单一主上下文中的背景提醒、指定目标参考、有效期 |

## 发布

从项目根目录构建所有外部页面：

```sh
node frontend/build-plugins.mjs extensions
```

构建输出在各包 `web/dist`。发布时复制整个包到 `data/plugins/<id>`。在插件页启用或重载；页面、工具、技能随生命周期注册撤销。不要修改核心路由。

首次 AstrBot 迁移使用 `scripts/migrate-astrbot-extensions.py`，只可在 SakuBot 停止时执行；重复运行会拒绝覆盖当前状态。它先在 `backups/astrbot-migration-*` 备份旧源码、配置、相关数据和两个数据库，然后复制包、导入数据并加入启用列表。AstrBot 保持原样。`data/plugin_data/astrbot_migration.json` 是非密钥迁移摘要。备份包含 SSH 私钥和连接凭据，目录权限为700，请按私有备份保管。

依赖持久保存在 `data/plugin_dependencies`，与核心镜像分开，使用同一 Python 进程的依赖搜索路径；这不是依赖隔离或代码沙箱。依赖版本冲突仍需统一解决。此批依赖见本目录 requirements.txt，运行镜像 Python 3.13；不要用宿主机 Python 安装二进制依赖。当前加载不会自动执行 pip。

## 迁移语义

SSH保留同一私钥、服务器指纹、设备与会话记录；网络连接按需重新建立，运行进程不搬迁。HA保留连接、已初始化房间实体、别名分组、手册与草稿；设备策略仍是业务配置，没有框架管理员或会话鉴权。MC保留目录、提醒、观测和基线，主动事件提交主队列；旧会话目的地转换为 main/private:号码/group:号码，不能确定的旧MC目标保留原值并暂停规则，避免误发。上下文提醒保留原目标供追溯，明确目标转换，无法确定类型的旧纯数字目标只进入主上下文背景，不主动发送。

图库服务本身的图片、审核结果仍由原服务保存；旧插件只保存连接配置，没有可迁移的持久取图历史。新取图结果保存在共享工作空间。DeepSeek余额无需复制第三方Key，使用SakuBot供应商设置。所有私钥、token和个人设备记录均不包含在本源码目录中。

本轮已解析依赖的精确版本见 requirements.lock；在同架构运行镜像中安装 `python -m pip install --target /data/plugin_dependencies -r requirements.lock` 可复用。核心现支持异步感知钩子，天气和ScanElf仅在模型请求或用户主动查询时按缓存规则访问服务，不进行闲置轮询。SSH下载等工作空间产物可用 workspace_publish 交付到主对话。
