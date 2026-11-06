"""Plugin-owned result contracts. Dynamic platform fields are explicitly open."""
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias
from sakubot.contracts.common import Artifact, DynamicObject, DynamicJSON, Truncated

class Pending(TypedDict, total=False):
    pending: Required[Annotated[int, '待审核图片数']]

class ImageResult(TypedDict, total=False):
    id: Required[Annotated[str, '图库图片 ID']]
    url: Required[Annotated[str, '发布的框架附件地址']]
    name: Required[Annotated[str, '附件文件名']]
    mime: Required[Annotated[str, '图片 MIME']]
    expires: Required[Annotated[float, '附件过期 Unix 秒']]
    path: Required[Annotated[str, '工作空间图片相对路径']]
    at: Required[Annotated[float, '取图 Unix 秒']]

class Sent(TypedDict, total=False):
    sent: Required[Annotated[bool, '是否已提交发送']]
    url: Required[Annotated[str, '框架附件 URL']]
    name: Required[Annotated[str, '文件名']]
    mime: Required[Annotated[str, 'MIME']]
    expires: Required[Annotated[float, '过期 Unix 秒']]

R_count_pending_images: TypeAlias = Pending
R_fetch_anime_image: TypeAlias = ImageResult
R_gallery_send: TypeAlias = Sent

RESULTS = {'count_pending_images': R_count_pending_images, 'fetch_anime_image': R_fetch_anime_image, 'gallery_send': R_gallery_send}
