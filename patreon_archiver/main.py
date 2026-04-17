"""Entry point."""

from __future__ import annotations

from contextlib import suppress
from os import chdir
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
import asyncio
import json
import logging
import signal
import sys

from anyio import Path as AsyncPath
from bascom import setup_logging
from niquests import AsyncSession
from niquests.exceptions import HTTPError
from urllib3_future.util.retry import Retry
from yt_dlp_utils.aio import get_configured_yt_dlp, setup_session
from yt_dlp_utils.constants import DEFAULT_RETRY_BACKOFF_FACTOR, DEFAULT_RETRY_STATUS_FORCELIST
import click

from .constants import SHARED_HEADERS
from .status_display import STATUS_REFRESH_HZ, StatusDisplay
from .typing import Stats, YTDLPState
from .workers import WorkerAbort, run_workers

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import FrameType

    from niquests.cookies import RequestsCookieJar
    from yt_dlp_utils.aio import AsyncYoutubeDL

    from .typing import OnMessage

__all__ = ('main',)

log = logging.getLogger(__name__)

_TERMINATION_SIGNALS = (signal.SIGINT, signal.SIGTERM)

_GENERIC_SHUTDOWN_MESSAGE = ('Termination requested. Finishing the in-flight work. Press '
                             'Ctrl+C (or send SIGTERM) again to force quit.')
_YT_DLP_ACTIVE_WARNING_MESSAGE = (
    'yt-dlp is still processing a post. Quitting now may corrupt the file. Press Ctrl+C '
    '(or send SIGTERM) again to force quit.')


class _TerminationState:
    """Mutable state shared between signal handlers and ``_async_main``."""
    def __init__(self, yt_dlp_idle_event: asyncio.Event) -> None:
        self.signal_count = 0
        self.warning_task: asyncio.Task[None] | None = None
        self.yt_dlp_idle_event = yt_dlp_idle_event


def _show_status_message(display: StatusDisplay | None, message: str) -> None:
    if display is None:
        click.echo(message, err=True)
        return
    display.write(message)


def _set_transient_message(display: StatusDisplay | None, message: str) -> None:
    if display is None:
        click.echo(message, err=True)
        return
    display.set_message(message)


async def _cancel_task(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def _make_termination_signal_handler(stop_event: asyncio.Event,
                                     run_workers_task: asyncio.Task[None],
                                     display: StatusDisplay | None,
                                     state: _TerminationState) -> Callable[[], None]:
    async def _swap_warning_when_idle() -> None:
        try:
            await state.yt_dlp_idle_event.wait()
        except asyncio.CancelledError:
            return
        _set_transient_message(display, _GENERIC_SHUTDOWN_MESSAGE)

    def _handle_termination_signal() -> None:
        state.signal_count += 1
        if state.signal_count == 1:
            stop_event.set()
            if not state.yt_dlp_idle_event.is_set():
                _set_transient_message(display, _YT_DLP_ACTIVE_WARNING_MESSAGE)
                state.warning_task = asyncio.create_task(_swap_warning_when_idle())
            else:
                _show_status_message(display, _GENERIC_SHUTDOWN_MESSAGE)
            return
        _show_status_message(display, 'Force quit requested. Aborting in-flight work immediately.')
        run_workers_task.cancel()

    return _handle_termination_signal


def _start_status_display(
        stats: Stats,
        stop_event: asyncio.Event) -> tuple[StatusDisplay, OnMessage, asyncio.Task[None]]:
    display = StatusDisplay(stats, stream=sys.stderr)
    display.start()

    def spin_update(message: str) -> None:
        display.set_message(message)

    async def _refresh_display() -> None:
        try:
            while not stop_event.is_set():
                display.refresh()
                await asyncio.sleep(1 / STATUS_REFRESH_HZ)
        except asyncio.CancelledError:
            return

    refresh_task = asyncio.create_task(_refresh_display())
    return display, spin_update, refresh_task


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
                      sleep_time: int, *, fail: bool, debug: bool, quiet: bool,
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
    stats = Stats()
    yt_dlp_state = YTDLPState()
    yt_dlp_idle_event = asyncio.Event()
    yt_dlp_idle_event.set()
    termination_state = _TerminationState(yt_dlp_idle_event)
    display: StatusDisplay | None = None
    on_message: OnMessage | None = None
    refresh_task: asyncio.Task[None] | None = None
    if not debug and not quiet:
        display, on_message, refresh_task = _start_status_display(stats, stop_event)

    def on_cleanup(message: str) -> None:
        if termination_state.signal_count == 0:
            return
        _show_status_message(display, message)

    loop = asyncio.get_running_loop()
    run_workers_task = asyncio.create_task(
        run_workers(campaign_id,
                    first_exception,
                    session,
                    stop_event,
                    fail=fail,
                    on_cleanup=on_cleanup,
                    on_message=on_message,
                    stats=stats,
                    use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts,
                    ydl=ydl,
                    yt_dlp_idle_event=yt_dlp_idle_event,
                    yt_dlp_state=yt_dlp_state))

    handler = _make_termination_signal_handler(stop_event, run_workers_task, display,
                                               termination_state)
    (registered_loop_signals, registered_windows_signal_handlers,
     previous_windows_signal_handlers) = _register_termination_signal_handlers(loop, handler)
    try:
        await run_workers_task
    except asyncio.CancelledError as e:
        if termination_state.signal_count > 0:
            raise click.Abort from e
        raise
    except HTTPError as e:
        if (response := e.response) is not None and (content := response.content) is not None:
            log.debug('JSON: %s', content.decode())
        click.echo('Go to patreon.com, complete the verification, wait 30 seconds, and try again.',
                   err=True)
        raise click.Abort from e
    finally:
        await _cancel_task(termination_state.warning_task)
        await _cancel_task(refresh_task)
        if display is not None:
            display.stop()
        _restore_termination_signal_handlers(loop, registered_loop_signals,
                                             registered_windows_signal_handlers,
                                             previous_windows_signal_handlers)
    if first_exception:
        if isinstance(first_exception[0], WorkerAbort):
            raise click.Abort from first_exception[0]
        raise first_exception[0]
    if termination_state.signal_count > 0:
        raise click.Abort


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
                    sleep_time,
                    fail=fail,
                    debug=debug,
                    quiet=quiet,
                    use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts))
