# 事件与脚本自动化

入口：系统功能 → 事件与脚本。系统运行器随框架启动，无需插件开关，不依赖主 Agent 是否启用。

## 程序、绑定与执行

程序保存 Python 代码、参数 JSON Schema、版本、超时和忙碌策略。保存只解析语法，不执行代码。当前版本、历史版本和 manifest 位于 `data/scripts/<id>/`；私有 JSON 状态位于 `data/script_data/<id>/state.json`，数据库保留注册表、触发绑定与执行记录。

每次执行固定代码与配置版本。一个脚本串行，不同脚本最多并行 8 个。`merge` 保留一个待执行任务，并用最新事件替换其参数；`queue` 逐条处理，最多排队 100 个；`skip` 忽略忙碌时的新事件。需要逐条处理数据时选 queue。主动调用始终排队，不使用丢弃/合并策略。

进程重启后，排队任务可继续开始；已执行任务标记中断，不重放。脚本删除要求先解除绑定并停止任务；删除注册保留源码版本、私有状态和历史记录，避免误删产物。

## SDK

```python
from script_types import ScriptContext

async def main(ctx: ScriptContext) -> object:
    result = await ctx.tools.utilities.calculate(expression="1+1")
    ctx.log("完成", result=result)
    old = ctx.state.get("last")
    ctx.state.set("last", result)
    if old is not None and old != result:
        await ctx.wake("结果发生变化，请根据需要处理", data=result,
                       send_result_to_source=True)
    return result
```

- `ctx.params`：通过脚本 Schema 校验的参数。
- `ctx.event`：事件 ID、来源、时间与 `data`。
- `ctx.call(plugin, tool, arguments)`：通过框架参数校验、可用性检查和工具调用追踪。
- `ctx.state.get/set/delete`：跨执行 JSON 状态，上限 256 KiB。
- `ctx.log(message, **data)`、print：执行日志，上限保留末尾 256 KiB。
- `ctx.workspace`、`ctx.data_dir`：共享工作空间、该脚本的私有目录。
- `await ctx.wake(content, data=..., send_result_to_source=True)`：向唯一主 Agent 发 wake，数据临时注入。
- `await ctx.notify(content, send_result_to_source=True, include_context=False)`：固定通知。

工具返回显式 `error` 或 `success=false` 时视为失败。历史插件可能将失败作为普通字符串返回；这类业务结果需要脚本按具体工具约定处理，框架不猜测自然语言的含义。脚本失败策略支持连续失败阈值、冷却时间、wake/notify/仅记录；绑定的策略覆盖脚本默认策略。

独立进程是故障隔离，不是安全沙箱。脚本属于可信本地代码，具有容器当前用户能访问的文件与网络能力。取消/超时结束进程组；已经发往外部服务的动作不能撤销，不能承诺恰好执行一次。Windows 原生环境目前仅终止工作进程，进程树清理仍需额外适配。

## 插件触发源 API

```python
from sakubot.trigger_schema import field, event_schema

self.trigger_source(
    "sample_changed.*", "样本变化",
    parameters={"type": "object", "properties": {
        "device_id": field("string", "设备 ID；留空匹配全部设备", title="设备")
    }},
    event_schema=event_schema(
        "设备温度样本发生变化后触发，首次观测只建立基线。",
        {"device_id": field("string", "发生变化的设备唯一 ID"),
         "value": field("number", "本次温度，单位：摄氏度", **{"x-unit": "celsius"}),
         "observed_at": field("number", "观测时间，Unix 秒，UTC 基准", **{"x-unit": "seconds"})},
        {"device_id": "sensor-1", "value": 24.5, "observed_at": 1793926800},
        required=("device_id", "value", "observed_at"),
    ),
    id_description="sample_changed.<device_id>；星号为设备唯一 ID，例如 sample_changed.sensor-1。",
    options=self.device_options,
    match=lambda event, params: not params.get("device_id") or event["device_id"] == params["device_id"],
)
await self.emit_trigger("sample_changed.sensor-1", {
    "device_id": "sensor-1", "value": 24.5, "observed_at": 1793926800,
}, uid="sample:123")
```

`options()` 返回字段名到 `{value,label}` 数组的映射。`validate(params)` 做本地校验，不执行脚本。对于需要按需连接的来源，提供 `subscribe(params, emit)`，返回可调用的清理函数（可异步）；相同来源与参数共享一份订阅。订阅通过 emit 发布到对应参数组，不必自行再次广播。

插件停用、删除或重载前框架撤销声明与订阅；绑定保留，显示不可用。插件恢复且参数匹配时自动订阅。插件已有轮询或本地写入回调时直接 emit，无需新开轮询。`publish_trigger` 是同步发布入口，会将分发任务交回框架事件循环；需要等待事件已进入运行队列时使用 await emit_trigger。原始平台消息与业务存储仍属于插件，不进入核心。

