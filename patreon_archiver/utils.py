"""Utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, AnyStr, Literal, TypeVar
import json
import logging

import yt_dlp_utils

from .constants import FIELDS, MEDIA_POST_TYPES, MEDIA_URI, POSTS_URI, SHARED_PARAMS
from .typing import MediaData, Posts, PostsData, SaveInfo

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

    import requests

__all__ = (
    'UnknownMimetypeError',
    'get_all_media_uris',
    'get_extension',
    'get_shared_params',
    'process_posts',
    'save_images',
    'save_other',
    'unique_iter',
    'write_if_new',
)

T = TypeVar('T')
log = logging.getLogger(__name__)


def write_if_new(target: Path | str, content: AnyStr, mode: str = 'w') -> None:
    """Write content to a file if it does not already exist."""
    target = Path(target)
    if not target.is_file():
        if 'b' in mode:
            assert isinstance(content, bytes)
            target.write_bytes(content)
        else:
            assert isinstance(content, str)
            target.write_text(content, encoding='utf-8')


class UnknownMimetypeError(Exception):
    """Exception raised when an unknown mimetype is encountered."""


def get_extension(mimetype: str) -> Literal['png', 'jpg', 'webp', 'gif']:
    """
    Get the file extension based on the mimetype.

    Raises
    ------
    UnknownMimetypeError
        If the mimetype is not recognised.
    """
    if mimetype == 'image/jpeg':
        return 'jpg'
    if mimetype == 'image/png':
        return 'png'
    if mimetype == 'image/webp':
        return 'webp'
    if mimetype == 'image/gif':
        return 'gif'
    raise UnknownMimetypeError(mimetype)


def get_shared_params(campaign_id: str) -> Mapping[str, str]:
    """Get the shared parameters for Patreon API requests."""
    return {
        **SHARED_PARAMS,
        **{f'fields[{x}]': y for x, y in FIELDS.items()},
        'filter[campaign_id]': campaign_id,
    }


def unique_iter(seq: Iterable[T]) -> Iterator[T]:
    """Based on https://stackoverflow.com/a/480227/374110."""
    seen: set[T] = set()
    seen_add = seen.add
    return (x for x in seq if not (x in seen or seen_add(x)))


def save_images(session: requests.Session, pdd: PostsData) -> SaveInfo:
    """Save images."""
    log.debug('Image file: %s', pdd['attributes']['url'])
    target_dir = Path('.', 'images', pdd['id'])
    target_dir.mkdir(parents=True, exist_ok=True)
    write_if_new(target_dir.joinpath('post.json'), f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')
    assert pdd['attributes']['post_type'] == 'image_file'
    if pdd['attributes']['post_metadata']:
        for index, id_ in enumerate(pdd['attributes']['post_metadata']['image_order'], start=1):
            with session.get(f'{MEDIA_URI}/{id_}') as req:
                data: MediaData = req.json()['data']
                with session.get(data['attributes']['image_urls']['original']) as req2:
                    write_if_new(
                        target_dir.joinpath(
                            f'{index:02d}-{data["id"]}.'
                            + get_extension(data['attributes']['mimetype'])
                        ),
                        req2.content,
                        'wb',
                    )
    return SaveInfo(post_data_dict=pdd, target_dir=target_dir)


def save_other(pdd: PostsData) -> SaveInfo:
    """Save other post types."""
    log.debug('%s: %s', pdd['attributes']['post_type'].title(), pdd['attributes']['url'])
    other = Path('.', 'other')
    other.mkdir(parents=True, exist_ok=True)
    write_if_new(
        other.joinpath(f'{pdd["attributes"]["post_type"]}-{pdd["id"]}.json'),
        f'{json.dumps(pdd, sort_keys=True, indent=2)}\n',
    )
    return SaveInfo(post_data_dict=pdd, target_dir=other)


def process_posts(posts: Posts, session: requests.Session) -> Iterator[str | SaveInfo]:
    """
    Process posts.

    Yields
    ------
    str | SaveInfo
        If ``str`` it is a media URI. Otherwise it is a :py:class:`SaveInfo` object for an image or
        other post type.
    """
    for post in posts['data']:
        if post['attributes']['post_type'] in MEDIA_POST_TYPES:
            yield post['attributes']['url']
        elif post['attributes']['post_type'] == 'image_file':
            yield from save_images(session, post)
        else:
            yield save_other(post)


def get_all_media_uris(
    campaign_id: str,
    session: requests.Session | None = None,
    browser: str | None = None,
    profile: str | None = None,
) -> Iterator[str]:
    """
    Get all media URIs for a given campaign ID.

    Parameters
    ----------
    campaign_id : str
        The campaign ID to fetch posts for.
    session : requests.Session | None
        A pre-existing requests session. If not provided, a new session will be created.
    browser : str | None
        The browser to extract cookies from. Required if ``session`` is not provided.
    profile : str | None
        The profile to extract cookies from. Required if ``session`` is not provided.

    Yields
    ------
    str
        Media URIs from the posts of the specified campaign.
    """
    if session is None:
        assert browser is not None
        assert profile is not None
        session = yt_dlp_utils.setup_session(
            browser, profile, domains={'patreon.com'}, setup_retry=True
        )
    r = session.get(POSTS_URI, params=get_shared_params(campaign_id))
    r.raise_for_status()
    posts: Posts = r.json()
    yield from (x for x in process_posts(posts, session) if isinstance(x, str))
    next_uri = posts['links']['next']
    log.debug('Next URI: %s', next_uri)
    while next_uri:
        with session.get(next_uri) as req:
            req.raise_for_status()
            posts = req.json()
            yield from (x for x in process_posts(posts, session) if isinstance(x, str))
            try:
                next_uri = posts['links']['next']
                log.debug('Next URI: %s', next_uri)
            except KeyError:
                next_uri = None
