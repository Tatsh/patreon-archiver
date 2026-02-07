"""Entry point."""

from __future__ import annotations

from itertools import batched
from os import chdir
from pathlib import Path
import json
import logging

from bascom import setup_logging
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from yt_dlp_utils.constants import DEFAULT_RETRY_BACKOFF_FACTOR, DEFAULT_RETRY_STATUS_FORCELIST
import click
import requests
import yt_dlp_utils

from .constants import SHARED_HEADERS
from .utils import get_all_media_uris, unique_iter

__all__ = ('main',)

log = logging.getLogger(__name__)


@click.command()
@click.option(
    '-o',
    '--output-dir',
    default=None,
    help='Output directory.',
    type=click.Path(file_okay=False, writable=True, resolve_path=True, path_type=Path),
)
@click.option('-b', '--browser', default='chrome', help='Browser to read cookies from.')
@click.option('-p', '--profile', default='Default', help='Browser profile.')
@click.option(
    '-c',
    '--cookies-json',
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
    help='Path to JSON file containing cookies (overrides --browser/--profile).',
)
@click.option(
    '-x', '--fail', is_flag=True, help='Do not continue processing after a failed yt-dlp command.'
)
@click.option(
    '-L',
    '--yt-dlp-arg-limit',
    default=20,
    type=int,
    help='Number of media URIs to pass to yt-dlp at a time.',
)
@click.option(
    '-P', '--use-yt-dlp-for-podcasts', is_flag=True, help='Use yt-dlp to download podcasts.'
)
@click.option(
    '-S', '--sleep-time', default=1, type=int, help='Number of seconds to wait between requests.'
)
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.argument('campaign_id')
def main(
    browser: str,
    profile: str,
    campaign_id: str,
    output_dir: Path | None = None,
    cookies_json: Path | None = None,
    yt_dlp_arg_limit: int = 20,
    sleep_time: int = 1,
    *,
    fail: bool = False,
    debug: bool = False,
    use_yt_dlp_for_podcasts: bool = False,
) -> None:
    """Archive Patreon data you have access to."""  # noqa: DOC501
    setup_logging(
        debug=debug,
        loggers={
            'patreon_archiver': {},
            'urllib3': {},
            'yt_dlp_utils': {},
        },
    )
    if not output_dir:
        output_dir = Path('.', campaign_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    chdir(output_dir)

    if cookies_json is not None:
        session = requests.Session()
        session.mount(
            'https://',
            HTTPAdapter(
                max_retries=Retry(
                    backoff_factor=DEFAULT_RETRY_BACKOFF_FACTOR,
                    status_forcelist=DEFAULT_RETRY_STATUS_FORCELIST,
                )
            ),
        )
        session.headers.update(SHARED_HEADERS)
        cookies_data = json.loads(cookies_json.read_text())
        for cookie in cookies_data:
            session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', '').lstrip('.'),
                path=cookie.get('path', '/'),
            )
    else:
        session = yt_dlp_utils.setup_session(
            browser, profile, domains={'patreon.com', 'www.patreon.com'}, setup_retry=True
        )

    try:
        media_uris = get_all_media_uris(
            campaign_id, session=session, process_podcasts=not use_yt_dlp_for_podcasts
        )
    except requests.exceptions.HTTPError as e:
        log.debug('JSON: %s', e.response.content.decode())
        click.echo(
            'Go to patreon.com and perform the verification, wait 30 seconds and try again.',
            err=True,
        )
        raise click.Abort from e
    ydl = yt_dlp_utils.get_configured_yt_dlp(sleep_time, debug=debug)
    for cookie in session.cookies:
        ydl.cookiejar.set_cookie(cookie)
    for chunk in batched(unique_iter(media_uris), yt_dlp_arg_limit):
        try:
            return_code = ydl.download(chunk)  # type: ignore[func-returns-value]
        except Exception as e:
            if fail:
                log.exception('yt-dlp failed.')
                raise click.Abort from e
        else:
            if return_code != 0 and fail:
                log.error('yt-dlp returned error code %d.', return_code)
                raise click.Abort