事件 UID 在绑定内去重；合并策略会舍弃旧的待处理输入。由脚本工具调用产生的本地事件携带因果链，最多 8 层且不允许立即递归回同一脚本。HA 等远端异步事件无法可靠保留调用因果关系，因此应使用条件、幂等操作和冷却防止外部反馈循环。

## 已接入来源

| 来源 | 参数 | 依赖 |
|---|---|---|
| timers.schedule.* | interval/daily/once、时间与时区 | 定时任务插件启用 |
| ha_control.entity_state_changed.* | entity_id、可选目标状态 | 已配置 HA，房间与实体允许读取 |
| minecraft_status.observation.* | server_id、观测/状态/人数 | 原插件轮询开启 |
| freereps_activity.workout_added.* | 训练名称关键词 | 原插件轮询开启，首次只建立基线；仅新增去重后的训练记录触发 |
| calorie_calendar.record_changed.* | 可选日期 | 记录实际增删改后触发 |
| calorie_calendar.confirmation_changed.* | 可选日期 | 确认状态实际改变 |
| scanelf.device_state_changed.* | 可选 MAC、上线/下线 | 存在绑定才共享订阅 /api/v1/ws，过期快照不判定变化 |

Agent 工具：script_manage、script_run、script_execution、script_binding、script_tools。附带 script-automation 技能。查看工具和源定义无需执行代码；所有普通执行结果留在脚本记录，不自动污染主上下文。

定时任务管理页也可选择“执行脚本”，保存 script_id 和 script_params；按原有 at/interval/daily 触发，执行与异常策略使用脚本配置。此类任务通过插件的 script_references 回调阻止误删仍被使用的程序。

## 软声明与泛触发

声明用于 Schema、动态选项和按需订阅，不是事件白名单。绑定可保存尚未安装插件、尚未声明或暂时不存在的来源，参数先按 JSON 对象保存；来源出现后自动使用其 Schema 校验与订阅，不匹配时显示待配置。来源名称允许 `*`，例如 `mattermost.slash.*` 接收所有 Slash 指令，`mattermost.slash.weather` 仅接收 /weather。脚本的 ctx.event["source"] 始终保留实际事件名。

泛触发声明可使用 `trigger_source('slash.*', ...)`，实际发布时使用 `emit_trigger('slash.weather', payload)`。未声明的名称也能发布，框架按软绑定匹配。通配绑定本身不会凭空建立远端订阅；没有插件生产事件时永远不会触发，这是允许的。

Mattermost 的「斜杠命令」标签集中提供接收设置、请求方向、服务端配置步骤和已声明命令表格。只需手填 Mattermost 能访问的 SakuBot 基础地址，例如同一 Docker 网络中的 `http://sakubot:6190/` 或外部访问的 `https://sakubot.example.com/`；插件自动拼接 `hooks/mattermost/slash` 并展示完整请求地址。旧版配置的完整请求地址自动迁移为基础地址。默认关闭；创建托管命令会自动开启。入口仅接受插件管理的命令令牌，不使用也不暴露管理令牌；令牌不会存入脚本事件。收到命令只排队匹配脚本并立即返回临时确认，不自动唤醒 Agent。事件包含 command/text/user_id/channel_id/team_id 等字段，脚本可以通过 Mattermost 工具返回结果；需要按用户/频道限制时在绑定参数中配置或在脚本中判断。

### Mattermost 指令自管理

`Mattermost → 斜杠命令` 与 `mattermost_command` 共用管理服务。先保存脚本，再指定 team_id、trigger、script_id 创建命令；插件自动登记返回的令牌、开启接收、建立带 team_id 筛选的专属绑定。每条命令统一使用该页的请求地址，不提供单独地址参数。修改地址后用“同步 / 修复”更新已有命令，操作前显示“请求地址待同步”。请求地址不是 Mattermost 自身的 base_url。

工具提供 list/get/save/enable/disable/repair/rotate_token/delete；修改使用本地 id，远端 command_id 单独展示。停用只阻止本地接收并撤下自己的绑定；删除同时删除远端资源和自己创建的绑定，需要 confirm=true，管理页有二次确认。不会删除程序、其他绑定与历史执行记录。有指令引用的脚本不能直接删除，应先删除指令。

私有令牌和资源操作登记保存在插件命名空间 KV（`mattermost:slash_commands`），归属于当前服务器和账号。界面、工具结果、触发事件与日志均不返回命令令牌；已移除手动令牌登记与接收逻辑，升级删除旧 slash_tokens 配置，托管令牌保留。托管令牌同时验证团队、指令名称及可选用户、频道；插件停用时所有入口撤销。更换机器人访问令牌后需修复登记；只有同一服务器、同一远端创建者可恢复。

