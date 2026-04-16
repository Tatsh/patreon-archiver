"""Utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
import json
import logging

from anyio import Path as AsyncPath

from .constants import FIELDS, MEDIA_URI, POSTS_URI, SHARED_PARAMS
from .typing import ImageFileAttributes, MediaData, Posts, PostsData, SaveInfo

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from niquests import AsyncSession

    from .typing import OnMessage

__all__ = ('UnknownMimetypeError', 'get_all_posts', 'save_images', 'save_other', 'save_podcast')

log = logging.getLogger(__name__)


def _write_if_new(target: Path | str, content: str | bytes, mode: str = 'w') -> None:
    """
    Write content to a file if it does not already exist.

    Parameters
    ----------
    target : Path | str
        The file path to write to.
    content : str | bytes
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


def _get_extension(mimetype: str) -> Literal['png', 'jpg', 'webp', 'gif']:
    """
    Get the file extension based on the MIME type.

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


def _get_shared_params(campaign_id: str) -> dict[str, str]:
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


async def save_images(session: AsyncSession,
                      pdd: PostsData,
                      *,
                      on_message: OnMessage | None = None) -> SaveInfo:
    """
    Save images.

    Parameters
    ----------
    session : AsyncSession
        The niquests async session to use for downloads.
    pdd : PostsData
        The post data dictionary.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.

    Returns
    -------
    SaveInfo
        Information about the saved images.
    """
    if on_message is not None:
        on_message(f'Processing image post {pdd["id"]}...')
    log.debug('Image file: %s', pdd['attributes']['url'])
    target_dir = Path('.', 'images', pdd['id'])
    await AsyncPath(target_dir).mkdir(parents=True, exist_ok=True)
    _write_if_new(target_dir.joinpath('post.json'),
                  f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')
    attrs = cast('ImageFileAttributes', pdd['attributes'])
    if attrs['post_metadata']:
        for index, id_ in enumerate(attrs['post_metadata']['image_order'], start=1):
            req = await session.get(f'{MEDIA_URI}/{id_}')
            data: MediaData = req.json()['data']
            req2 = await session.get(data['attributes']['image_urls']['original'])
            if req2.content is not None:
                _write_if_new(
                    target_dir.joinpath(f'{index:02d}-{data["id"]}.' +
                                        _get_extension(data['attributes']['mimetype'])),
                    req2.content,
                    'wb',
                )
    if on_message is not None:
        on_message(f'Saved image post {pdd["id"]}.')
    return SaveInfo(post_data_dict=pdd, target_dir=target_dir)


def save_other(pdd: PostsData, *, on_message: OnMessage | None = None) -> SaveInfo:
    """
    Save other post types.

    Parameters
    ----------
    pdd : PostsData
        The post data dictionary.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.

    Returns
    -------
    SaveInfo
        Information about the saved post.
    """
    if on_message is not None:
        on_message(f'Processing post {pdd["id"]}...')
    log.debug('%s: %s', pdd['attributes']['post_type'].title(), pdd['attributes']['url'])
    other = Path('.', 'other')
    other.mkdir(parents=True, exist_ok=True)
    _write_if_new(
        other.joinpath(f'{pdd["attributes"]["post_type"]}-{pdd["id"]}.json'),
        f'{json.dumps(pdd, sort_keys=True, indent=2)}\n',
    )
    if on_message is not None:
        on_message(f'Saved post {pdd["id"]}.')
    return SaveInfo(post_data_dict=pdd, target_dir=other)


async def save_podcast(session: AsyncSession,
                       pdd: PostsData,
                       *,
                       on_message: OnMessage | None = None) -> SaveInfo:
    """
    Save podcast posts.

    Parameters
    ----------
    session : AsyncSession
        The niquests async session to use for downloads.
    pdd : PostsData
        The post data dictionary.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.

    Returns
    -------
    SaveInfo
        Information about the saved podcast.
    """
    if on_message is not None:
        on_message(f'Processing podcast post {pdd["id"]}...')
    log.debug('Podcast: %s', pdd['attributes']['url'])
    target_dir = Path('.', 'podcasts', pdd['id'])
    await AsyncPath(target_dir).mkdir(parents=True, exist_ok=True)
    _write_if_new(target_dir.joinpath('post.json'),
                  f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')

    media_list = pdd.get('relationships', {}).get('media', {}).get('data', [])
    for index, media_ref in enumerate(media_list, start=1):
        media_id = media_ref['id']
        req = await session.get(f'{MEDIA_URI}/{media_id}')
        media: MediaData = req.json()['data']
        if download_url := media['attributes'].get('download_url'):
            file_name = Path(media['attributes'].get('file_name') or media_id).name
            req2 = await session.get(download_url)
            if req2.content is not None:
                _write_if_new(target_dir.joinpath(f'{media_id}-{file_name}'), req2.content, 'wb')
        elif media['attributes'].get('image_urls') and (
                image_url := media['attributes']['image_urls'].get('original')):
            ext = _get_extension(media['attributes']['mimetype'])
            req2 = await session.get(image_url)
            if req2.content is not None:
                _write_if_new(
                    target_dir.joinpath(f'{index:02d}-{media_id}.{ext}'),
                    req2.content,
                    'wb',
                )
    if on_message is not None:
        on_message(f'Saved podcast post {pdd["id"]}.')
    return SaveInfo(post_data_dict=pdd, target_dir=target_dir)


async def get_all_posts(campaign_id: str,
                        session: AsyncSession,
                        *,
                        on_message: OnMessage | None = None) -> AsyncIterator[PostsData]:
    """
    Yield all posts for a campaign.

    Parameters
    ----------
    campaign_id : str
        The campaign ID to fetch posts for.
    session : AsyncSession
        The niquests async session to use for API calls.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.

    Yields
    ------
    PostsData
        A single post payload from the Patreon API.
    """
    req = await session.get(POSTS_URI, params=_get_shared_params(campaign_id))
    req.raise_for_status()
    posts: Posts = req.json()
    for post in posts['data']:
        yield post

    next_uri = posts.get('links', {}).get('next')
    if next_uri:
        log.debug('Next URI: %s', next_uri)
    while next_uri:
        if on_message is not None:
            on_message('Fetching next page of posts...')
        req = await session.get(next_uri)
        req.raise_for_status()
        posts = req.json()
        for post in posts['data']:
            yield post
        next_uri = posts.get('links', {}).get('next')
        if next_uri:
            log.debug('Next URI: %s', next_uri)
