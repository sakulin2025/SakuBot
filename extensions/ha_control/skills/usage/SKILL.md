---
name: ha_control
description: HA 初始化、设备查询控制与操作手册。
---

连接配置填写后，使用 ha_initialize status/scan 查看草稿，再 rooms/room 选择房间，entities/policy 选择设备策略，review_room(confirmed=true) 确认房间，最后 build(confirmed=true) 发布。询问用户实际偏好，不自行开放房间。日常控制先参考手册和设备名称，switch 也可能是照明；实时状态必须查询。

HA 事件均为泛事件：ha_control.entity_state_changed.*、entity_turned_on.*、entity_turned_off.*、entity_unavailable.*、entity_available.*、entity_attribute_changed.*（后五项也加 ha_control. 前缀）。可用具体实体后缀，如 ha_control.entity_state_changed.switch.lamp，或用泛来源加 entity_id/domain/from_state/to_state 筛选。实体留空表示所有允许实体；同一泛事件可创建多个不同筛选的绑定。
