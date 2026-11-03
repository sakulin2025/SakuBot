---
name: minecraft_status
description: Minecraft 服务器目录、状态查询与人数/在线变化主动事件。
---

先用 minecraft_servers list 识别名字和别名，再调用 minecraft_status。人数样本可能不完整，不可达不等于确定关服。提醒用 minecraft_alerts，新规则 target 默认 main；需要固定私聊/群聊时填 private:号码/group:号码。所有事件进入唯一主 Agent 队列，不另建聊天上下文。

服务器事件均为泛来源：minecraft_status.observation.*、status_changed.*、server_online.*、server_offline.*、players_changed.*、players_increased.*、players_decreased.*、players_joined.*、players_reached.*、players_below.*（后九项也加 minecraft_status. 前缀）。具体后缀为保存的服务器 ID。可按 server_id 筛选，人数阈值事件按 threshold 筛选，留空服务器表示全部。首次基线不报开关服；关服沿用连续失败确认，不直接断言服务器已关闭。