远端写操作前先保存待确认记录并暂停自己的绑定。超时/中断保留记录，不盲目重复 POST 创建或重置令牌；repair 查询远端恢复状态。没有唯一匹配时不擅自接管其他指令，需人工确认后删除登记再新建。未完成的删除可通过 repair 继续查询与完成。修复完成前指令不会触发脚本。停用、修改或删除不会撤销已经开始的脚本或外部操作。

服务端必须开启自定义 Slash 指令，当前 Mattermost 账户需具备团队的 `manage_slash_commands`。权限不足会返回明确错误，不要求给 SakuBot 额外填写管理员令牌。保存指令、登记令牌与修复不会执行脚本。接口依据：[Mattermost Commands API](https://docs.mattermost.com/api/reference/commands)。

公共插件 Webhook 接口为 `self.webhook(path, handler, methods=('POST',))`，路径位于 `/hooks/<plugin>/<path>`。此入口独立于管理 API，插件 handler 必须校验自己的服务凭据；停用插件后入口失效。

脚本运行器不自动请求模型，但脚本主动调用的插件工具可能包含图片理解、团队委派等模型操作，这些调用仍按工具本身消耗额度。

## 直接唤醒主智能体

触发绑定支持 `target_kind=script`（默认，兼容旧绑定）或 `target_kind=wake`。选择唤醒时填写 `prompt`，无需创建脚本；`send_result_to_source` 控制是否向主对话源投递结果，网页仍同步。

触发后进入持久队列，通过事件 UID 去重，执行记录保存提交结果和 wake 事件 ID。“完成”表示已提交唤醒，智能体执行结果在唤醒详情中查看。提示词作为当前任务；触发源、时间和观测数据仅注入本轮临时上下文。提示词为普通文本，不执行模板或代码。

AI 可通过 `script_binding` 保存：

```json
{"action":"save","target_kind":"wake","name":"余额预警","source":"deepseek_balance.balance_low.*","source_params":{},"prompt":"DeepSeek 余额已跌至预警值，请检查本轮观测数据并提醒主人。","send_result_to_source":true}
```

软声明、通配符、参数校验及订阅清理对两种目标一致。保存不触发执行。

## 事件目录与唯一绑定

触发绑定页展示插件声明的事件，通配事件展开为树，已绑定动作排在前面。绑定到暂未声明事件的记录仍保留并显示。具名来源 ID（不含 `*`）最多保存一个动作，包括停用中的绑定；修改须编辑原绑定，切换动作须修改或删除后重建。通配来源允许多个绑定；通配绑定与具体事件绑定独立匹配。旧的重复具名绑定不会删除，除第一个外标记为冲突并禁止执行，可手动清理。

### Mattermost 动作归属

Slash 指令登记负责远端资源、令牌和接收状态；事件动作以框架绑定为准。创建时 script_id 可选，不传可再绑定 wake；不再要求为直接唤醒创建脚本。改为 wake 后，登记中的历史脚本字段不构成引用，允许删除旧脚本。启停只控制入口，保留动作；修复不覆盖框架已更新的动作。页面动作列展示实际绑定。

## 对象泛事件

| 插件 | 泛事件族 | 具体事件后缀 |
|---|---|---|
| Home Assistant | entity_state_changed、entity_turned_on、entity_turned_off、entity_unavailable、entity_available、entity_attribute_changed | HA 实体 ID，如 switch.lamp |
| ScanElf | device_state_changed、device_online、device_offline、device_discovered | 标准大写 MAC，保留冒号 |
| 我的世界 | observation、status_changed、server_online、server_offline、players_changed、players_increased、players_decreased、players_joined、players_reached、players_below | 保存的服务器 ID |
| DeepSeek | balance_low | 供应商 ID.币种，例如 provider.CNY |
| FreeReps | workout_added | 训练记录 ID |
| 热量日历 | record_changed、confirmation_changed | 日期 YYYY-MM-DD |
| 定时任务 | schedule | interval、daily、once |

以上事件族均加 `. *`（去掉中间空格）注册，例如 `ha_control.entity_state_changed.*`；可绑定全体、多组筛选或具体来源 `ha_control.entity_state_changed.switch.lamp`。具名来源仍一个动作，泛来源可以保存多个动作。通配符按大小写匹配；MAC 使用 ScanElf 返回的标准大写格式。HA 仍只观察已配置的房间与实体，实体筛选留空表示全部允许实体。人数阈值事件在参数 threshold 中设置，只有跨过阈值才命中；开关服沿用连续失败确认，首次基线不触发变化提醒。

`Plugin.trigger_source(..., legacy_ids=('old_event',))` 可将该插件旧事件绑定迁至新声明，保留绑定 ID、动作、开关与参数；迁移不执行动作。参数不兼容时原绑定保留并记日志。通用订阅可共享物理连接，按实际对象发布 `emit_trigger('family.' + object_id, data, uid=...)`；不要直接发布带星号的事件名称。


## 事件变量文档规范

`trigger_source()` 在注册阶段执行文档校验，声明与运行时业务数据校验分别进行。缺少以下内容会拒绝注册并给出字段路径：

- `parameters.properties` 与 `event_schema.properties` 的每个变量必须包含类型和非空 `description`；递归覆盖嵌套属性、数组元素、动态键 Schema、组合类型的分支。
- `event_schema.description` 说明何时触发、首次观测、去重和状态判断等业务语义。
- `id_description` 为必填，说明实际事件 ID；泛事件还必须说明星号对应的动态标识并给例子。
- `event_schema.examples` 至少有一个完整 payload 对象，涵盖根级全部已声明字段（包括可选字段），且须通过该事件 Schema 校验。示例不是实际事件，也不会触发动作。
- 枚举以 `x-enum-descriptions` 字典逐项说明取值，键使用对应值的字符串形式；数值须在说明中注明单位，推荐另加 `x-unit`。时间注明 ISO 8601/Unix 秒/毫秒、时区或时钟基准。可空字段解释 null 含义，筛选参数解释留空和默认值。
- 平台动态对象在说明中注明来源、已知关键字段及未知键的语义，不能靠伪造固定字段列表表达未知协议数据。当前不支持 `$ref`，请内联可读字段定义。

`field(type, description, **constraints)` 与 `event_schema(description, properties, example, required=())` 为公共辅助函数，也可直接填写等价 JSON Schema。框架验证说明存在与结构有效性；说明是否准确仍由插件作者负责。

脚本业务变量位于 `ctx.event["data"]`；`ctx.event["id"]` 是生产者去重标识，`ctx.event["source"]` 是实际完整事件名（无星号），`ctx.event["at"]` 是框架分发时的 Unix 秒（UTC 基准）。页面“事件变量”会同时显示这些封装字段；“事件示例”展示的是 data 的 payload。Agent 通过 `script_binding(action="sources")` 按需获取相同的字段文档，不自动注入所有事件定义。

本规范是已声明事件的开发约束，不改变软声明机制：尚不存在的来源仍允许保存绑定；未声明来源没有可推断的字段文档。旧插件升级时需补齐说明、示例和 id_description，无需重建已有绑定或执行历史。插件可将定义保存在自己的 `event_docs.py`，导出时随程序一起打包。


## Python 类型契约与静态保存检查

插件可用 `typing.TypedDict` 声明参数、事件数据与结果结构，用 `Annotated[T, "字段说明"]` 或 `Annotated[T, {"description": "说明", ...JSONSchema约束}]` 提供说明和单位。`NotRequired` 表示键可缺失，`T | None` 表示值可为 null，两者不同。事件封装 `Event[T]` 是泛型 TypedDict，运行时仍是 dict。

`Plugin.trigger_source(..., parameters_type=Params, event_type=Payload, description="何时触发", examples=[完整样本], id_description="泛ID规则")` 从类型生成并校验 Schema。`Plugin.typed_tool(name, description, Arguments, Result, handler)` 同时声明参数与结果，并在调用入口和返回时验证。函数式注册支持 TypedDict/Annotated 注解；原始 `tool()` 也可提供 result_type。旧 Schema 插件保留兼容路径，未声明结果类型不伪造字段。

现有触发源已迁移到各插件的 `event_types.py`，由该 Python 类型生成 `event_docs.py` 中的 Schema，避免维护两份独立定义。

Agent 调用 `script_development` 获得专属 SDK、字典/实例约定和示例。SDK 包含 ScriptContext、EventData、ScriptParams、ctx.tools 的带参数和返回类型方法。tool_plugins 可缩小范围；SDK 按 offset/limit 分页，后续页须携带 sdk_hash。检查器根据同一份注册数据生成类型，不导入或执行脚本。

`script_manage(action="check")` 只返回诊断；`save` 每次检查 Python 语法与 Pyright 类型。错误或警告默认返回 saved=false，不产生新版本。`hard=true` 加非空 hard_reason 仅可绕过类型诊断；语法错误、入口结构错误和检查器故障不可绕过。成功版本保存 validation 诊断与强制原因、sdk_hash 和版本专属 `.types.py`。修改启停等元数据也会进入保存检查。旧版本照常运行，不在升级时批量重写或触发执行。

运行前校验 event 的字典封装，以及保存时的事件来源与数据 Schema。手动执行已声明事件类型的脚本需通过 script_run 的 event 参数提供完整样本；页面提供事件样本输入框。

静态检查无法证明网络请求必然成功、业务计算合理或工具无副作用；动态工具调用、未知来源/返回类型和显式 Any 都不能当作静态安全保证。Pyright 不可用时普通和强制保存均被阻止。
