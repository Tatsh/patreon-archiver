"""Typing helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


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


class PostsData(TypedDict):
    """Data for a Patreon post."""

    attributes: (
        AudioEmbedAttributes
        | AudioFileAttributes
        | ImageFileAttributes
        | VideoEmbedAttributes
        | LivestreamCrowdcastAttributes
    )
    """Attributes of the post."""
    id: str
    """ID of the post."""


class _Links(TypedDict):
    next: str | None


class Posts(TypedDict):
    """Container for Patreon posts from API."""

    data: Sequence[PostsData]
    """List of post data."""
    links: _Links
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
