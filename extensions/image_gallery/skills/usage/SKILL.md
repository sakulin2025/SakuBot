---
name: image_gallery
description: 图库图片、合集收藏、管理API、推送图片ID事件与公开原图链接。
---

# 每次操作前查阅

每次编写或修改相关脚本，重新读取本技能及 references/api.md，或通过script_development取得当前文档；不能凭记忆猜路径、请求体、返回字段。图库上游为anime-image-lib。接口参考以当前源码路由为准，旧API.md中的/api/images_page已不是当前分页路径，正确为/api/images/page。

# 常用能力

- fetch_anime_image(orientation="",image_id="")：随机取图或按真实ID取图，返回id/path/url等；大图可回退预览。随机去重不适用于指定ID。
- count_pending_images()：返回{pending:整数}。
- gallery_send(path)：将工作空间图片发往当前主会话，工具返回sent只表示提交，不保证所有源收到。
- gallery_image_link(image_id)：只用外部访问URL生成/api/images/{ID}原图链接。没有外部URL就报未配置。链接公开、无过期，不附带密码、Cookie或内部地址；只推广用户允许公开的图片，不擅自把受限内容分享出去。
- gallery_api(method,path,query,body,form,upload_path,download_path)：管理密码配置后提供。Cookie由插件内部管理，不向模型索取或输出Cookie。API操作失败看ok/status/data；网络异常抛出，写操作结果不确定时查询确认，不盲目重试。

# 收藏即合集

用户说收藏、收藏夹时对应Collection。先列出真实合集，按用户要求选用或创建，不能猜ID。新增成员用POST /api/collections/{id}/images，body={"image_ids":[实际完整图片ID]}。不是{"images":...}；返回added/not_found可能为null，不能假设都是数组。移出收藏不会删除图库原图；删除整个合集与删除图片是不同操作。

更新标题或标签优先PATCH，避免PUT缺字段覆盖旧值。PATCH images数组会替换整个成员列表，绝不是追加。详细类型、顺序和示例见参考。

# 推送事件

image_gallery.push_received含batch_id:string、target:string、image_ids:list[str]、replay:bool、fetched_at:带时区ISO8601字符串。只代表领取并本地登记，不代表发送给用户，不包含图片本体。根据绑定要求选择脚本或唤醒，不默认报告或转发；需要图片时按ID取图。

轮询默认关闭；配置独立target，不能与图库NapCat adaptor共用。无可用动作绑定时不领取。优先重发队列，否则读取updates；updates是GET但有副作用，立即标记推送，不能当只读查询、试验或健康检查。轮询已开启时不要手动使用同一target消费updates或ack。


## 文件大小

取图下载上限与API文件传输上限独立，均可设置1～500MiB。普通取图超限尝试预览；API文件超限抛异常，不静默用预览替换原文件。大文件通过文件流处理，返回工作空间路径与附件URL。配置容量不代表QQ/Mattermost或其他消息源一定接受该大小，其自身限制不变。

## 提前获取推送

调用 `gallery_push_now()` 可请求提前一次已有推送检查：下次检查还需超过10秒则提前执行；10秒内保持原计划；正在执行或已请求提前时不重复领取。工具仅返回调度状态，图片ID通过 `image_gallery.push_received` 事件交给绑定动作，不直接返回图片。默认遵守免打扰；传入 `gallery_push_now(ignore_quiet=true)` 可仅让本次请求对应的下一次检查跳过免打扰，不修改长期配置。下次在10秒内时保持时间不变，但仍应用这一次免打扰豁免；重复请求不重复领取。关闭轮询、缺少配置或无启用事件绑定时不绕过限制。执行完成后按配置范围内的自适应随机间隔重新安排，不再额外保留旧定时点。

## 自适应随机间隔

下一次间隔根据最近一次成功领取的实际数量与本次尝试数量决定，始终位于配置的最短、最长分钟数之间。取满时用Beta(1,3)偏向短间隔，未取满（包括0张）时用Beta(3,1)偏向长间隔；期望位置分别是区间的25%和75%，并非固定等待时间，也不不断累积退避。上下限相同时为固定间隔。

实际数量按有效图片ID去重计数，尝试数量是这次随机选择并传给上游的count，而不是配置的最多张数。重发队列和普通推送都按实际领取结果判断。反馈持久保存，重启后保留；没有反馈或切换了图库地址/推送目标时先均匀随机。请求异常、免打扰跳过、未领取或仅重投递旧批次不会覆盖上次领取反馈。保留重载前已排定的next_at，不因热重载立即取图。
