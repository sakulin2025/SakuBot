# 音频模型与音箱主会话

## 模型能力

模型管理页将 ASR（语音识别）、TTS（语音合成）、持续流式输入、流式输出、实时双向能力分别列为标签。普通“音频”标签不能替代 ASR/TTS 标签，也不会自动选择语音模型。

官方 MiMo 预设：

| 模型 | ASR | TTS | 流式输出 | 持续输入 | 实时双向 |
|---|---|---|---|---|---|
| mimo-v2.5-asr | 是 | 否 | SSE 文字 | 否 | 否 |
| mimo-v2.5-tts | 否 | 是 | SSE PCM16 | 否 | 否 |

选择语音接口 `MiMo`，官方 API 根地址为 `https://api.xiaomimimo.com/v1`。密钥填写供应商设置；不要放入代码、日志或部署文档。标准 MiMo TTS 是 24kHz 单声道 PCM16，插件以有状态低通重采样转为设备的 16kHz。voice-design/voice-clone 不承诺低延迟流式播放。普通 OpenAI 兼容接口提供整段 WAV 转写和 PCM 合成；选择相应接口与正确 PCM 采样率。标签是能力声明，不会凭空提供协议适配；当前插件不接受未实现的实时输入模型。

MiMo ASR 接收完整音频后才开始推理，SSE 只表示识别文字分批返回。桥接提前转交 PCM 可以减少收尾传输等待，并为后续实时 ASR 适配保留输入通道，**不代表 MiMo 可以边录边识别**。

## 插件设置

更新核心程序和已安装的 `audio_terminal` 插件程序到 0.4.0 后，在插件设置中：

1. 保持原服务地址、API_TOKEN、临时上下文和事件订阅。
2. 语音处理方式选择「Sakubot 模型 ASR/TTS」。
3. 分别选择已有 ASR、TTS 模型。下拉列表根据模型能力动态更新，无需重启插件。保存前检查模型及供应商可用。
4. 开启「新语音自动打断」。音色留空时标准 MiMo 使用 `mimo_default`；需要更改时填写供应商支持的音色名。风格要求单独填写。
5. 思考与工具提示默认关闭；开启后只在语音播报开始前提示，避免替换正在播放的回答。

原有「音频服务 ASR/TTS」兼容方式继续可用。核心镜像更新不会自动覆盖 `/data/plugins/audio_terminal`；插件程序需单独更新，配置保存在 `/data/plugin_data/audio_terminal/config.json`，不要覆盖或迁移其他用户数据。`audio_terminal_voices` 查询当前方式、选定模型和默认音色；模型模式返回当前已配置音色，不冒充供应商完整音色目录。

## 对话与打断

- 插件以原始音频提供者声明：`input=audio, requires_asr=false, input_stream=true, device_mode=single`；`barge_in` 对应自动打断开关。
- 桥接保持一对一能力提供者绑定；单设备锁贯穿打断，其他设备不能抢占。双敲仍按桥接路由发事件，不转成 ASR 主会话。
- 每段录音进入一次 ASR，识别结果通过原有主会话源交给 Agent，临时上下文仍随轮次注入。
- Agent 文字按句号、问号、感叹号等边界送 TTS；没有边界时最多约 180 字切分。每句 TTS PCM 增量发送，同轮使用一个连续播放流，设备播放完成后才恢复普通聆听。
- 新语音自动打断使用设备 AEC 后 VAD 与持续约 360ms 的能量门限，过滤短敲击及播报启动瞬态。取消当前识别、生成和待播内容，保留会话并保存触发打断的首段语音；迟到的旧轮次结果丢弃。实际扬声器回声与声学阈值仍需现场确认。
- 音频终端管理页和桥接控制台均有「打断并继续听」。打断保留会话；「结束会话」退出并释放锁。
- Agent 结束工具仍是 `audio_terminal_end_conversation()`，无参数、幂等。ASR、TTS、Agent 响应失败或超时立即结束会话；普通工具调用参数错误不会直接结束会话。停止不清除主会话历史。
- 每段收音最多约15秒，单轮播放最多120秒，Agent 轮次总期限180秒，网络/队列有界且不自动重播音频。安静自动结束和会话最长时间由桥接现有配置决定，最长时间0表示不限总会话时长。

## 230 开发、部署与回滚

Sakubot 使用本机隔离工作树开发提交并推送，再在230拉取并构建；不在Mac下载镜像或安装构建依赖，也不修改原脏工作树和本机正在运行的容器。230桥接源码单独在服务器开发。GitHub从230不可达时，使用**已推送提交的增量 Git bundle**，230执行 `git fetch` 并检出同一提交；不要用 rsync 覆盖源码。

- Sakubot运行目录：`/repo/docker-compose/sakubot`，容器 `sakubot`，控制台6190。
- 桥接运行目录：`/repo/docker-compose/esp32_playground`，容器 `esp32-audio-terminal`，宿主18765、容器8765。
- 沿用默认 bridge 与 `172.17.0.1`，不创建自定义 Docker 网络。保持现有 bind volumes。
- 更新环境变量：在对应运行目录编辑 `.env`，执行 `docker compose up -d --force-recreate --no-build --pull never <服务名>`；单纯 `restart` 不重新读取环境变量。
- 镜像替换前保留旧镜像标签，并备份配置、插件程序及 SQLite 在线备份。升级只替换程序，不覆盖配置/历史。
- 回滚：将保留镜像重新标记为 `sakubot:local` 或 `esp32-audio-terminal:local`，恢复备份插件程序，再 `docker compose up -d --no-build --pull never <服务名>`。先结束活动会话，配置切回兼容语音方式即可停用模型音频协议。不要删除卷或回滚整库丢失新对话。

## 验证

在230的已有镜像中挂载候选源码，设置 `PYTHONDONTWRITEBYTECODE=1`，禁止网络即可运行离线检查：

- `scripts/check-speech.py`：MiMo ASR/TTS 请求、SSE分割、取消、错误脱敏、采样与抗混叠。
- `scripts/check-audio-conversation.py`：需挂载桥接源码到Python路径、插件到 `/plugin`；覆盖旧文本模式、新PCM模式、首句提前播放、去重、识别/合成异常、打断、参数为空的结束工具和动态模型列表。
- 桥接 `python -m unittest tests.test_interactions tests.test_live_audio`：独占绑定、输入输出流、实际播放完成回执、短噪声抑制、打断保留锁、迟到输出拒绝、连续Opus编码和停顿发送节奏。

真实 MiMo API 合成与转写可在隔离设备模拟器中验证；不能据此宣称现场噪声、AEC或自动打断已通过人的听感验收。

官方接口资料：[ASR](https://mimo.mi.com/docs/zh-CN/api/audio/Speech-Recognition-post)、[TTS](https://mimo.mi.com/docs/zh-CN/api/audio/tts-post)。
