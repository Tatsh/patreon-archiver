"""Worker orchestration for asynchronous post processing."""

from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio
import logging

from .constants import MEDIA_POST_TYPES
from .utils import get_all_posts, save_images, save_other, save_podcast

if TYPE_CHECKING:
    from niquests import AsyncSession
    from yt_dlp_utils.aio import AsyncYoutubeDL

    from .typing import OnMessage, PostsData

__all__ = ('WorkerAbort', 'image_worker', 'other_worker', 'podcast_worker', 'producer',
           'run_workers', 'yt_dlp_worker')

log = logging.getLogger(__name__)


class WorkerAbort(Exception):
    """Worker-level abort signal for graceful CLI handling."""


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


async def producer(campaign_id: str,
                   image_queue: asyncio.Queue[PostsData | None],
                   other_queue: asyncio.Queue[PostsData | None],
                   podcast_queue: asyncio.Queue[PostsData | None],
                   session: AsyncSession,
                   stop_event: asyncio.Event,
                   *,
                   on_cleanup: OnMessage | None = None,
                   on_message: OnMessage | None = None,
                   use_yt_dlp_for_podcasts: bool,
                   yt_dlp_queue: asyncio.Queue[str | None]) -> None:
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
    on_cleanup : OnMessage | None
        Optional callback that receives cleanup status updates.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.
    use_yt_dlp_for_podcasts : bool
        If ``True``, route podcast URLs to yt-dlp.
    yt_dlp_queue : asyncio.Queue[str | None]
        Queue receiving media URLs for yt-dlp.
    """
    media_post_types = set(MEDIA_POST_TYPES) | ({'podcast'} if use_yt_dlp_for_podcasts else set())
    seen_uris: set[str] = set()
    try:
        async for post in get_all_posts(campaign_id, session, on_message=on_message):
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
                    if on_message is not None:
                        on_message(f'Queued yt-dlp URI from post {post["id"]}.')
                case 'image_file':
                    await image_queue.put(post)
                    if on_message is not None:
                        on_message(f'Queued image post {post["id"]}.')
                case 'podcast':
                    await podcast_queue.put(post)
                    if on_message is not None:
                        on_message(f'Queued podcast post {post["id"]}.')
                case _:
                    await other_queue.put(post)
                    if on_message is not None:
                        on_message(f'Queued other post {post["id"]}.')
    finally:
        await yt_dlp_queue.put(None)
        if on_cleanup is not None:
            on_cleanup('Queued yt-dlp worker shutdown sentinel.')
        await image_queue.put(None)
        if on_cleanup is not None:
            on_cleanup('Queued image worker shutdown sentinel.')
        await podcast_queue.put(None)
        if on_cleanup is not None:
            on_cleanup('Queued podcast worker shutdown sentinel.')
        await other_queue.put(None)
        if on_cleanup is not None:
            on_cleanup('Queued other worker shutdown sentinel.')


async def yt_dlp_worker(*,
                        fail: bool,
                        first_exception: list[BaseException],
                        on_cleanup: OnMessage | None = None,
                        on_message: OnMessage | None = None,
                        stop_event: asyncio.Event,
                        ydl: AsyncYoutubeDL,
                        yt_dlp_arg_limit: int,
                        yt_dlp_queue: asyncio.Queue[str | None]) -> None:
    """
    Process yt-dlp URIs one download at a time.

    Parameters
    ----------
    fail : bool
        Whether to stop on the first yt-dlp failure.
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    on_cleanup : OnMessage | None
        Optional callback that receives cleanup status updates.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    ydl : AsyncYoutubeDL
        Configured yt-dlp wrapper returned by :func:`~yt_dlp_utils.aio.get_configured_yt_dlp`.
    yt_dlp_arg_limit : int
        Maximum number of queued URIs to pass to one yt-dlp invocation.
    yt_dlp_queue : asyncio.Queue[str | None]
        Queue containing URIs for yt-dlp to handle.
    """
    while not stop_event.is_set():
        uri = await yt_dlp_queue.get()
        batch: list[str] = []
        saw_sentinel = False
        try:
            if uri is None:
                if on_cleanup is not None:
                    on_cleanup('yt-dlp worker exited.')
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
                if on_message is not None:
                    on_message(f'Downloading {len(batch)} URI(s) with yt-dlp...')
                return_code = await ydl.download(tuple(batch))
            except Exception:
                if fail:
                    _set_first_exception(first_exception, WorkerAbort(), stop_event)
                    log.exception('yt-dlp failure.')
            else:
                if return_code != 0 and fail:
                    log.error('yt-dlp returned error code %d.', return_code)
                    _set_first_exception(first_exception, WorkerAbort(), stop_event)
        finally:
            for _ in batch:
                yt_dlp_queue.task_done()
        if saw_sentinel:
            return


async def image_worker(image_queue: asyncio.Queue[PostsData | None],
                       first_exception: list[BaseException],
                       session: AsyncSession,
                       stop_event: asyncio.Event,
                       *,
                       on_cleanup: OnMessage | None = None,
                       on_message: OnMessage | None = None) -> None:
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
    on_cleanup : OnMessage | None
        Optional callback that receives cleanup status updates.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.
    """
    while not stop_event.is_set():
        post = await image_queue.get()
        try:
            if post is None:
                if on_cleanup is not None:
                    on_cleanup('Image worker exited.')
                return
            await save_images(session, post, on_message=on_message)
        except Exception as error:  # noqa: BLE001
            _set_first_exception(first_exception, error, stop_event)
            return
        finally:
            image_queue.task_done()


