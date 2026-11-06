"""Authoritative documented argument types; preserve registered constraints."""
from __future__ import annotations
from typing import Annotated, Literal, NotRequired, Required, TypedDict, TypeAlias

A_fetch_anime_image1 = TypedDict(
    'A_fetch_anime_image1',
    {
        'orientation': NotRequired[Annotated[str, {'default': '', 'description': 'horizontal 横图、vertical 竖图；空字符串随机'}]],
    },
    total=False,
)

A_fetch_anime_image: TypeAlias = Annotated[A_fetch_anime_image1, {'additionalProperties': False}]

A_count_pending_images2 = TypedDict(
    'A_count_pending_images2',
    {
    },
    total=False,
)

A_count_pending_images: TypeAlias = Annotated[A_count_pending_images2, {'additionalProperties': False}]

A_gallery_send3 = TypedDict(
    'A_gallery_send3',
    {
        'path': Required[Annotated[str, {'description': 'fetch_anime_image 返回的工作空间图片相对路径'}]],
    },
    total=False,
)

A_gallery_send: TypeAlias = Annotated[A_gallery_send3, {'additionalProperties': False}]

ARGUMENTS = {'fetch_anime_image': A_fetch_anime_image, 'count_pending_images': A_count_pending_images, 'gallery_send': A_gallery_send}
