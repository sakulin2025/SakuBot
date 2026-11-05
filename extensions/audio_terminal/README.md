# 音频终端插件

提供设备查询、控制、WAV 播放及事件，不包含语音识别、语音合成或自动唤醒 Agent。

连接设置使用框架插件设置表单：base_url 默认 http://esp32-audio-terminal:8765，token 填桥接服务 API_TOKEN。subscribe_events 控制事件订阅。密钥保存在 plugin_data/audio_terminal/config.json。

工具：audio_terminal_devices、audio_terminal_status、audio_terminal_control、audio_terminal_play、audio_terminal_stop、audio_terminal_events。

脚本触发源：audio_terminal.wake.*、button.*、playback.*、connection.*，可按 device_id 过滤。事件含 id、device_id、event、received_at、timestamp_ms、data。设备 VAD、训练候选只进入事件列表。最近400条事件保存在内存，最近200条定期保存到插件 KV，重启恢复；断线事件不补传。

管理页位于“网络与设备 / 音频终端”，显示设备状态、控制和事件。只读设备发现每5秒刷新，状态约10秒更新；页面每2.5秒读取缓存。控制及播放不自动重试。WAV 要求 16kHz、单声道、PCM16，最长120秒。

从 sakubot 根目录构建页面：node frontend/build-plugins.mjs extensions。将完整目录发布到运行数据目录 plugins/audio_terminal，通过插件管理启用或重载。外部依赖复用 httpx、websockets。
