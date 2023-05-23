from typing import Literal, Sequence, TypedDict


class CommonAttributes(TypedDict):
    url: str


class AudioEmbedAttributes(CommonAttributes, TypedDict):
    post_type: Literal['audio_embed']


class AudioFileAttributes(CommonAttributes, TypedDict):
    post_type: Literal['audio_file']


class _PostFile(TypedDict):
    name: str
    url: str


class ImageFileAttributesPostMetadata(TypedDict):
    image_order: Sequence[str]


class ImageFileAttributes(CommonAttributes, TypedDict):
    post_file: _PostFile
    post_metadata: ImageFileAttributesPostMetadata | None
    post_type: Literal['image_file']


class VideoEmbedAttributes(CommonAttributes, TypedDict):
    post_type: Literal['video_embed']


class PostsData(TypedDict):
    attributes: (AudioEmbedAttributes | AudioFileAttributes
                 | ImageFileAttributes | VideoEmbedAttributes)
    id: str


class _Links(TypedDict):
    next: str | None


class Posts(TypedDict):
    data: Sequence[PostsData]
    links: _Links


class MediaDataAttributesImageURLs(TypedDict):
    original: str


class MediaDataAttributes(TypedDict):
    image_urls: MediaDataAttributesImageURLs
    mimetype: str


class MediaData(TypedDict):
    attributes: MediaDataAttributes
    id: str


class Media(TypedDict):
    data: MediaData
