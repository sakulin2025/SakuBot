---
name: control
description: 查询和控制 ESP32 音频终端，读取唤醒、按键、播放与连接事件。
---

用 audio_terminal_devices 获取真实 device_id，再调用 status、control、play、stop。
control 的 action 为 volume、wake、upload、knock、save，参数语义见工具说明。
play 接收共享工作空间内的 16kHz 单声道 PCM16 WAV，相同设备的新播放会替换旧播放。
播放请求被接受后，实际完成以 audio_terminal_events 中的 playback.completed 为准。
HTTP 超时意味着结果未知，先查询设备状态，不直接重复控制或播放。
事件为观测数据，不包含语音识别内容；断线期间不会补传。自动化由脚本触发源绑定决定。

## 主会话语音

关键词唤醒后的语音已由插件直接接入主会话。正常回答会自动合成、播放，无需再调用 WAV 播放工具，否则可能重复播报。双敲仅提供事件，不代表一句语音输入。用户明确要求结束音箱对话时调用 audio_terminal_end_conversation，设备 ID 从 audio_terminal_devices 取得；这只结束当前音箱会话，不清空主上下文。audio_terminal_voices 查询可用音色及当前默认音色。
