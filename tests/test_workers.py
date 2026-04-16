"""Tests for the public worker API."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
import asyncio

import click
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


async def test_yt_worker_handles_queue_empty_and_sentinel() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=0)
    stop_event = asyncio.Event()
    first_exception: list[BaseException] = []
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    worker = asyncio.create_task(
        workers_module.yt_dlp_worker(fail=False,
                                     first_exception=first_exception,
                                     stop_event=stop_event,
                                     ydl=ydl,
                                     yt_dlp_arg_limit=3,
                                     yt_dlp_queue=queue))
    await asyncio.sleep(0)
    await queue.put(None)
    await worker
    ydl.download.assert_awaited_once_with(('uri1',))
    assert not first_exception


async def test_workers_exit_when_stop_event_already_set() -> None:
    stop_event = asyncio.Event()
    stop_event.set()
    await workers_module.yt_dlp_worker(fail=False,
                                       first_exception=[],
                                       stop_event=stop_event,
                                       ydl=AsyncMock(),
                                       yt_dlp_arg_limit=1,
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
                                       yt_dlp_arg_limit=4,
                                       yt_dlp_queue=queue)
    ydl.download.assert_awaited_once_with(('uri1',))


async def test_yt_worker_fail_true_records_abort_on_exception() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(side_effect=RuntimeError('boom'))
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    first_exception: list[BaseException] = []
    stop_event = asyncio.Event()
    await workers_module.yt_dlp_worker(fail=True,
                                       first_exception=first_exception,
                                       stop_event=stop_event,
                                       ydl=ydl,
                                       yt_dlp_arg_limit=1,
                                       yt_dlp_queue=queue)
    assert stop_event.is_set()
    assert len(first_exception) == 1
    assert isinstance(first_exception[0], click.Abort)


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
                                       yt_dlp_arg_limit=1,
                                       yt_dlp_queue=queue)
    assert stop_event.is_set()
    assert len(first_exception) == 1
    assert isinstance(first_exception[0], click.Abort)


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
                                       yt_dlp_arg_limit=4,
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
    await workers_module.image_worker(image_queue, [], AsyncMock(), asyncio.Event())
    await workers_module.podcast_worker([], podcast_queue, AsyncMock(), asyncio.Event())
    await workers_module.other_worker([], other_queue, asyncio.Event())


async def test_run_workers_runs_all_tasks(mocker: MockerFixture) -> None:
    mock_producer = mocker.patch('patreon_archiver.workers.producer', new_callable=AsyncMock)
    mock_yt_worker = mocker.patch('patreon_archiver.workers.yt_dlp_worker', new_callable=AsyncMock)
    mock_image_worker = mocker.patch('patreon_archiver.workers.image_worker',
                                     new_callable=AsyncMock)
    mock_podcast_worker = mocker.patch('patreon_archiver.workers.podcast_worker',
                                       new_callable=AsyncMock)
    mock_other_worker = mocker.patch('patreon_archiver.workers.other_worker',
                                     new_callable=AsyncMock)
    await workers_module.run_workers('campaign', [],
                                     AsyncMock(),
                                     asyncio.Event(),
                                     fail=False,
                                     use_yt_dlp_for_podcasts=False,
                                     ydl=AsyncMock(),
                                     yt_dlp_arg_limit=2)
    mock_producer.assert_awaited_once()
    mock_yt_worker.assert_awaited_once()
    mock_image_worker.assert_awaited_once()
    mock_podcast_worker.assert_awaited_once()
    mock_other_worker.assert_awaited_once()


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
                                         ydl=AsyncMock(),
                                         yt_dlp_arg_limit=2)
    assert stop_event.is_set()
