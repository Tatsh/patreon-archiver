"""Tests for the public worker API."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
import asyncio

from patreon_archiver.typing import (
    IMAGES_PROCESSED,
    OTHERS_PROCESSED,
    PODCASTS_PROCESSED,
    POSTS_HANDLED,
    YT_DLP_STATUS,
    Stats,
    YTDLPState,
)
import patreon_archiver.workers as workers_module
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from patreon_archiver.typing import PostsData
    from pytest_mock import MockerFixture


def _post(url: str, *, id_: str = 'id1', post_type: str = 'audio_embed') -> PostsData:
    return cast('PostsData', {
        'attributes': {
            'post_type': post_type,
            'url': url
        },
        'id': id_,
        'relationships': {}
    })


async def _yield_posts(*posts: PostsData) -> AsyncGenerator[PostsData]:
    await asyncio.sleep(0)
    for post in posts:
        yield post


async def _yield_posts_with_stop(stop_event: asyncio.Event, first: PostsData,
                                 second: PostsData) -> AsyncGenerator[PostsData]:
    await asyncio.sleep(0)
    yield first
    stop_event.set()
    yield second


async def test_producer_routes_dedupes_and_sends_sentinels(mocker: MockerFixture) -> None:
    image_post = _post('image', id_='img', post_type='image_file')
    podcast_post = _post('pod', id_='pod', post_type='podcast')
    other_post = _post('oth', id_='oth', post_type='article')
    mocker.patch('patreon_archiver.workers.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _yield_posts(_post(
                     'uri1'), _post('uri1', id_='dupe'), image_post, podcast_post, other_post))
    yt_queue: asyncio.Queue[str | None] = asyncio.Queue()
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    cleanup_messages: list[str] = []
    messages: list[str] = []
    await workers_module.producer('campaign',
                                  image_queue,
                                  other_queue,
                                  podcast_queue,
                                  AsyncMock(),
                                  asyncio.Event(),
                                  on_cleanup=cleanup_messages.append,
                                  on_message=messages.append,
                                  use_yt_dlp_for_podcasts=False,
                                  yt_dlp_queue=yt_queue)
    assert [yt_queue.get_nowait(), yt_queue.get_nowait()] == ['uri1', None]
    assert [image_queue.get_nowait(), image_queue.get_nowait()] == [image_post, None]
    assert [podcast_queue.get_nowait(), podcast_queue.get_nowait()] == [podcast_post, None]
    assert [other_queue.get_nowait(), other_queue.get_nowait()] == [other_post, None]
    assert messages == [
        'Queued yt-dlp URI from post id1.', 'Queued image post img.', 'Queued podcast post pod.',
        'Queued other post oth.'
    ]
    assert cleanup_messages == [
        'Queued yt-dlp worker shutdown sentinel.', 'Queued image worker shutdown sentinel.',
        'Queued podcast worker shutdown sentinel.', 'Queued other worker shutdown sentinel.'
    ]


async def test_producer_stops_when_stop_event_is_set(mocker: MockerFixture) -> None:
    stop_event = asyncio.Event()
    first_post = _post('uri1')
    second_post = _post('uri2', id_='2')
    mocker.patch('patreon_archiver.workers.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _yield_posts_with_stop(
                     stop_event, first_post, second_post))
    yt_queue: asyncio.Queue[str | None] = asyncio.Queue()
    await workers_module.producer('campaign',
                                  asyncio.Queue(),
                                  asyncio.Queue(),
                                  asyncio.Queue(),
                                  AsyncMock(),
                                  stop_event,
                                  use_yt_dlp_for_podcasts=True,
                                  yt_dlp_queue=yt_queue)
    assert [yt_queue.get_nowait(), yt_queue.get_nowait()] == ['uri1', None]


async def test_producer_routes_without_on_message(mocker: MockerFixture) -> None:
    image_post = _post('image', id_='img', post_type='image_file')
    podcast_post = _post('pod', id_='pod', post_type='podcast')
    other_post = _post('oth', id_='oth', post_type='article')
    mocker.patch('patreon_archiver.workers.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), image_post,
                                                                    podcast_post, other_post))
    yt_queue: asyncio.Queue[str | None] = asyncio.Queue()
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await workers_module.producer('campaign',
                                  image_queue,
                                  other_queue,
                                  podcast_queue,
                                  AsyncMock(),
                                  asyncio.Event(),
                                  use_yt_dlp_for_podcasts=False,
                                  yt_dlp_queue=yt_queue)
    assert [yt_queue.get_nowait(), yt_queue.get_nowait()] == ['uri1', None]
    assert [image_queue.get_nowait(), image_queue.get_nowait()] == [image_post, None]
    assert [podcast_queue.get_nowait(), podcast_queue.get_nowait()] == [podcast_post, None]
    assert [other_queue.get_nowait(), other_queue.get_nowait()] == [other_post, None]


async def test_producer_updates_stats_posts_handled(mocker: MockerFixture) -> None:
    image_post = _post('image', id_='img', post_type='image_file')
    podcast_post = _post('pod', id_='pod', post_type='podcast')
    other_post = _post('oth', id_='oth', post_type='article')
    mocker.patch('patreon_archiver.workers.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), image_post,
                                                                    podcast_post, other_post))
    stats = Stats()
    yt_dlp_state = YTDLPState()
    await workers_module.producer('campaign',
                                  asyncio.Queue(),
                                  asyncio.Queue(),
                                  asyncio.Queue(),
                                  AsyncMock(),
                                  asyncio.Event(),
                                  stats=stats,
                                  use_yt_dlp_for_podcasts=False,
                                  yt_dlp_queue=asyncio.Queue(),
                                  yt_dlp_state=yt_dlp_state)
    assert stats[POSTS_HANDLED] == 4
    assert yt_dlp_state.total_uris == 1


async def test_producer_updates_yt_dlp_state_without_stats(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.workers.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1')))
    yt_dlp_state = YTDLPState()
    await workers_module.producer('campaign',
                                  asyncio.Queue(),
                                  asyncio.Queue(),
                                  asyncio.Queue(),
                                  AsyncMock(),
                                  asyncio.Event(),
                                  use_yt_dlp_for_podcasts=False,
                                  yt_dlp_queue=asyncio.Queue(),
                                  yt_dlp_state=yt_dlp_state)
    assert yt_dlp_state.total_uris == 1


async def test_yt_worker_updates_state_without_stats() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=0)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri-a')
    await queue.put(None)
    yt_dlp_state = YTDLPState(total_uris=1)
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       stop_event=asyncio.Event(),
                                       ydl=ydl,
                                       yt_dlp_queue=queue,
                                       yt_dlp_state=yt_dlp_state)
    assert yt_dlp_state.current_uri is None
    assert yt_dlp_state.current_index == 1


async def test_yt_worker_updates_stats_for_each_uri() -> None:
    observed: list[tuple[str | None, int]] = []

    async def _recording_download(urls: object) -> int:
        await asyncio.sleep(0)
        observed.append((yt_dlp_state.current_uri, yt_dlp_state.current_index))
        _ = urls
        return 0

    ydl = AsyncMock()
    ydl.download = AsyncMock(side_effect=_recording_download)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri-a')
    await queue.put('uri-b')
    await queue.put(None)
    stats = Stats()
    yt_dlp_state = YTDLPState(total_uris=2)
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       stats=stats,
                                       stop_event=asyncio.Event(),
                                       ydl=ydl,
                                       yt_dlp_queue=queue,
                                       yt_dlp_state=yt_dlp_state)
    assert observed == [('uri-a', 1), ('uri-b', 2)]
    assert yt_dlp_state.current_uri is None
    assert yt_dlp_state.current_index == 2
    assert yt_dlp_state.total_uris == 2
    assert stats[YT_DLP_STATUS] is None


async def test_yt_worker_stats_cleared_after_fail() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=1)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri-a')
    await queue.put(None)
    stats = Stats()
    yt_dlp_state = YTDLPState(total_uris=1)
    first_exception: list[BaseException] = []
    await workers_module.yt_dlp_worker(fail=True,
                                       first_exception=first_exception,
                                       stats=stats,
                                       stop_event=asyncio.Event(),
                                       ydl=ydl,
                                       yt_dlp_queue=queue,
                                       yt_dlp_state=yt_dlp_state)
    assert yt_dlp_state.current_uri is None
    assert stats[YT_DLP_STATUS] is None
    assert first_exception


async def test_image_podcast_other_workers_increment_stats(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.workers.save_images', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.save_podcast', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.save_other')
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await image_queue.put(_post('img', id_='img', post_type='image_file'))
    await image_queue.put(None)
    await podcast_queue.put(_post('pod', id_='pod', post_type='podcast'))
    await podcast_queue.put(None)
    await other_queue.put(_post('oth', id_='oth', post_type='article'))
    await other_queue.put(None)
    stats = Stats()
    await workers_module.image_worker(image_queue, [], AsyncMock(), asyncio.Event(), stats=stats)
    await workers_module.podcast_worker([],
                                        podcast_queue,
                                        AsyncMock(),
                                        asyncio.Event(),
                                        stats=stats)
    await workers_module.other_worker([], other_queue, asyncio.Event(), stats=stats)
    assert stats[IMAGES_PROCESSED] == 1
    assert stats[PODCASTS_PROCESSED] == 1
    assert stats[OTHERS_PROCESSED] == 1


async def test_yt_worker_handles_queue_empty_and_sentinel() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=0)
    stop_event = asyncio.Event()
    first_exception: list[BaseException] = []
    messages: list[str] = []
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    worker = asyncio.create_task(
        workers_module.yt_dlp_worker(fail=False,
                                     first_exception=first_exception,
                                     on_message=messages.append,
                                     stop_event=stop_event,
                                     ydl=ydl,
                                     yt_dlp_queue=queue))
    await asyncio.sleep(0)
    await queue.put(None)
    await worker
    ydl.download.assert_awaited_once_with(('uri1',))
    assert not first_exception
    assert messages == ['Downloading uri1 with yt-dlp...']


async def test_workers_exit_when_stop_event_already_set() -> None:
    stop_event = asyncio.Event()
    stop_event.set()
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       stop_event=stop_event,
                                       ydl=AsyncMock(),
                                       yt_dlp_queue=asyncio.Queue())
    await workers_module.image_worker(asyncio.Queue(), [], AsyncMock(), stop_event)
    await workers_module.podcast_worker([], asyncio.Queue(), AsyncMock(), stop_event)
    await workers_module.other_worker([], asyncio.Queue(), stop_event)


async def test_workers_record_exceptions(mocker: MockerFixture) -> None:
    image_error = RuntimeError('image')
    podcast_error = RuntimeError('podcast')
    other_error = RuntimeError('other')
    mocker.patch('patreon_archiver.workers.save_images', side_effect=image_error)
    mocker.patch('patreon_archiver.workers.save_podcast', side_effect=podcast_error)
    mocker.patch('patreon_archiver.workers.save_other', side_effect=other_error)

    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await image_queue.put(_post('image', post_type='image_file'))
    await podcast_queue.put(_post('pod', post_type='podcast'))
    await other_queue.put(_post('oth', post_type='article'))

    image_errors: list[BaseException] = []
    podcast_errors: list[BaseException] = []
    other_errors: list[BaseException] = []
    image_stop = asyncio.Event()
    podcast_stop = asyncio.Event()
    other_stop = asyncio.Event()

    await workers_module.image_worker(image_queue, image_errors, AsyncMock(), image_stop)
    await workers_module.podcast_worker(podcast_errors, podcast_queue, AsyncMock(), podcast_stop)
    await workers_module.other_worker(other_errors, other_queue, other_stop)

    assert image_stop.is_set()
    assert podcast_stop.is_set()
    assert other_stop.is_set()
    assert isinstance(image_errors[0], RuntimeError)
    assert isinstance(podcast_errors[0], RuntimeError)
    assert isinstance(other_errors[0], RuntimeError)


async def test_image_worker_does_not_record_error_when_stop_event_already_set_on_failure(
        mocker: MockerFixture) -> None:
    stop_event = asyncio.Event()
    first_exception: list[BaseException] = []
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await image_queue.put(_post('image', post_type='image_file'))

    async def _raise_after_stop(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        stop_event.set()
        msg = 'ignored once stop is set'
        raise RuntimeError(msg)

    mocker.patch('patreon_archiver.workers.save_images', side_effect=_raise_after_stop)
    await workers_module.image_worker(image_queue, first_exception, AsyncMock(), stop_event)
    assert stop_event.is_set()
    assert not first_exception


async def test_yt_worker_returns_on_sentinel_in_same_batch() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=0)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    await queue.put(None)
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       stop_event=asyncio.Event(),
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    ydl.download.assert_awaited_once_with(('uri1',))


async def test_yt_worker_fail_true_records_abort_on_exception() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(side_effect=RuntimeError('boom'))
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    first_exception: list[BaseException] = []
    messages: list[str] = []
    stop_event = asyncio.Event()
    await workers_module.yt_dlp_worker(fail=True,
                                       first_exception=first_exception,
                                       on_message=messages.append,
                                       stop_event=stop_event,
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    assert stop_event.is_set()
    assert len(first_exception) == 1
    assert isinstance(first_exception[0], workers_module.WorkerAbort)
    assert messages == ['Downloading uri1 with yt-dlp...']


async def test_yt_worker_fail_true_records_abort_on_non_zero_return_code() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=1)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    first_exception: list[BaseException] = []
    stop_event = asyncio.Event()
    await workers_module.yt_dlp_worker(fail=True,
                                       first_exception=first_exception,
                                       stop_event=stop_event,
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    assert stop_event.is_set()
    assert len(first_exception) == 1
    assert isinstance(first_exception[0], workers_module.WorkerAbort)


async def test_yt_worker_non_zero_return_code_reports_message() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=1)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    first_exception: list[BaseException] = []
    messages: list[str] = []
    stop_event = asyncio.Event()
    await workers_module.yt_dlp_worker(fail=True,
                                       first_exception=first_exception,
                                       on_message=messages.append,
                                       stop_event=stop_event,
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    assert messages == ['Downloading uri1 with yt-dlp...']


async def test_yt_worker_exception_with_fail_false_keeps_running_until_sentinel() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(side_effect=RuntimeError('boom'))
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    await queue.put('uri2')
    await queue.put(None)
    first_exception: list[BaseException] = []
    stop_event = asyncio.Event()
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=first_exception,
                                       stop_event=stop_event,
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    assert not stop_event.is_set()
    assert not first_exception


async def test_workers_return_when_queue_gets_sentinel() -> None:
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await image_queue.put(None)
    await podcast_queue.put(None)
    await other_queue.put(None)
    image_cleanup: list[str] = []
    podcast_cleanup: list[str] = []
    other_cleanup: list[str] = []
    await workers_module.image_worker(image_queue, [],
                                      AsyncMock(),
                                      asyncio.Event(),
                                      on_cleanup=image_cleanup.append)
    await workers_module.podcast_worker([],
                                        podcast_queue,
                                        AsyncMock(),
                                        asyncio.Event(),
                                        on_cleanup=podcast_cleanup.append)
    await workers_module.other_worker([],
                                      other_queue,
                                      asyncio.Event(),
                                      on_cleanup=other_cleanup.append)
    assert image_cleanup == ['Image worker exited.']
    assert podcast_cleanup == ['Podcast worker exited.']
    assert other_cleanup == ['Other worker exited.']


async def test_workers_return_when_queue_gets_sentinel_without_cleanup_callback() -> None:
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await image_queue.put(None)
    await podcast_queue.put(None)
    await other_queue.put(None)
    await workers_module.image_worker(image_queue, [], AsyncMock(), asyncio.Event())
    await workers_module.podcast_worker([], podcast_queue, AsyncMock(), asyncio.Event())
    await workers_module.other_worker([], other_queue, asyncio.Event())


async def test_yt_worker_reports_cleanup_on_sentinel() -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put(None)
    cleanup_messages: list[str] = []
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       on_cleanup=cleanup_messages.append,
                                       stop_event=asyncio.Event(),
                                       ydl=AsyncMock(),
                                       yt_dlp_queue=queue)
    assert cleanup_messages == ['yt-dlp worker exited.']


async def test_run_workers_runs_all_tasks(mocker: MockerFixture) -> None:
    mock_producer = mocker.patch('patreon_archiver.workers.producer', new_callable=AsyncMock)
    mock_yt_worker = mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mock_image_worker = mocker.patch('patreon_archiver.workers.image_worker',
                                     new_callable=AsyncMock)
    mock_podcast_worker = mocker.patch('patreon_archiver.workers.podcast_worker',
                                       new_callable=AsyncMock)
    mock_other_worker = mocker.patch('patreon_archiver.workers.other_worker',
                                     new_callable=AsyncMock)
    on_cleanup = mocker.Mock()
    on_message = mocker.Mock()
    await workers_module.run_workers('campaign', [],
                                     AsyncMock(),
                                     asyncio.Event(),
                                     fail=False,
                                     on_cleanup=on_cleanup,
                                     on_message=on_message,
                                     use_yt_dlp_for_podcasts=False,
                                     ydl=AsyncMock())
    mock_producer.assert_awaited_once()
    mock_yt_worker.assert_awaited_once()
    mock_image_worker.assert_awaited_once()
    mock_podcast_worker.assert_awaited_once()
    mock_other_worker.assert_awaited_once()
    assert mock_producer.await_args is not None
    assert mock_yt_worker.await_args is not None
    assert mock_image_worker.await_args is not None
    assert mock_producer.await_args.kwargs['on_message'] is on_message
    assert mock_producer.await_args.kwargs['on_cleanup'] is on_cleanup
    assert mock_yt_worker.await_args.kwargs['on_message'] is on_message
    assert mock_image_worker.await_args.kwargs['on_cleanup'] is on_cleanup


async def test_run_workers_passes_stats_to_workers(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.workers.producer', new_callable=AsyncMock)
    mock_yt_worker = mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mock_image_worker = mocker.patch('patreon_archiver.workers.image_worker',
                                     new_callable=AsyncMock)
    mock_podcast_worker = mocker.patch('patreon_archiver.workers.podcast_worker',
                                       new_callable=AsyncMock)
    mock_other_worker = mocker.patch('patreon_archiver.workers.other_worker',
                                     new_callable=AsyncMock)
    stats = Stats()
    await workers_module.run_workers('campaign', [],
                                     AsyncMock(),
                                     asyncio.Event(),
                                     fail=False,
                                     stats=stats,
                                     use_yt_dlp_for_podcasts=False,
                                     ydl=AsyncMock())
    assert mock_yt_worker.await_args is not None
    assert mock_image_worker.await_args is not None
    assert mock_podcast_worker.await_args is not None
    assert mock_other_worker.await_args is not None
    assert mock_yt_worker.await_args.kwargs['stats'] is stats
    assert mock_image_worker.await_args.kwargs['stats'] is stats
    assert mock_podcast_worker.await_args.kwargs['stats'] is stats
    assert mock_other_worker.await_args.kwargs['stats'] is stats


async def test_run_workers_re_raises_producer_error(mocker: MockerFixture) -> None:
    producer_error = RuntimeError('producer failed')
    mocker.patch('patreon_archiver.workers.producer',
                 new_callable=AsyncMock,
                 side_effect=producer_error)
    mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.image_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.podcast_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.other_worker', new_callable=AsyncMock)
    stop_event = asyncio.Event()
    with pytest.raises(RuntimeError, match='producer failed'):
        await workers_module.run_workers('campaign', [],
                                         AsyncMock(),
                                         stop_event,
                                         fail=False,
                                         use_yt_dlp_for_podcasts=False,
                                         ydl=AsyncMock())
    assert stop_event.is_set()


async def test_run_workers_cleans_up_and_re_raises_cancelled_error(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.workers.producer',
                 new_callable=AsyncMock,
                 side_effect=asyncio.CancelledError())
    mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.image_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.podcast_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.other_worker', new_callable=AsyncMock)
    cleanup_messages: list[str] = []
    stop_event = asyncio.Event()
    with pytest.raises(asyncio.CancelledError):
        await workers_module.run_workers('campaign', [],
                                         AsyncMock(),
                                         stop_event,
                                         fail=False,
                                         on_cleanup=cleanup_messages.append,
                                         use_yt_dlp_for_podcasts=False,
                                         ydl=AsyncMock())
    assert stop_event.is_set()
    assert cleanup_messages == ['Producer cancellation received.', 'All worker tasks cleaned up.']


async def test_run_workers_re_raises_cancelled_error_without_cleanup_callback(
        mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.workers.producer',
                 new_callable=AsyncMock,
                 side_effect=asyncio.CancelledError())
    mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.image_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.podcast_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.other_worker', new_callable=AsyncMock)
    with pytest.raises(asyncio.CancelledError):
        await workers_module.run_workers('campaign', [],
                                         AsyncMock(),
                                         asyncio.Event(),
                                         fail=False,
                                         use_yt_dlp_for_podcasts=False,
                                         ydl=AsyncMock())


async def test_yt_worker_toggles_idle_event_around_download() -> None:
    idle_states: list[bool] = []

    async def _record_idle(urls: object) -> int:
        await asyncio.sleep(0)
        idle_states.append(idle_event.is_set())
        _ = urls
        return 0

    ydl = AsyncMock()
    ydl.download = AsyncMock(side_effect=_record_idle)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri-a')
    await queue.put(None)
    idle_event = asyncio.Event()
    idle_event.clear()
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       idle_event=idle_event,
                                       stop_event=asyncio.Event(),
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    assert idle_states == [False]
    assert idle_event.is_set()


async def test_yt_worker_idle_event_set_after_download_failure() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(side_effect=RuntimeError('boom'))
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri-a')
    await queue.put(None)
    idle_event = asyncio.Event()
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       idle_event=idle_event,
                                       stop_event=asyncio.Event(),
                                       ydl=ydl,
                                       yt_dlp_queue=queue)
    assert idle_event.is_set()


async def test_run_workers_cancel_watcher_cancels_producer_when_stop_event_set(
        mocker: MockerFixture) -> None:
    producer_started = asyncio.Event()

    async def _slow_producer(*_args: object, **_kwargs: object) -> None:
        producer_started.set()
        await asyncio.sleep(10)

    mocker.patch('patreon_archiver.workers.producer', side_effect=_slow_producer)
    mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.image_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.podcast_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.other_worker', new_callable=AsyncMock)
    stop_event = asyncio.Event()
    cleanup_messages: list[str] = []
    run_task = asyncio.create_task(
        workers_module.run_workers('campaign', [],
                                   AsyncMock(),
                                   stop_event,
                                   fail=False,
                                   on_cleanup=cleanup_messages.append,
                                   use_yt_dlp_for_podcasts=False,
                                   ydl=AsyncMock()))
    await producer_started.wait()
    stop_event.set()
    with pytest.raises(asyncio.CancelledError):
        await run_task
    assert 'Producer cancellation received.' in cleanup_messages
    assert 'All worker tasks cleaned up.' in cleanup_messages


async def test_image_podcast_other_workers_succeed_without_stats(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.workers.save_images', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.save_podcast', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.save_other')
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await image_queue.put(_post('img', id_='img', post_type='image_file'))
    await image_queue.put(None)
    await podcast_queue.put(_post('pod', id_='pod', post_type='podcast'))
    await podcast_queue.put(None)
    await other_queue.put(_post('oth', id_='oth', post_type='article'))
    await other_queue.put(None)
    await workers_module.image_worker(image_queue, [], AsyncMock(), asyncio.Event())
    await workers_module.podcast_worker([], podcast_queue, AsyncMock(), asyncio.Event())
    await workers_module.other_worker([], other_queue, asyncio.Event())


async def test_run_workers_cancel_watcher_observes_producer_done(mocker: MockerFixture) -> None:
    stop_event = asyncio.Event()

    async def _producer_sets_stop_and_returns(  # ruff:ignore[unused-async]
            *_args: object, **_kwargs: object) -> None:
        stop_event.set()

    mocker.patch('patreon_archiver.workers.producer', side_effect=_producer_sets_stop_and_returns)
    mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.image_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.podcast_worker', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.workers.other_worker', new_callable=AsyncMock)
    await workers_module.run_workers('campaign', [],
                                     AsyncMock(),
                                     stop_event,
                                     fail=False,
                                     use_yt_dlp_for_podcasts=False,
                                     ydl=AsyncMock())
    assert stop_event.is_set()
