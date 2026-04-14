"""Utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, AnyStr, Literal, TypeVar, cast
import json
import logging

from anyio import Path as AsyncPath

from .constants import FIELDS, MEDIA_POST_TYPES, MEDIA_URI, POSTS_URI, SHARED_PARAMS
from .typing import ImageFileAttributes, MediaData, Posts, PostsData, SaveInfo

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Iterator

    from niquests import AsyncSession

__all__ = (
    'UnknownMimetypeError',
    'get_all_media_uris',
    'get_extension',
    'get_shared_params',
    'process_posts',
    'save_images',
    'save_other',
    'save_podcast',
    'unique_iter',
    'write_if_new',
)

T = TypeVar('T')
log = logging.getLogger(__name__)


def write_if_new(target: Path | str, content: AnyStr, mode: str = 'w') -> None:
    """
    Write content to a file if it does not already exist.

    Parameters
    ----------
    target : Path | str
        The file path to write to.
    content : AnyStr
        The content to write.
    mode : str
        The file mode (``'w'`` for text, ``'wb'`` for binary).
    """
    target = Path(target)
    if not target.is_file():
        if 'b' in mode and isinstance(content, bytes):
            target.write_bytes(content)
        elif isinstance(content, str):
            target.write_text(content, encoding='utf-8')


class UnknownMimetypeError(Exception):
    """Exception raised when an unknown MIME type is encountered."""


def get_extension(mimetype: str) -> Literal['png', 'jpg', 'webp', 'gif']:
    """
    Get the file extension based on the mimetype.

    Parameters
    ----------
    mimetype : str
        The MIME type string.

    Returns
    -------
    Literal['png', 'jpg', 'webp', 'gif']
        The file extension.

    Raises
    ------
    UnknownMimetypeError
        If the MIME type is not recognised.
    """
    match mimetype:
        case 'image/jpeg':
            return 'jpg'
        case 'image/png':
            return 'png'
        case 'image/webp':
            return 'webp'
        case 'image/gif':
            return 'gif'
        case _:
            raise UnknownMimetypeError(mimetype)


def get_shared_params(campaign_id: str) -> dict[str, str]:
    """
    Get the shared parameters for Patreon API requests.

    Parameters
    ----------
    campaign_id : str
        The campaign ID.

    Returns
    -------
    dict[str, str]
        The shared parameters dictionary.
    """
    return {
        **SHARED_PARAMS,
        **{
            f'fields[{x}]': y
            for x, y in FIELDS.items()
        },
        'filter[campaign_id]': campaign_id,
    }


def unique_iter(seq: Iterable[T]) -> Iterator[T]:
    """
    Yield unique items from a sequence preserving order.

    Based on https://stackoverflow.com/a/480227/374110.

    Parameters
    ----------
    seq : Iterable[T]
        The input sequence.

    Returns
    -------
    Iterator[T]
        Unique items in order of first appearance.
    """
    seen: set[T] = set()
    seen_add = seen.add
    return (x for x in seq if not (x in seen or seen_add(x)))


async def save_images(session: AsyncSession, pdd: PostsData) -> SaveInfo:
    """
    Save images.

    Parameters
    ----------
    session : AsyncSession
        The niquests async session to use for downloads.
    pdd : PostsData
        The post data dictionary.

    Returns
    -------
    SaveInfo
        Information about the saved images.
    """
    log.debug('Image file: %s', pdd['attributes']['url'])
    target_dir = Path('.', 'images', pdd['id'])
    await AsyncPath(target_dir).mkdir(parents=True, exist_ok=True)
    write_if_new(target_dir.joinpath('post.json'), f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')
    attrs = cast('ImageFileAttributes', pdd['attributes'])
    if attrs['post_metadata']:
        for index, id_ in enumerate(attrs['post_metadata']['image_order'], start=1):
            req = await session.get(f'{MEDIA_URI}/{id_}')
            data: MediaData = req.json()['data']
            req2 = await session.get(data['attributes']['image_urls']['original'])
            if req2.content is not None:
                write_if_new(
                    target_dir.joinpath(f'{index:02d}-{data["id"]}.' +
                                        get_extension(data['attributes']['mimetype'])),
                    req2.content,
                    'wb',
                )
    return SaveInfo(post_data_dict=pdd, target_dir=target_dir)


def save_other(pdd: PostsData) -> SaveInfo:
    """
    Save other post types.

    Parameters
    ----------
    pdd : PostsData
        The post data dictionary.

    Returns
    -------
    SaveInfo
        Information about the saved post.
    """
    log.debug('%s: %s', pdd['attributes']['post_type'].title(), pdd['attributes']['url'])
    other = Path('.', 'other')
    other.mkdir(parents=True, exist_ok=True)
    write_if_new(
        other.joinpath(f'{pdd["attributes"]["post_type"]}-{pdd["id"]}.json'),
        f'{json.dumps(pdd, sort_keys=True, indent=2)}\n',
    )
    return SaveInfo(post_data_dict=pdd, target_dir=other)


async def save_podcast(session: AsyncSession, pdd: PostsData) -> SaveInfo:
    """
    Save podcast posts.

    Parameters
    ----------
    session : AsyncSession
        The niquests async session to use for downloads.
    pdd : PostsData
        The post data dictionary.

    Returns
    -------
    SaveInfo
        Information about the saved podcast.
    """
    log.debug('Podcast: %s', pdd['attributes']['url'])
    target_dir = Path('.', 'podcasts', pdd['id'])
    await AsyncPath(target_dir).mkdir(parents=True, exist_ok=True)
    write_if_new(target_dir.joinpath('post.json'), f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')

    media_list = pdd.get('relationships', {}).get('media', {}).get('data', [])
    for index, media_ref in enumerate(media_list, start=1):
        media_id = media_ref['id']
        req = await session.get(f'{MEDIA_URI}/{media_id}')
        media: MediaData = req.json()['data']
        if download_url := media['attributes'].get('download_url'):
            file_name = Path(media['attributes'].get('file_name') or media_id).name
            req2 = await session.get(download_url)
            if req2.content is not None:
                write_if_new(target_dir.joinpath(f'{media_id}-{file_name}'), req2.content, 'wb')
        elif media['attributes'].get('image_urls') and (
                image_url := media['attributes']['image_urls'].get('original')):
            ext = get_extension(media['attributes']['mimetype'])
            req2 = await session.get(image_url)
            if req2.content is not None:
                write_if_new(
                    target_dir.joinpath(f'{index:02d}-{media_id}.{ext}'),
                    req2.content,
                    'wb',
                )
    return SaveInfo(post_data_dict=pdd, target_dir=target_dir)


async def process_posts(posts: Posts,
                        session: AsyncSession,
                        *,
                        process_podcasts: bool = True) -> AsyncIterator[str | SaveInfo]:
    """
    Process posts.

    Parameters
    ----------
    posts : Posts
        The posts data from the API.
    session : AsyncSession
        The niquests async session to use for downloads.
    process_podcasts : bool
        If ``True``, uses Patreon Archiver's handler to download podcasts and metadata. If
        ``False``, the media URL is yielded.

    Yields
    ------
    str | SaveInfo
        If ``str`` it is a media URI. Otherwise it is a :py:class:`SaveInfo` object for an image or
        other post type.
    """
    media_post_types = set(MEDIA_POST_TYPES) | ({'podcast'} if not process_podcasts else set())
    for post in posts['data']:
        post_type = post['attributes']['post_type']
        match post_type:
            case t if t in media_post_types:
                log.debug('Sending URI: %s', post['attributes']['url'])
                yield post['attributes']['url']
            case 'image_file':
                yield await save_images(session, post)
            case 'podcast':
                yield await save_podcast(session, post)
            case _:
                yield save_other(post)


async def get_all_media_uris(
    campaign_id: str,
    session: AsyncSession,
    *,
    process_podcasts: bool = True,
) -> AsyncIterator[str]:
    """
    Get all media URIs for a given campaign ID.

    Parameters
    ----------
    campaign_id : str
        The campaign ID to fetch posts for.
    session : AsyncSession
        The niquests async session to use for API calls.
    process_podcasts : bool
        If ``True``, uses Patreon Archiver's handler for podcasts. If ``False``, yields podcast
        media URLs for yt-dlp.

    Yields
    ------
    str
        Media URIs from the posts of the specified campaign.
    """
    r = await session.get(POSTS_URI, params=get_shared_params(campaign_id))
    r.raise_for_status()
    posts: Posts = r.json()
    async for x in process_posts(posts, session, process_podcasts=process_podcasts):
        if isinstance(x, str):
            yield x
    next_uri = posts['links']['next']
    log.debug('Next URI: %s', next_uri)
    while next_uri:
        req = await session.get(next_uri)
        req.raise_for_status()
        posts = req.json()
        async for x in process_posts(posts, session, process_podcasts=process_podcasts):
            if isinstance(x, str):
                yield x
        try:
            next_uri = posts['links']['next']
            log.debug('Next URI: %s', next_uri)
        except KeyError:
            next_uri = None
