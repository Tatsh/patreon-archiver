from os import chdir, makedirs
from pathlib import Path
from typing import List, Optional, Union
import json
import subprocess as sp

from loguru import logger
from yt_dlp.cookies import extract_cookies_from_browser
import click
import requests

from .constants import MEDIA_URI, POSTS_URI, SHARED_HEADERS
from .patreon_typing import PostDataDict, PostDataImageDict, PostsDict
from .utils import (chunks, get_extension, get_shared_params, setup_logging,
                    write_if_new)

__all__ = ('main',)


def save_images(session: requests.Session, pdd: PostDataDict) -> None:
    click.secho(f"Image file: {pdd['attributes']['url']}")
    target_dir = Path('.', 'images', pdd['id'])
    makedirs(target_dir, exist_ok=True)
    write_if_new(target_dir.joinpath('post.json'),
                 f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')
    for index, id_ in enumerate(
            pdd['attributes']['post_metadata']['image_order'], start=1):
        with session.get(f'{MEDIA_URI}/{id_}') as r:
            data: PostDataImageDict = r.json()['data']
            with session.get(
                    data['attributes']['image_urls']['original']) as r:
                write_if_new(
                    target_dir.joinpath(
                        f'{index:02d}-{data["id"]}.' +
                        get_extension(data["attributes"]["mimetype"])),
                    r.content, 'wb')


def save_other(pdd: PostDataDict) -> None:
    click.secho(f"{pdd['attributes']['post_type'].title()}: " +
                pdd['attributes']['url'])
    other = Path('.', 'other')
    makedirs(other, exist_ok=True)
    write_if_new(
        other.joinpath(f"{pdd['attributes']['post_type']}-{pdd['id']}.json"),
        f'{json.dumps(pdd, sort_keys=True, indent=2)}\n')


def process_posts(posts: PostsDict, media_uris: List[str],
                  session: requests.Session) -> None:
    for post in posts['data']:
        if (post['attributes']['post_type']
                in ('audio_file', 'audio_embed', 'video_embed')):
            media_uris.append(post['attributes']['url'])
        elif post['attributes']['post_type'] == 'image_file':
            save_images(session, post)
        else:
            save_other(post)


@click.command()
@click.option('-o', '--output-dir', default=None, help='Output directory')
@click.option('-b',
              '--browser',
              default='chrome',
              help='Browser to read cookies from')
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
@click.option('-d', '--debug', is_flag=True, help='Enable debug output')
@click.argument('campaign_id')
def main(output_dir: Optional[Union[Path, str]],
         browser: str,
         profile: str,
         campaign_id: str,
         fail: bool = False,
         yt_dlp_arg_limit: int = 20,
         debug: bool = False) -> None:
    setup_logging(debug)
    if output_dir is None:
        output_dir = Path('.', campaign_id)
        makedirs(output_dir, exist_ok=True)
    chdir(output_dir)
    with requests.Session() as session:
        session.headers.update({
            **SHARED_HEADERS,
            **dict(cookie='; '.join(f'{c.name}={c.value}' \
                for c in extract_cookies_from_browser(browser, profile)
                    if 'patreon.com' in c.domain))
        })
        with session.get(POSTS_URI,
                         params=get_shared_params(campaign_id)) as r:
            r.raise_for_status()
            media_uris: List[str] = []
            posts: PostsDict = r.json()
            process_posts(posts, media_uris, session)
            next_uri: Optional[str] = posts['links']['next']
            logger.debug(f'Next URI: {next_uri}')
            while next_uri:
                with session.get(next_uri) as r:
                    r.raise_for_status()
                    posts = r.json()
                    process_posts(posts, media_uris, session)
                    try:
                        next_uri = posts['links']['next']
                        logger.debug(f'Next URI: {next_uri}')
                    except KeyError:
                        next_uri = None
            for chunk in chunks(list(set(media_uris)), yt_dlp_arg_limit):
                try:
                    sp.run(['yt-dlp'] + list(chunk), check=True)
                except sp.CalledProcessError as e:
                    if fail:
                        raise click.Abort() from e
