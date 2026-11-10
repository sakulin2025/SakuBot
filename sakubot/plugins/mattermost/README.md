# Mattermost 主会话

可选内置插件，新部署默认关闭。通过插件管理启用，不自动导入第三方插件目录；配置与数据仍使用 `plugin_data/mattermost` 和插件 KV 命名空间。

启用插件后，在「会话连接 → Mattermost」页面填写服务器地址、机器人访问令牌和生效频道 ID 列表。保存时验证账号及各频道访问。页面提供连接状态、重连和近期日志；日志不记录令牌与消息正文。机器人账号需要加入所选频道，并能读取用户资料和收发消息。

只处理生效频道中的普通消息；频道可以是私聊、群组私聊或公开/私有频道，机器人自己的消息不会再次唤醒。主对话输出跟随当前响应源，并受本轮报告开关控制。支持文本、图片、语音、视频、文件和工具调用开始通知；接收的附件保存到工作空间 `inbox/mattermost`。不实现流式分段输出。历史补收依赖服务器的消息接口，首次绑定只处理绑定后的消息，重连时尝试补收。大文件上限 20 MiB。

WebSocket 和文件服务由 Mattermost 提供，Token 使用 Bearer 认证。连接状态和错误可从插件状态查看。

回应分段配置同时适用于主对话自动投递和 `mattermost_send` 的 message：共用正则分割、移除、裁剪、换行合并和随机间隔；首段立即发送，后续各段随机等待。同一频道的完整消息不会相互穿插，附件只在首段出现，各段保留相同 root_id。工具结果返回首段 id 和全部 post_ids；部分失败不自动重试，需先核实已发送消息。

Agent 工具包含用户、团队、频道和消息查询，发送消息与附件、消息编辑删除、表情、置顶、文件上传下载，以及 `mattermost_request` 官方 JSON API 入口。工具仅在插件可用且对该 Agent 可见时提供，权限取决于 Mattermost 机器人账号。附带 `mattermost` Skill。

「斜杠命令」页集中展示接收设置、请求方向、Mattermost 配置步骤及已声明命令表格。只需填写 Mattermost 能访问的 SakuBot 基础地址，例如容器内的 `http://sakubot:6190/` 或外部访问的 `https://sakubot.example.com/`。插件自动拼接 `hooks/mattermost/slash` 并显示完整请求地址。它指向 SakuBot，连接页的服务器地址则指向 Mattermost。修改后对已有命令点击“同步 / 修复”更新远端地址。旧版完整请求地址会自动转换为基础地址。

页面与 `mattermost_command` 工具支持创建、修改、启停、修复、重置令牌及删除自己管理的指令。先保存脚本，选择团队和命令名称即可自动创建远端命令、私下登记验证令牌并绑定脚本。无需去 Mattermost 手动建命令，令牌由插件管理，不提供手动登记入口。每条命令的请求地址统一取接收设置，无需重复填写。

服务端需要开启自定义 Slash 指令，机器人账号需具备目标团队的 `manage_slash_commands` 权限。内部地址需要在 Mattermost 的 `ServiceSettings.AllowedUntrustedInternalConnections` 中允许对应主机名。停用只阻止本地接收；删除同时移除远端命令及自己的绑定，不删除脚本或执行记录。远端操作超时会保留待修复登记，不盲目重复创建。收到命令只排队执行脚本，不自动唤醒主 Agent；脚本可主动发送结果或按条件唤醒。升级会删除旧的手动令牌配置，只接受本插件创建并管理的命令；已托管命令的令牌保留。

命令保存、修复与令牌轮换会自动回读远端配置并同步验证令牌，通过后才进入 ready。入口认证独立于下游事件动作，不因绑定 wake 或删除旧脚本而失效。403 拒绝原因写入 mattermost.slash.rejected，按原因和指令限频，不记录令牌及消息内容。

## 生效频道
连接页以频道 ID 列表配置接入，机器人须已加入各频道；保存时检查频道访问。每个频道使用独立主对话源，响应跟随当前主会话源；消息实际开始处理或被安全点吸收时才切换。空列表不接收普通消息，Slash 和工具仍可使用。旧主人私聊首次连接时迁移为对应频道，不回放已处理消息。每次唤醒临时提供频道和真实发送者 ID、用户名及昵称。

连接页可开启“回应所有私聊”：仅在收到机器人参与的一对一私聊（D 类型）时动态声明来源，不自动接入群组或公共频道。发现记录按服务器地址和机器人账号隔离保存，重连恢复既有发现；关闭后撤销自动来源，手动填写的频道仍保留。新来源默认不可信，信任由框架管理。


## 话题跟随

收到root_id非空的新消息时，本轮自动回复跟随该话题。吸收时最后一条消息更新位置；普通频道消息将位置转回主消息流。主动切换主会话源清除跟随，新wake不继承旧话题。不增加频道来源数量。mattermost_send支持thread_id选择话题、空字符串回频道，不传则继承本轮匹配频道的话题；root_id保留兼容。此前已入队但未携带root_id的旧唤醒不会补造话题信息。

根消息随话题回复接收时读取，正文和作者时间作为本轮临时引用，不反复写入主对话模型历史；事件元数据保留供追踪。吸收更新跟随时同时更换引用。根消息读取失败不阻断本次唤醒，显示不可读取；附件不自动下载或调用图片模型。


表情反馈泛事件：mattermost.reaction_added.<channel_id>及mattermost.reaction_removed.<channel_id>。在事件与脚本中绑定具体频道或通配模式，可筛选回应者ID、表情名。只接收他人对当前Bot消息的回应，排除自己的回应。监听无需新增主会话源，是否唤醒由事件绑定决定。已有mattermost_post_action的react/unreact/reactions可管理Bot表情，技能提供例子。WebSocket断线期间不保证补收表情事件。

## 当前安装路径

Mattermost 是内置插件，运行程序位于 `/app/sakubot/plugins/mattermost`。旧部署可能遗留 `/data/plugins/mattermost`，内置同名插件存在时该目录不参与加载，不能用其版本判断运行版本。通过 `system_plugins(action="list")` 返回的 `program_path`、`version` 和 `shadowed_paths` 确认当前安装内容；通过 `script_binding(action="sources", source="mattermost")` 或 `source="mattermost.*"` 获取当前实际注册的事件。

## 原生交互与Webhook

mattermost_send新增原生body模式；其他路径使用mattermost_request。mattermost_webhook创建通用HTTP入口，事件为mattermost.webhook.<入口ID>，可绑定脚本、wake或临时监听。回调地址复用斜杠命令页的SakuBot基础地址，无需启用Slash。详细字段、返回、原生按钮示例与身份边界见skills/mattermost/references/webhooks.md。旧专用按钮登记、mattermost_actions和mattermost.action.*.*入口已移除，不自动迁移旧按钮或旧绑定；用新Webhook URL更新消息即可。
