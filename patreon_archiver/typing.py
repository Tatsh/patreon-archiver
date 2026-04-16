"""Typing helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias, TypedDict

from typing_extensions import NotRequired

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

__all__ = ('AudioEmbedAttributes', 'AudioFileAttributes', 'CommonAttributes', 'ImageFileAttributes',
           'ImageFileAttributesPostMetadata', 'Links', 'LivestreamCrowdcastAttributes', 'Media',
           'MediaData', 'MediaDataAttributes', 'MediaDataAttributesImageURLs', 'OnMessage',
           'PodcastAttributes', 'PostAttributes', 'PostFile', 'Posts', 'PostsData',
           'PostsDataRelationships', 'PostsDataRelationshipsMedia',
           'PostsDataRelationshipsMediaData', 'SaveInfo', 'Stats', 'VideoEmbedAttributes')

OnMessage: TypeAlias = Callable[[str], None]
"""Callback used to report human-readable progress updates."""


@dataclass
class Stats:
    """Live pipeline statistics shown in the progress spinner."""

    posts_handled: int = 0
    """Number of posts routed by the producer so far."""
    images_processed: int = 0
    """Number of image posts that have been saved successfully."""
    others_processed: int = 0
    """Number of non-media posts that have been saved successfully."""
    podcasts_processed: int = 0
    """Number of podcast posts that have been saved successfully."""
    yt_dlp_total_uris: int = 0
    """Running total of URIs the producer has sent to the yt-dlp worker."""
    yt_dlp_current_uri: str | None = None
    """URI yt-dlp is currently downloading, or ``None`` when idle."""
    yt_dlp_current_index: int = 0
    """
    1-based index of the URI currently being processed within :attr:`yt_dlp_total_uris`.
    """


class CommonAttributes(TypedDict):
    """Attributes shared by all post types."""

    url: str
    """URL of the post."""


class AudioEmbedAttributes(CommonAttributes, TypedDict):
    """Attributes for audio embed posts."""

    post_type: Literal['audio_embed']
    """Post type."""


class AudioFileAttributes(CommonAttributes, TypedDict):
    """Attributes for audio file posts."""

    post_type: Literal['audio_file']
    """Post type."""


class PostFile(TypedDict):
    """File information for posts."""

    name: str
    """Name of the file."""
    url: str
    """URL of the file."""


class ImageFileAttributesPostMetadata(TypedDict):
    """Metadata for image file posts."""

    image_order: Sequence[str]
    """Order of images in the post."""


class ImageFileAttributes(CommonAttributes, TypedDict):
    """Attributes for image file posts."""

    post_file: PostFile
    """File."""
    post_metadata: ImageFileAttributesPostMetadata | None
    """Metadata."""
    post_type: Literal['image_file']
    """Post type."""


class VideoEmbedAttributes(CommonAttributes, TypedDict):
    """Attributes for video embed posts."""

    post_type: Literal['video_embed']
    """Post type."""


class LivestreamCrowdcastAttributes(CommonAttributes, TypedDict):
    """Attributes for 'livestream crowdcast' posts."""

    post_type: Literal['livestream_crowdcast']
    """Post type."""


class PodcastAttributes(CommonAttributes, TypedDict):
    """Attributes for podcast posts."""

    post_type: Literal['podcast']
    """Post type."""


PostAttributes: TypeAlias = (AudioEmbedAttributes
                             | AudioFileAttributes
                             | ImageFileAttributes
                             | VideoEmbedAttributes
                             | LivestreamCrowdcastAttributes
                             | PodcastAttributes)
"""Union of all supported post attribute payloads."""


class PostsDataRelationshipsMediaData(TypedDict):
    """Media data of a post."""

    id: str
    """ID of the media."""
    type: Literal['media']
    """Type of the media."""


class PostsDataRelationshipsMedia(TypedDict):
    """Media data of a post."""

    data: NotRequired[list[PostsDataRelationshipsMediaData]]
    """Media data."""


class PostsDataRelationships(TypedDict):
    """Relationships for post data."""

    media: NotRequired[PostsDataRelationshipsMedia]
    """Media data."""


class PostsData(TypedDict):
    """Data for a Patreon post."""

    attributes: PostAttributes
    """Attributes of the post."""
    id: str
    """ID of the post."""
    relationships: PostsDataRelationships
    """Relationships for the post."""


class Links(TypedDict):
    """Links for pagination."""

    next: str | None
    """Next page URI."""


class Posts(TypedDict):
    """Container for Patreon posts from API."""

    data: Sequence[PostsData]
    """List of post data."""
    links: NotRequired[Links]
    """Links for pagination."""


class MediaDataAttributesImageURLs(TypedDict):
    """URLs for media data attributes."""

    original: str
    """URL for the original image."""


class MediaDataAttributes(TypedDict):
    """Attributes for media data."""

    image_urls: MediaDataAttributesImageURLs
    """URLs for images."""
    mimetype: str
    """MIME type of the media."""
    download_url: str
    """URL to download the media file."""
    file_name: str
    """Original file name of the media."""


class MediaData(TypedDict):
    """Data for a media item."""

    attributes: MediaDataAttributes
    """Media data attributes."""
    id: str
    """ID."""


class Media(TypedDict):
    """Container for media data."""

    data: MediaData
    """Media data."""


class SaveInfo(TypedDict):
    """Information about a saved post."""

    post_data_dict: PostsData
    """Data dictionary for the post."""
    target_dir: Path
    """Directory where the post is saved."""
