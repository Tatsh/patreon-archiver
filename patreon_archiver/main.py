from __future__ import annotations

from itertools import batched
from os import chdir
from pathlib import Path
import logging

import click
import requests

from .utils import get_all_media_uris, get_yt_dlp_downloader, unique_iter

__all__ = ('main',)

log = logging.getLogger(__name__)


@click.command()
@click.option('-o',
              '--output-dir',
              default=None,
              help='Output directory.',
              type=click.Path(file_okay=False, writable=True, resolve_path=True, path_type=Path))
@click.option('-b', '--browser', default='chrome', help='Browser to read cookies from.')
@click.option('-p', '--profile', default='Default', help='Browser profile.')
@click.option('-x',
              '--fail',
              is_flag=True,
              help='Do not continue processing after a failed yt-dlp command.')
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
def main(browser: str,
         profile: str,
         campaign_id: str,
         output_dir: Path | None = None,
         yt_dlp_arg_limit: int = 20,
         sleep_time: int = 1,
         *,
         fail: bool = False,
         debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO,
                        format='%(levelname)s:%(name)s:%(lineno)d:%(funcName)s:%(message)s')
    if output_dir is None:
        output_dir = Path('.', campaign_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    chdir(output_dir)
    try:
        media_uris = get_all_media_uris(campaign_id, browser=browser, profile=profile)
    except requests.exceptions.HTTPError as e:
        log.debug('JSON: %s', e.response.content.decode())
        click.echo('Go to patreon.com and perform the verification, wait 30 seconds and try again.',
                   err=True)
        raise click.Abort from e
    ydl = get_yt_dlp_downloader(sleep_time, debug=debug)
    for chunk in batched(unique_iter(media_uris), yt_dlp_arg_limit):
        try:
            ydl.download(chunk)
        except Exception as e:
            if fail:
                raise click.Abort from e
