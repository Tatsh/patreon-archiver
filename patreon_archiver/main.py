from __future__ import annotations

from itertools import batched
from os import chdir
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict
import json
import logging
import sys

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from yt_dlp.cookies import extract_cookies_from_browser
import click
import requests
import yt_dlp

from .constants import MEDIA_URI, POSTS_URI, SHARED_HEADERS
from .utils import (
    YoutubeDLLogger,
    get_extension,
    get_shared_params,
    unique_iter,
    write_if_new,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .patreon_typing import MediaData, Posts, PostsData

__all__ = ('main',)

logger = logging.getLogger(__name__)


class SaveInfo(TypedDict):
    post_data_dict: PostsData
    target_dir: Path


def save_images(session: requests.Session, pdd: PostsData) -> SaveInfo:
    click.secho(f'Image file: {pdd["attributes"]["url"]}')
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
    click.secho(f'{pdd["attributes"]["post_type"].title()}: ' + pdd['attributes']['url'])
    other = Path('.', 'other')
    other.mkdir(parents=True, exist_ok=True)
    write_if_new(other.joinpath(f'{pdd["attributes"]["post_type"]}-{pdd["id"]}.json'),
                 f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')
    return SaveInfo(post_data_dict=pdd, target_dir=other)


MEDIA_POST_TYPES = {'audio_file', 'audio_embed', 'video_embed', 'video_external_file'}


def process_posts(posts: Posts, session: requests.Session) -> Iterator[str | SaveInfo]:
    for post in posts['data']:
        if post['attributes']['post_type'] in MEDIA_POST_TYPES:
            yield post['attributes']['url']
        elif post['attributes']['post_type'] == 'image_file':
            yield from save_images(session, post)
        else:
            yield save_other(post)


@click.command()
@click.option('-o', '--output-dir', default=None, help='Output directory')
@click.option('-b', '--browser', default='chrome', help='Browser to read cookies from')
@click.option('-p', '--profile', default='Default', help='Browser profile')
@click.option('-x',
              '--fail',
              is_flag=True,
              help=('Do not continue processing after a failed '
                    'yt-dlp command.'))
@click.option('-L',
              '--yt-dlp-arg-limit',
              default=20,
              type=int,
              help='Number of media URIs to pass to yt-dlp at a time.')
@click.option('-S',
              '--sleep-time',
              default=1,
              type=int,
              help='Number of seconds to wait between requests')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output')
@click.argument('campaign_id')
def main(output_dir: Path | str | None,
         browser: str,
         profile: str,
         campaign_id: str,
         yt_dlp_arg_limit: int = 20,
         sleep_time: int = 1,
         *,
         fail: bool = False,
         debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    if output_dir is None:
        output_dir = Path('.', campaign_id)
        output_dir.mkdir(parents=True, exist_ok=True)
    chdir(output_dir)
    with requests.Session() as session:
        session.mount(
            'https://',
            HTTPAdapter(
                max_retries=Retry(backoff_factor=2.5, status_forcelist=[429, 500, 502, 503, 504])))
        headers = dict(**SHARED_HEADERS)
        cookies = '; '.join(f'{cookie.name}={cookie.value}'
                            for cookie in extract_cookies_from_browser(browser, profile)
                            if 'patreon.com' in cookie.domain)
        session.headers.update({**headers, 'cookie': cookies})
        try:
            with session.get(POSTS_URI, params=get_shared_params(campaign_id)) as req:
                req.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.debug('JSON: %s', e.response.content.decode())
            click.echo(
                'Go to patreon.com and perform the verification, wait 30 seconds and try again.',
                err=True)
            raise click.Abort from e
        posts: Posts = req.json()
        media_uris = [x for x in process_posts(posts, session) if isinstance(x, str)]
        next_uri = posts['links']['next']
        logger.debug('Next URI: %s', next_uri)
        while next_uri:
            with session.get(next_uri) as req:
                req.raise_for_status()
                posts = req.json()
                media_uris.extend(x for x in process_posts(posts, session) if isinstance(x, str))
                try:
                    next_uri = posts['links']['next']
                    logger.debug('Next URI: %s', next_uri)
                except KeyError:
                    next_uri = None
        sys.argv = [sys.argv[0]]
        ydl_opts = yt_dlp.parse_options()[-1]
        ydl_opts['logger'] = YoutubeDLLogger()
        ydl_opts['sleep_interval_requests'] = sleep_time
        ydl_opts['verbose'] = debug
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        for chunk in (list(x) for x in batched(unique_iter(media_uris), yt_dlp_arg_limit)):
            try:
                ydl.download(chunk)
            except Exception as e:
                if fail:
                    raise click.Abort from e
