---
name: scanelf
description: 局域网设备识别、MAC 别名描述及完整上下线时间线。
---

scanelf_devices 返回已合并别名和记忆的设备。设备在线不代表人员在场。时间线使用 scanelf_device_timeline，has_more=true 时继续以 next_cursor 作为 before，不把一页说成全部历史。缺少IP不要猜测。
