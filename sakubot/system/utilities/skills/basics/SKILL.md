---
name: 时间与数值计算
description: 查询准确时间、转换时区、计算时间差或数值表达式时使用。
---
# 时间与数值计算

- time_info 的 value 留空查询现在；支持带偏移的 ISO8601 和 Unix 秒。不要把毫秒当成秒。
- 时区使用 Asia/Shanghai、UTC 等 IANA 名称；没有偏移的输入按指定时区解释。夏令时歧义时间提供明确偏移。
- time_difference 返回 end-start 的实际秒数；days 按24小时计算，不表示日历上的日期数量。
- calculate 接受数值表达式，不接受 Python 代码、赋值或属性访问。乘方用 **，支持 sqrt、round、min/max 等函数。
- 定时唤醒或提醒使用 timers 插件；本插件只提供时间和计算能力。
