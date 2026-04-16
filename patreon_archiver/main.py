"""Entry point."""

from __future__ import annotations

from os import chdir
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast
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

from .constants import MEDIA_POST_TYPES, SHARED_HEADERS
from .utils import get_all_posts, save_images, save_other, save_podcast

if TYPE_CHECKING:
    from niquests.cookies import RequestsCookieJar

    from .typing import PostsData


class _YtDLP(Protocol):
    ydl: Any

    async def download(self, url_list: tuple[str, ...]) -> int:
        """
        Download a batch of URLs.

        Parameters
        ----------
        url_list : tuple[str, ...]
            URLs to download in one invocation.

        Returns
        -------
        int
            Process return code.
        """


__all__ = ('main',)

log = logging.getLogger(__name__)


def _set_first_exception(first_exception: list[BaseException], error: BaseException,
                         stop_event: asyncio.Event) -> None:
    """
    Set the first fatal exception and trigger shutdown.

    Parameters
    ----------
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    error : BaseException
        The exception to store.
    stop_event : asyncio.Event
        Event signalling that the pipeline should stop.
    """
    if not stop_event.is_set():
        first_exception.append(error)
        stop_event.set()


async def _producer(
    campaign_id: str,
    image_queue: asyncio.Queue[PostsData | None],
    other_queue: asyncio.Queue[PostsData | None],
    podcast_queue: asyncio.Queue[PostsData | None],
    session: AsyncSession,
    stop_event: asyncio.Event,
    *,
    use_yt_dlp_for_podcasts: bool,
    yt_dlp_queue: asyncio.Queue[str | None],
) -> None:
    """
    Produce classified work items from Patreon posts.

    Parameters
    ----------
    campaign_id : str
        Campaign ID to fetch posts for.
    image_queue : asyncio.Queue[PostsData | None]
        Queue receiving image posts.
    other_queue : asyncio.Queue[PostsData | None]
        Queue receiving unsupported post types.
    podcast_queue : asyncio.Queue[PostsData | None]
        Queue receiving podcast posts for native processing.
    session : AsyncSession
        Session used to fetch Patreon posts.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    use_yt_dlp_for_podcasts : bool
        If ``True``, route podcast URLs to yt-dlp.
    yt_dlp_queue : asyncio.Queue[str | None]
        Queue receiving media URLs for yt-dlp.
    """
    media_post_types = set(MEDIA_POST_TYPES) | ({'podcast'} if use_yt_dlp_for_podcasts else set())
    seen_uris: set[str] = set()
    try:
        async for post in get_all_posts(campaign_id, session):
            if stop_event.is_set():
                break
            post_type = post['attributes']['post_type']
            match post_type:
                case t if t in media_post_types:
                    uri = post['attributes']['url']
                    if uri in seen_uris:
                        continue
                    seen_uris.add(uri)
                    log.debug('Queuing URI: %s', uri)
                    await yt_dlp_queue.put(uri)
                case 'image_file':
                    await image_queue.put(post)
                case 'podcast':
                    await podcast_queue.put(post)
                case _:
                    await other_queue.put(post)
    finally:
        await yt_dlp_queue.put(None)
        await image_queue.put(None)
        await podcast_queue.put(None)
        await other_queue.put(None)


