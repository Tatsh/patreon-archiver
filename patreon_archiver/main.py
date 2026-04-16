"""Entry point."""

from __future__ import annotations

from contextlib import suppress
from os import chdir
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
import asyncio
import json
import logging
import secrets
import signal
import sys

from anyio import Path as AsyncPath
from bascom import setup_logging
from niquests import AsyncSession
from niquests.exceptions import HTTPError
from urllib3_future.util.retry import Retry
from yaspin import yaspin
from yaspin.spinners import Spinners
from yt_dlp_utils.aio import get_configured_yt_dlp, setup_session
from yt_dlp_utils.constants import DEFAULT_RETRY_BACKOFF_FACTOR, DEFAULT_RETRY_STATUS_FORCELIST
import click

from .constants import SHARED_HEADERS
from .workers import WorkerAbort, run_workers

if TYPE_CHECKING:
    from types import FrameType

    from niquests.cookies import RequestsCookieJar
    from yt_dlp_utils.aio import AsyncYoutubeDL

    from .typing import OnMessage

__all__ = ('main',)

log = logging.getLogger(__name__)

_CLI_SPINNERS = (Spinners.arc, Spinners.dots, Spinners.earth, Spinners.hamburger, Spinners.line,
                 Spinners.orangeBluePulse, Spinners.point, Spinners.simpleDotsScrolling,
                 Spinners.soccerHeader, Spinners.weather)
_TERMINATION_SIGNALS = (signal.SIGINT, signal.SIGTERM)


def _random_cli_spinner() -> Any:
    return secrets.choice(_CLI_SPINNERS)


def _spin_update(spinner: Any, message: str) -> None:
    spinner.text = message


def _spin_stop(spinner: Any | None) -> None:
    if spinner is not None:
        spinner.stop()


def _show_status_message(spinner: Any | None, message: str) -> None:
    if spinner is None:
        click.echo(message, err=True)
        return
    spinner.write(message)


def _register_termination_signal_handlers(
        loop: asyncio.AbstractEventLoop, on_signal: Any
) -> tuple[list[signal.Signals], list[signal.Signals], dict[signal.Signals, Any]]:
    registered_loop_signals: list[signal.Signals] = []
    registered_windows_signal_handlers: list[signal.Signals] = []
    previous_windows_signal_handlers: dict[signal.Signals, Any] = {}
    try:
        for handled_signal in _TERMINATION_SIGNALS:
            loop.add_signal_handler(handled_signal, on_signal)
            registered_loop_signals.append(handled_signal)
    except NotImplementedError:
        # Usually Windows.
        for handled_signal in _TERMINATION_SIGNALS:
            previous_handler = _register_windows_signal_handler(handled_signal, on_signal)
            if previous_handler is None:
                continue
            previous_windows_signal_handlers[handled_signal] = previous_handler
            registered_windows_signal_handlers.append(handled_signal)
    return (registered_loop_signals, registered_windows_signal_handlers,
            previous_windows_signal_handlers)


def _register_windows_signal_handler(handled_signal: signal.Signals, on_signal: Any) -> Any | None:
    try:
        previous_handler = signal.getsignal(handled_signal)

        def _windows_signal_handler(_signum: int, _frame: FrameType | None) -> None:
            on_signal()

        signal.signal(handled_signal, _windows_signal_handler)
    except ValueError:
        return None
    else:
        return previous_handler


def _restore_termination_signal_handlers(
        loop: asyncio.AbstractEventLoop, registered_loop_signals: list[signal.Signals],
        registered_windows_signal_handlers: list[signal.Signals],
        previous_windows_signal_handlers: dict[signal.Signals, Any]) -> None:
    for handled_signal in registered_loop_signals:
        loop.remove_signal_handler(handled_signal)
    for handled_signal in registered_windows_signal_handlers:
        with suppress(ValueError):
            signal.signal(handled_signal, previous_windows_signal_handlers[handled_signal])


async def _async_main(browser: str, profile: str, campaign_id: str, cookies_json: Path | None,
                      yt_dlp_arg_limit: int, sleep_time: int, *, fail: bool, debug: bool,
                      quiet: bool, use_yt_dlp_for_podcasts: bool) -> None:
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
    received_termination_signal = False
    stop_event = asyncio.Event()
    spinner: Any | None = None
    on_message: OnMessage | None = None
    if not debug and not quiet:
        spinner = yaspin(_random_cli_spinner(), text='Starting workers...', stream=sys.stderr)
        spinner.start()

        def spin_update(message: str) -> None:
            _spin_update(spinner, message)

        on_message = spin_update

    def on_cleanup(message: str) -> None:
        if not received_termination_signal:
            return
        _show_status_message(spinner, message)

    loop = asyncio.get_running_loop()
    run_workers_task = asyncio.create_task(
        run_workers(campaign_id,
                    first_exception,
                    session,
                    stop_event,
                    fail=fail,
                    on_cleanup=on_cleanup,
                    on_message=on_message,
                    use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts,
                    ydl=ydl,
                    yt_dlp_arg_limit=yt_dlp_arg_limit))

    def _handle_termination_signal() -> None:
        nonlocal received_termination_signal
        if received_termination_signal:
            return
        received_termination_signal = True
        _show_status_message(
            spinner, 'Request to terminate acknowledged. Please wait for clean up to complete...')
        stop_event.set()
        run_workers_task.cancel()

    (registered_loop_signals, registered_windows_signal_handlers,
     previous_windows_signal_handlers) = _register_termination_signal_handlers(
         loop, _handle_termination_signal)
    try:
        await run_workers_task
    except asyncio.CancelledError as e:
        if received_termination_signal:
            raise click.Abort from e
        raise
    except HTTPError as e:
        if (response := e.response) is not None and (content := response.content) is not None:
            log.debug('JSON: %s', content.decode())
        click.echo('Go to patreon.com, complete the verification, wait 30 seconds, and try again.',
                   err=True)
        raise click.Abort from e
    finally:
        _spin_stop(spinner)
        _restore_termination_signal_handlers(loop, registered_loop_signals,
                                             registered_windows_signal_handlers,
                                             previous_windows_signal_handlers)
    if first_exception:
        if isinstance(first_exception[0], WorkerAbort):
            raise click.Abort from first_exception[0]
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
@click.option('-q', '--quiet', is_flag=True, help='Disable progress spinner updates.')
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
         quiet: bool = False,
         use_yt_dlp_for_podcasts: bool = False) -> None:
    """Archive Patreon data you have access to."""
    setup_logging(debug=debug,
                  loggers={
                      'patreon_archiver': {} if debug else {
                          'level': 'WARNING'
                      },
                      'urllib3': {
                          'level': 'WARNING'
                      },
                      'urllib3.util.retry': {
                          'level': 'WARNING'
                      },
                      'yt_dlp_utils': {} if debug else {
                          'level': 'WARNING'
                      }
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
                    quiet=quiet,
                    use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts))
