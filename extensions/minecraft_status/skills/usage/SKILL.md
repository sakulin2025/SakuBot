---
name: minecraft_status
description: Minecraft 服务器目录、状态查询与人数/在线变化主动事件。
---

先用 minecraft_servers list 识别名字和别名，再调用 minecraft_status。人数样本可能不完整，不可达不等于确定关服。提醒用 minecraft_alerts，新规则 target 默认 main；需要固定私聊/群聊时填 private:号码/group:号码。所有事件进入唯一主 Agent 队列，不另建聊天上下文。
