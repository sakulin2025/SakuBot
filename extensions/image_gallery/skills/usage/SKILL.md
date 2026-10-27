---
name: image_gallery
description: 图库审核通过的随机图片、图片ID与待审核数量。
---

fetch_anime_image 返回实际图片ID、工作空间相对路径与附件URL，保留ID以供引用。要发图时主 Agent 用 gallery_send(path)，协作 Agent 把路径交给主 Agent。不根据元数据编造图片内容。count_pending_images 只查询待审核数量。
