"""Entry point."""

from __future__ import annotations

from contextlib import suppress
from os import chdir
from pathlib import Path
from typing import TYPE_CHECKING, cast
import asyncio
import json
import logging
import signal

from anyio import Path as AsyncPath
from bascom import setup_logging
from niquests import AsyncSession
from niquests.exceptions import HTTPError
from urllib3_future.util.retry import Retry
from yt_dlp_utils.aio import get_configured_yt_dlp, setup_session
from yt_dlp_utils.constants import DEFAULT_RETRY_BACKOFF_FACTOR, DEFAULT_RETRY_STATUS_FORCELIST
import click

from .constants import SHARED_HEADERS
from .workers import run_workers

if TYPE_CHECKING:
    from niquests.cookies import RequestsCookieJar
    from yt_dlp_utils.aio import AsyncYoutubeDL

__all__ = ('main',)

log = logging.getLogger(__name__)


async def _async_main(browser: str, profile: str, campaign_id: str, cookies_json: Path | None,
                      yt_dlp_arg_limit: int, sleep_time: int, *, fail: bool, debug: bool,
                      use_yt_dlp_for_podcasts: bool) -> None:
    if cookies_json is not None:
        session = AsyncSession(retries=Retry(  # ty: ignore[invalid-argument-type]
            backoff_factor=DEFAULT_RETRY_BACKOFF_FACTOR,
            status_forcelist=set(DEFAULT_RETRY_STATUS_FORCELIST)))
        session.headers.update(SHARED_HEADERS)
        cookies_data = json.loads(await AsyncPath(cookies_json).read_text())
        jar = cast('RequestsCookieJar', session.cookies)
        for cookie in cookies_data:
            jar.set(  # type: ignore[no-untyped-call]  # niquests stubs incomplete
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', '').lstrip('.'),
                path=cookie.get('path', '/'))
    else:
        session = await setup_session(browser,
                                      profile,
                                      domains={'patreon.com', 'www.patreon.com'},
                                      setup_retry=True)
    ydl: AsyncYoutubeDL = get_configured_yt_dlp(sleep_time, debug=debug)
    for cookie in session.cookies:
        ydl.ydl.cookiejar.set_cookie(cookie)
    first_exception: list[BaseException] = []
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    run_workers_task = asyncio.create_task(
        run_workers(campaign_id,
                    first_exception,
                    session,
                    stop_event,
                    fail=fail,
                    use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts,
                    ydl=ydl,
                    yt_dlp_arg_limit=yt_dlp_arg_limit))
    received_sigint = False

    def _handle_sigint() -> None:
        nonlocal received_sigint
        if received_sigint:
            return
        received_sigint = True
        stop_event.set()
        run_workers_task.cancel()

    registered_sigint_handler = False
    with suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGINT, _handle_sigint)
        registered_sigint_handler = True
    try:
        await run_workers_task
    except asyncio.CancelledError as e:
        if received_sigint:
            raise click.Abort from e
        raise
    except HTTPError as e:
        if (response := e.response) is not None and (content := response.content) is not None:
            log.debug('JSON: %s', content.decode())
        click.echo('Go to patreon.com, complete the verification, wait 30 seconds, and try again.',
                   err=True)
        raise click.Abort from e
    finally:
        if registered_sigint_handler:
            loop.remove_signal_handler(signal.SIGINT)
    if first_exception:
        raise first_exception[0]


@click.command()
@click.option('-o',
              '--output-dir',
              default=None,
              help='Output directory.',
              type=click.Path(file_okay=False, writable=True, resolve_path=True, path_type=Path))
@click.option('-b', '--browser', default='chrome', help='Browser to read cookies from.')
@click.option('-p', '--profile', default='Default', help='Browser profile.')
@click.option('-c',
              '--cookies-json',
              default=None,
              type=click.Path(exists=True, dir_okay=False, resolve_path=True, path_type=Path),
              help='Path to JSON file containing cookies (overrides --browser/--profile).')
@click.option('-x',
              '--fail',
              is_flag=True,
              help='Do not continue processing after a failed yt-dlp command.')
@click.option('-L',
              '--yt-dlp-arg-limit',
              default=20,
              type=int,
              help='Number of media URIs to pass to yt-dlp at a time.')
@click.option('-P',
              '--use-yt-dlp-for-podcasts',
              is_flag=True,
              help='Use yt-dlp to download podcasts.')
@click.option('-S',
              '--sleep-time',
              default=1,
              type=int,
              help='Number of seconds to wait between requests.')
@click.option('-d', '--debug', is_flag=True, help='Enable debug output.')
@click.argument('campaign_id')
def main(browser: str,
         profile: str,
         campaign_id: str,
         output_dir: Path | None = None,
         cookies_json: Path | None = None,
         yt_dlp_arg_limit: int = 20,
         sleep_time: int = 1,
         *,
         fail: bool = False,
         debug: bool = False,
         use_yt_dlp_for_podcasts: bool = False) -> None:
    """Archive Patreon data you have access to."""
    setup_logging(debug=debug,
                  loggers={
                      'patreon_archiver': {},
                      'urllib3': {},
                      'urllib3.util.retry': {
                          'level': 'WARNING'
                      },
                      'yt_dlp_utils': {}
                  })
    if output_dir is None:
        output_dir = Path('.', campaign_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    chdir(output_dir)
    asyncio.run(
        _async_main(browser,
                    profile,
                    campaign_id,
                    cookies_json,
                    yt_dlp_arg_limit,
                    sleep_time,
                    fail=fail,
                    debug=debug,
                    use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts))