async def _yt_dlp_worker(
    *,
    fail: bool,
    first_exception: list[BaseException],
    stop_event: asyncio.Event,
    ydl: Any,
    yt_dlp_arg_limit: int,
    yt_dlp_queue: asyncio.Queue[str | None],
) -> None:
    """
    Process yt-dlp URIs one download at a time.

    Parameters
    ----------
    fail : bool
        Whether to stop on the first yt-dlp failure.
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    ydl : object
        Configured yt-dlp wrapper returned by :func:`~yt_dlp_utils.aio.get_configured_yt_dlp`.
    yt_dlp_arg_limit : int
        Maximum number of queued URIs to pass to one yt-dlp invocation.
    yt_dlp_queue : asyncio.Queue[str | None]
        Queue containing yt-dlp URIs.
    """
    typed_ydl = cast('_YtDLP', ydl)
    while not stop_event.is_set():
        uri = await yt_dlp_queue.get()
        batch: list[str] = []
        saw_sentinel = False
        try:
            if uri is None:
                return
            batch.append(uri)
            while len(batch) < yt_dlp_arg_limit:
                try:
                    next_uri = yt_dlp_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if next_uri is None:
                    saw_sentinel = True
                    yt_dlp_queue.task_done()
                    break
                batch.append(next_uri)

            try:
                return_code = await typed_ydl.download(tuple(batch))
            except Exception as error:
                if fail:
                    log.exception('yt-dlp failed.')
                    _set_first_exception(first_exception, click.Abort(), stop_event)
                    log.debug('yt-dlp failure was: %s', error)
            else:
                if return_code != 0 and fail:
                    log.error('yt-dlp returned error code %d.', return_code)
                    _set_first_exception(first_exception, click.Abort(), stop_event)
        finally:
            for _ in batch:
                yt_dlp_queue.task_done()
        if saw_sentinel:
            return


async def _image_worker(image_queue: asyncio.Queue[PostsData | None],
                        first_exception: list[BaseException], session: AsyncSession,
                        stop_event: asyncio.Event) -> None:
    """
    Save image posts sequentially.

    Parameters
    ----------
    image_queue : asyncio.Queue[PostsData | None]
        Queue containing image post payloads.
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    session : AsyncSession
        Session used for image downloads.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    """
    while not stop_event.is_set():
        post = await image_queue.get()
        try:
            if post is None:
                return
            await save_images(session, post)
        except Exception as error:  # noqa: BLE001
            _set_first_exception(first_exception, error, stop_event)
            return
        finally:
            image_queue.task_done()


async def _podcast_worker(first_exception: list[BaseException],
                          podcast_queue: asyncio.Queue[PostsData | None], session: AsyncSession,
                          stop_event: asyncio.Event) -> None:
    """
    Save podcast posts sequentially.

    Parameters
    ----------
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    podcast_queue : asyncio.Queue[PostsData | None]
        Queue containing podcast post payloads.
    session : AsyncSession
        Session used for podcast downloads.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    """
    while not stop_event.is_set():
        post = await podcast_queue.get()
        try:
            if post is None:
                return
            await save_podcast(session, post)
        except Exception as error:  # noqa: BLE001
            _set_first_exception(first_exception, error, stop_event)
            return
        finally:
            podcast_queue.task_done()


async def _other_worker(first_exception: list[BaseException],
                        other_queue: asyncio.Queue[PostsData | None],
                        stop_event: asyncio.Event) -> None:
    """
    Save other post types sequentially.

    Parameters
    ----------
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    other_queue : asyncio.Queue[PostsData | None]
        Queue containing unsupported post payloads.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    """
    while not stop_event.is_set():
        post = await other_queue.get()
        try:
            if post is None:
                return
            save_other(post)
        except Exception as error:  # noqa: BLE001
            _set_first_exception(first_exception, error, stop_event)
            return
        finally:
            other_queue.task_done()


