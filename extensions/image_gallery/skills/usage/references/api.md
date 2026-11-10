# Anime Image Library API

本地参考源：anime-image-lib/ImageStore/main.go、images/handlers.go、collections/handlers.go、collections/service.go、plugins/manager.go。所有path相对于图库服务URL，动态ID必须逐段URL编码；query独立传递，不拼进path。示例中的ID必须替换为实际值，示例不会执行。

## gallery_api 请求与响应

参数：method:string（默认GET）、path:string（默认/api/stats）、query:dict|null、body:dict|list|null、form:dict|null、upload_path:string、download_path:string。body不能与form/上传同时提供。query数组变为逗号连接；form数组作为重复的表单字段。

统一响应：ok:boolean（2xx）、status:integer、content_type:string、data:JSON|null。非2xx保留响应，不冒充成功。有X-Image-ID时额外返回image_id:string。二进制成功响应保存为file:{path:string,url:string,name:string,mime:string,expires:number}，path是工作空间相对路径，url是框架附件地址，不是图库公开永久地址。download_path是可选目标，不覆盖已有文件。默认二进制路径artifacts/gallery。上传与二进制下载受“API 文件传输上限 · MiB”共同控制，允许1～500，新安装默认100。普通取图使用独立“取图下载上限 · MiB”，允许1～500，旧配置迁移保留。下载采用64KiB分块写入临时文件，超限、失败或取消清理未完成文件，完成后才发布附件。上传使用文件流，不整文件读入内存。普通JSON响应仍限512KiB，超出需分页；文本最多返回30000字符。显式download_path会将成功响应（包括JSON/text）作为文件流保存，而不是返回完整data。