async def podcast_worker(first_exception: list[BaseException],
                         podcast_queue: asyncio.Queue[PostsData | None],
                         session: AsyncSession,
                         stop_event: asyncio.Event,
                         *,
                         on_cleanup: OnMessage | None = None,
                         on_message: OnMessage | None = None) -> None:
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
    on_cleanup : OnMessage | None
        Optional callback that receives cleanup status updates.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.
    """
    while not stop_event.is_set():
        post = await podcast_queue.get()
        try:
            if post is None:
                if on_cleanup is not None:
                    on_cleanup('Podcast worker exited.')
                return
            await save_podcast(session, post, on_message=on_message)
        except Exception as error:  # noqa: BLE001
            _set_first_exception(first_exception, error, stop_event)
            return
        finally:
            podcast_queue.task_done()


async def other_worker(first_exception: list[BaseException],
                       other_queue: asyncio.Queue[PostsData | None],
                       stop_event: asyncio.Event,
                       *,
                       on_cleanup: OnMessage | None = None,
                       on_message: OnMessage | None = None) -> None:
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
    on_cleanup : OnMessage | None
        Optional callback that receives cleanup status updates.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.
    """
    while not stop_event.is_set():
        post = await other_queue.get()
        try:
            if post is None:
                if on_cleanup is not None:
                    on_cleanup('Other worker exited.')
                return
            save_other(post, on_message=on_message)
        except Exception as error:  # noqa: BLE001
            _set_first_exception(first_exception, error, stop_event)
            return
        finally:
            other_queue.task_done()


async def run_workers(campaign_id: str,
                      first_exception: list[BaseException],
                      session: AsyncSession,
                      stop_event: asyncio.Event,
                      *,
                      fail: bool,
                      on_cleanup: OnMessage | None = None,
                      on_message: OnMessage | None = None,
                      use_yt_dlp_for_podcasts: bool,
                      ydl: AsyncYoutubeDL,
                      yt_dlp_arg_limit: int) -> None:
    """
    Run producer and workers for all post types.

    Parameters
    ----------
    campaign_id : str
        Campaign ID to fetch posts for.
    first_exception : list[BaseException]
        Mutable container for the first observed fatal exception.
    session : AsyncSession
        Session used by producer and download workers.
    stop_event : asyncio.Event
        Event indicating that workers should stop.
    fail : bool
        Whether yt-dlp failures should abort processing.
    on_cleanup : OnMessage | None
        Optional callback that receives cleanup status updates.
    on_message : OnMessage | None
        Optional callback that receives progress text updates.
    use_yt_dlp_for_podcasts : bool
        If ``True``, route podcast URLs to yt-dlp instead of the podcast worker.
    ydl : AsyncYoutubeDL
        Configured yt-dlp wrapper instance.
    yt_dlp_arg_limit : int
        Maximum number of URIs per yt-dlp invocation.
    """
    yt_dlp_queue: asyncio.Queue[str | None] = asyncio.Queue()
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    worker_tasks = (asyncio.create_task(
        yt_dlp_worker(fail=fail,
                      first_exception=first_exception,
                      on_cleanup=on_cleanup,
                      on_message=on_message,
                      stop_event=stop_event,
                      ydl=ydl,
                      yt_dlp_arg_limit=yt_dlp_arg_limit,
                      yt_dlp_queue=yt_dlp_queue)),
                    asyncio.create_task(
                        image_worker(image_queue,
                                     first_exception,
                                     session,
                                     stop_event,
                                     on_cleanup=on_cleanup,
                                     on_message=on_message)),
                    asyncio.create_task(
                        podcast_worker(first_exception,
                                       podcast_queue,
                                       session,
                                       stop_event,
                                       on_cleanup=on_cleanup,
                                       on_message=on_message)),
                    asyncio.create_task(
                        other_worker(first_exception,
                                     other_queue,
                                     stop_event,
                                     on_cleanup=on_cleanup,
                                     on_message=on_message)))
    cancelled_error: asyncio.CancelledError | None = None
    producer_error: Exception | None = None
    try:
        await producer(campaign_id,
                       image_queue,
                       other_queue,
                       podcast_queue,
                       session,
                       stop_event,
                       on_cleanup=on_cleanup,
                       on_message=on_message,
                       use_yt_dlp_for_podcasts=use_yt_dlp_for_podcasts,
                       yt_dlp_queue=yt_dlp_queue)
    except asyncio.CancelledError as error:
        cancelled_error = error
        stop_event.set()
        if on_cleanup is not None:
            on_cleanup('Producer cancellation received.')
    except Exception as error:  # noqa: BLE001
        producer_error = error
        stop_event.set()
    await asyncio.shield(asyncio.gather(*worker_tasks, return_exceptions=True))
    if on_cleanup is not None:
        on_cleanup('All worker tasks cleaned up.')
    if cancelled_error is not None:
        raise cancelled_error
    if producer_error is not None:
        raise producer_error