async def _run_workers(campaign_id: str, first_exception: list[BaseException],
                       session: AsyncSession, stop_event: asyncio.Event, *, fail: bool,
                       use_yt_dlp_for_podcasts: bool, ydl: Any, yt_dlp_arg_limit: int) -> None:
    """
    Run producer and workers for all post types.

    Parameters
    ----------
    campaign_id : str
        Campaign ID to fetch posts for.
    fail : bool
        Whether yt-dlp failures should abort processing.
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    session : AsyncSession
        Session used by producer and download workers.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    use_yt_dlp_for_podcasts : bool
        If ``True``, route podcast URLs to yt-dlp instead of the podcast worker.
    ydl : object
        Configured yt-dlp wrapper instance.
    yt_dlp_arg_limit : int
        Maximum number of URIs per yt-dlp invocation.
    """
    yt_dlp_queue: asyncio.Queue[str | None] = asyncio.Queue()
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    worker_tasks = (
        asyncio.create_task(
            _yt_dlp_worker(fail=fail,
                           first_exception=first_exception,
                           stop_event=stop_event,
                           ydl=ydl,
                           yt_dlp_arg_limit=yt_dlp_arg_limit,
                           yt_dlp_queue=yt_dlp_queue)),
        asyncio.create_task(_image_worker(image_queue, first_exception, session, stop_event)),
        asyncio.create_task(_podcast_worker(first_exception, podcast_queue, session, stop_event)),
        asyncio.create_task(_other_worker(first_exception, other_queue, stop_event)),
    )
    producer_error: Exception | None = None
    try:
        await _producer(campaign_id,
                        image_queue,
                        other_queue,
                        podcast_queue,
                        session,
                        stop_event,
                        use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts,
                        yt_dlp_queue=yt_dlp_queue)
    except Exception as error:  # noqa: BLE001
        producer_error = error
        stop_event.set()
    await asyncio.gather(*worker_tasks)
    if producer_error is not None:
        raise producer_error


async def _async_main(browser: str, profile: str, campaign_id: str, cookies_json: Path | None,
                      yt_dlp_arg_limit: int, sleep_time: int, *, fail: bool, debug: bool,
                      use_yt_dlp_for_podcasts: bool) -> None:
    if cookies_json is not None:
        session = AsyncSession(retries=Retry(  # ty: ignore[invalid-argument-type]
            backoff_factor=DEFAULT_RETRY_BACKOFF_FACTOR,
            status_forcelist=set(DEFAULT_RETRY_STATUS_FORCELIST),
        ))
        session.headers.update(SHARED_HEADERS)
        cookies_data = json.loads(await AsyncPath(cookies_json).read_text())
        jar = cast('RequestsCookieJar', session.cookies)
        for cookie in cookies_data:
            jar.set(  # type: ignore[no-untyped-call]  # niquests stubs incomplete
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', '').lstrip('.'),
                path=cookie.get('path', '/'),
            )
    else:
        session = await setup_session(browser,
                                      profile,
                                      domains={'patreon.com', 'www.patreon.com'},
                                      setup_retry=True)
    ydl = get_configured_yt_dlp(sleep_time, debug=debug)
    for cookie in session.cookies:
        ydl.ydl.cookiejar.set_cookie(cookie)
    first_exception: list[BaseException] = []
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    run_workers_task = asyncio.create_task(
        _run_workers(campaign_id,
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
    try:
        loop.add_signal_handler(signal.SIGINT, _handle_sigint)
        registered_sigint_handler = True
    except NotImplementedError:
        pass
    try:
        await run_workers_task
    except asyncio.CancelledError as e:
        if received_sigint:
            raise click.Abort from e
        raise
    except HTTPError as e:
        if (response := e.response) is not None and (content := response.content) is not None:
            log.debug('JSON: %s', content.decode())
        click.echo(
            'Go to patreon.com, complete the verification, wait 30 seconds, and try again.',
            err=True,
        )
        raise click.Abort from e
    finally:
        if registered_sigint_handler:
            loop.remove_signal_handler(signal.SIGINT)
    if first_exception:
        raise first_exception[0]


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
@click.option('-x',
              '--fail',
              is_flag=True,
              help='Do not continue processing after a failed yt-dlp command.')
@click.option(
    '-L',
    '--yt-dlp-arg-limit',
    default=20,
    type=int,
    help='Number of media URIs to pass to yt-dlp at a time.',
)
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
    """Archive Patreon data you have access to."""
    setup_logging(
        debug=debug,
        loggers={
            'patreon_archiver': {},
            'urllib3': {},
            'urllib3.util.retry': {
                'level': 'WARNING'
            },
            'yt_dlp_utils': {},
        },
    )
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