配置密码后自动登录，401时最多重新登录一次；网络失败不自动重发写请求。登录、退出由插件管理，通常不用手动操作/api/auth/*。

## 图片

| 方法/路径 | 参数、请求形式 | 返回 |
|---|---|---|
| GET /api/images | query.source:string、review_status:string，均可省略 | 图片列表；大范围优先page |
| GET /api/images/page | query.cursor:string、page_size:integer（默认20）、source/review_status/aspect_ratio:string | {images:list[图片元数据],next_cursor:string,has_more:boolean}；page_size最大100，has_more=true时使用next_cursor；不是旧/images_page |
| GET /api/images/random | query.source、aspect_ratio=horizontal/vertical、include_restricted:boolean、include_old:boolean | 图片二进制；原始响应X-Image-ID为真实ID，通常直接用fetch_anime_image |
| GET /api/images/{id} | 完整ID | 原图二进制 |
| GET /api/images/{id}/preview | 完整ID | 预览JPEG |
| GET /api/images/{id}/meta | 完整ID | 图片元数据对象 |
| POST /api/images | upload_path指定文件；form:{source:string,image_id:string,review_status?:string,added_at?:RFC3339,metadata_json?:JSON字符串,mime_type?:string} | 创建结果含实际ID；不要自行拼接推测完整ID |
| POST /api/images/{id}/review | form:{review_status:"pending"或"approved"或"rejected"或"restricted"} | {id:string,review_status:string,review_at:string|null}；不是JSON body |
| POST /api/images/batch_status | form:{image_ids:[完整ID,...]}，重复表单键 | ID→{exists:boolean,review_status:string|null}映射 |
| POST /api/images/batch_reject_pending | body:{image_ids:[完整ID,...]} | 批量拒绝待审结果；不当作物理删除 |
| DELETE /api/images/{id} | 完整ID | 删除原图及相关记录；必须用户要求 |

元数据包含id/source/review_status/metadata/added_at/review_at等；metadata内部由来源决定，不猜固定食物、画师等字段。

## 合集与收藏：固定结构

Collection={id:string,label:string,tags:list[string],images:list[string]}。images是按sort_order排列的完整图片ID，不是图片对象列表。新建必须提供id，不会自动生成。标签筛选query.tags使用逗号分隔，列表query.image筛选某张图所在合集；不同时依赖二者。

| 方法/路径 | 请求 | 响应和语义 |
|---|---|---|
| GET /api/collections | 可选query.tags或query.image | list[Collection]；空为[] |
| POST /api/collections | body:{id:string,label?:string,tags?:list[string]} | 201 Collection；冲突409；不直接用images字符串数组初始化 |
| GET /api/collections/{id} | 无 | Collection；不存在404 |
| PATCH /api/collections/{id} | body可含label:string、tags:list[string]、images:list[string] | Collection；只改提供字段，images出现即替换全部成员和顺序，空数组清空 |
| PUT /api/collections/{id} | body:{label:string,tags:list[string]} | Collection；label/tags未提供会被清空，不适合单字段更新 |
| DELETE /api/collections/{id} | 无 | {message:"deleted"}；删合集而非原图 |
| GET /api/collections/{id}/images | 无 | list[图片元数据]，按合集顺序，无分页；空为[] |
| POST /api/collections/{id}/images | body:{image_ids:list[string]}，非空 | {added:list[string]|null,not_found:list[string]|null}，可能部分成功；已存在成员不会重复插入；added不等于本次全是新成员 |
| DELETE /api/collections/{id}/images/{imageId} | 无 | {message:"removed"}；只移出合集 |
| GET /api/collections/{id}/images/random | 可选query.this:string排除当前图 | 随机图片二进制；仅一张时可能仍返回同一张 |
| GET /api/collections/{id}/images/next | 可选query.this:string当前ID | 下一张图片二进制；循环遍历 |
| GET /api/collections/{id}/images/{imageId} | 无 | 检查合集成员关系后返回原图；非成员404 |

PUT的底层Images结构是关系对象列表，不是PATCH的字符串数组；为减少歧义，成员替换仅使用PATCH，追加仅使用POST images。

### 收藏流程示例

```python
# 先查当前合集及真实图片ID，再选择用户指定的合集。
result = await tools["gallery_api"](method="GET", path="/api/collections")
if not result["ok"]:
    raise RuntimeError(str(result["data"]))
collections = result["data"]  # list，不是{"items":...}

# 仅在用户要创建且确认不存在时创建。
await tools["gallery_api"](method="POST", path="/api/collections",
    body={"id":"my-favorites", "label":"我的收藏", "tags":["收藏"]})

# 添加实际图片ID；检查not_found，不能将HTTP200视为全部添加。
result = await tools["gallery_api"](method="POST", path="/api/collections/my-favorites/images",
    body={"image_ids":["实际完整图片ID"]})
missing = result["data"].get("not_found") or []

# 仅改名称，保留原标签和成员。
await tools["gallery_api"](method="PATCH", path="/api/collections/my-favorites",
    body={"label":"精选收藏"})
```

## 推送与重发：读取有副作用

GET /api/updates：query.target:string必填；count:integer默认10（轮询配置限制1..100）；mode=latest/oldest/random/latePriority/oldPriority；image_source:string可选；include_restricted:boolean默认false；delay:integer审核后等待分钟数。返回图片元数据数组。领取即写推送记录，不等待发送成功。

GET /api/pending_updates：query.target必填，返回待审图片数组并写独立待审推送记录。不要用于自动公开推广。

GET /api/plugins/napcat/replay/next：query.target、count(1..100)，返回重发图片数组，不会移除。POST /api/plugins/napcat/replay/ack，body:{target:string,image_id:string}，移除该项，返回{ok:true}。POST /api/plugins/napcat/replay用于上游自带NapCat目标的最近50张历史重发，目标取上游NapCat配置，不接受任意SakuBot目标覆盖；不要误以为可往任意队列写入。

SakuBot轮询优先replay，空时updates。批次先落本地，再发image_gallery.push_received，登记后才ack。无动作绑定时不领取；重启可恢复本地待登记批次。此事件只表示图片ID已取得，不表示图片已被发送。上游消费与本地写入之间仍有无法跨服务原子提交的故障窗口。

## 服务与插件管理

| 方法/路径 | 请求/含义 |
|---|---|
| GET /api/health | 健康信息 |
| GET /api/stats | 统计；counts.pending为待审整数 |
| GET /api/logs | 清理日志，query.page/page_size |
| GET /api/settings | {settings:配置对象,restart_required:boolean} |
| PUT /api/settings | body为当前settings对象的修改版本，结构先GET读取 |
| POST /api/settings/restart | 重启图库服务，有中断副作用，不作为测试 |
| GET /api/plugins | 上游插件清单 |
| PUT /api/plugins/{id} | body:{enabled:boolean}，启停上游插件 |
| GET /api/plugins/{id}/config | 当前插件配置，字段随source/napcat/clock变化 |
| PUT /api/plugins/{id}/config | 按GET取得的当前配置格式修改，不猜字段 |
| POST /api/plugins/source/sync | 触发图源同步，有副作用 |
| POST /api/plugins/napcat/push-now | 触发上游NapCat推送，不是SakuBot轮询 |
| GET /api/plugins/clock/access | 时钟入口可用性状态 |

所有管理调用仅按用户意图使用，尤其禁止用删除、领取推送、主动推送或重启接口试验连接。图库后台本身的推送与SakuBot推送是两套消费者，target不能共用。
