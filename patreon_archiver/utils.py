from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, AnyStr, Literal, TypeVar
import json
import logging
import re
import sys

from requests.adapters import HTTPAdapter
from urllib3 import Retry
from yt_dlp.cookies import extract_cookies_from_browser
import requests
import yt_dlp

from .constants import FIELDS, MEDIA_POST_TYPES, MEDIA_URI, POSTS_URI, SHARED_HEADERS, SHARED_PARAMS
from .typing import MediaData, Posts, PostsData, SaveInfo

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

__all__ = ('UnknownMimetypeError', 'YoutubeDLLogger', 'create_session', 'get_all_media_uris',
           'get_extension', 'get_shared_params', 'get_yt_dlp_downloader', 'process_posts',
           'save_images', 'save_other', 'unique_iter', 'write_if_new')

T = TypeVar('T')
log = logging.getLogger(__name__)


def write_if_new(target: Path | str, content: AnyStr, mode: str = 'w') -> None:
    target = Path(target)
    if not target.is_file():
        if 'b' in mode:
            assert isinstance(content, bytes)
            target.write_bytes(content)
        else:
            assert isinstance(content, str)
            target.write_text(content, encoding='utf-8')


class UnknownMimetypeError(Exception):
    pass


def get_extension(mimetype: str) -> Literal['png', 'jpg', 'webp', 'gif']:
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
    return {
        **SHARED_PARAMS,
        **{
            f'fields[{x}]': y
            for x, y in FIELDS.items()
        },
        'filter[campaign_id]': campaign_id,
    }


def unique_iter(seq: Iterable[T]) -> Iterator[T]:
    """https://stackoverflow.com/a/480227/374110."""
    seen: set[T] = set()
    seen_add = seen.add
    return (x for x in seq if not (x in seen or seen_add(x)))


class YoutubeDLLogger:
    def debug(self, message: str) -> None:
        if re.match(r'^\[download\]\s+[0-9\.]+%', message):
            return
        log.info('%s', re.sub(r'^\[(?:info|debug)\]\s+', '', message))

    def info(self, message: str) -> None:
        log.info('%s', re.sub(r'^\[info\]\s+', '', message))

    def warning(self, message: str) -> None:
        log.warning('%s', re.sub(r'^\[warn(?:ing)?\]\s+', '', message))

    def error(self, message: str) -> None:
        log.error('%s', re.sub(r'^\[err(?:or)?\]\s+', '', message))


def save_images(session: requests.Session, pdd: PostsData) -> SaveInfo:
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
                        target_dir.joinpath(f'{index:02d}-{data["id"]}.' +
                                            get_extension(data['attributes']['mimetype'])),
                        req2.content, 'wb')
    return SaveInfo(post_data_dict=pdd, target_dir=target_dir)


def save_other(pdd: PostsData) -> SaveInfo:
    log.debug('%s: %s', pdd['attributes']['post_type'].title(), pdd['attributes']['url'])
    other = Path('.', 'other')
    other.mkdir(parents=True, exist_ok=True)
    write_if_new(other.joinpath(f'{pdd["attributes"]["post_type"]}-{pdd["id"]}.json'),
                 f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')
    return SaveInfo(post_data_dict=pdd, target_dir=other)


def process_posts(posts: Posts, session: requests.Session) -> Iterator[str | SaveInfo]:
    for post in posts['data']:
        if post['attributes']['post_type'] in MEDIA_POST_TYPES:
            yield post['attributes']['url']
        elif post['attributes']['post_type'] == 'image_file':
            yield from save_images(session, post)
        else:
            yield save_other(post)


def create_session(browser: str, profile: str) -> requests.Session:
    session = requests.Session()
    session.mount(
        'https://',
        HTTPAdapter(
            max_retries=Retry(backoff_factor=2.5, status_forcelist=(429, 500, 502, 503, 504))))
    session.headers.update(
        SHARED_HEADERS | {
            'cookie':
                '; '.join(f'{cookie.name}={cookie.value}'
                          for cookie in extract_cookies_from_browser(browser, profile)
                          if 'patreon.com' in cookie.domain)
        })
    return session


def get_yt_dlp_downloader(sleep_time: int, *, debug: bool = False) -> yt_dlp.YoutubeDL:
    sys.argv = [sys.argv[0]]
    ydl_opts = yt_dlp.parse_options()[-1]
    ydl_opts['color'] = {'stdout': 'never', 'stderr': 'never'}
    ydl_opts['logger'] = YoutubeDLLogger()
    ydl_opts['sleep_interval_requests'] = sleep_time
    ydl_opts['verbose'] = debug
    return yt_dlp.YoutubeDL(ydl_opts)


def get_all_media_uris(campaign_id: str,
                       session: requests.Session | None = None,
                       browser: str | None = None,
                       profile: str | None = None) -> Iterator[str]:
    if session is None:
        assert browser is not None
        assert profile is not None
        session = create_session(browser, profile)
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
