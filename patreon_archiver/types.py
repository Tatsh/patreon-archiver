from typing import Mapping, Sequence, TypedDict


class PostDataAttributesPostMetadataDict(TypedDict):
    image_order: Sequence[str]


class ImageURLDict(TypedDict):
    original: str


class PostDataAttributesImageDict(TypedDict):
    image_urls: ImageURLDict
    mimetype: str


class PostDataAttributesDict(TypedDict):
    post_metadata: PostDataAttributesPostMetadataDict
    post_type: str
    url: str


class PostDataImageDict(TypedDict):
    attributes: PostDataAttributesImageDict
    id: str


class PostDataDict(TypedDict):
    attributes: PostDataAttributesDict
    id: str


class PostsDict(TypedDict):
    data: Sequence[PostDataDict]
    links: Mapping[str, str]
