from typing import Literal as L, Sequence, TypedDict

__all__ = ('PostDataImageDict', 'PostsDict')


class PostDataAttributesPostMetadataDict(TypedDict):
    image_order: Sequence[str]


class ImageURLDict(TypedDict):
    original: str


class PostDataAttributesImageDict(TypedDict):
    image_urls: ImageURLDict
    mimetype: str


class PostDataAttributesDict(TypedDict):
    post_metadata: PostDataAttributesPostMetadataDict
    post_type: L['audio_file'] | L['audio_embed'] | L['video_embed']
    url: str


class PostDataImageDict(TypedDict):
    attributes: PostDataAttributesImageDict
    id: str


class PostDataDict(TypedDict):
    attributes: PostDataAttributesDict
    id: str


class PagerDict(TypedDict, total=False):
    next: str | None


class PostsDict(TypedDict):
    data: Sequence[PostDataDict]
    links: PagerDict
