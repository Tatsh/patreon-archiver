"""Tests for internal main module helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock

# ruff: noqa: SLF001,PLR6301,TRY003,EM101
import asyncio

import click
import patreon_archiver.main as main_module
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from patreon_archiver.typing import PostsData
    from pytest_mock import MockerFixture


def _post(url: str, *, id_: str = 'id1', post_type: str = 'audio_embed') -> PostsData:
    return cast('PostsData', {
        'attributes': {
            'post_type': post_type,
            'url': url,
        },
        'id': id_,
        'relationships': {},
    })


async def _yield_posts(*posts: PostsData) -> AsyncGenerator[PostsData]:
    await asyncio.sleep(0)
    for post in posts:
        yield post


async def _yield_posts_with_stop(
    stop_event: asyncio.Event,
    first: PostsData,
    second: PostsData,
) -> AsyncGenerator[PostsData]:
    await asyncio.sleep(0)
    yield first
    stop_event.set()
    yield second


class _LoopRaising:
    def add_signal_handler(self, _signal: int, _handler: object) -> None:
        raise NotImplementedError

    def remove_signal_handler(self, _signal: int) -> None:
        raise AssertionError('remove_signal_handler should not be called.')


class _LoopCalling:
    def __init__(self) -> None:
        self.removed = False

    def add_signal_handler(self, _signal: int, handler: Callable[[], None]) -> None:
        handler()
        handler()

    def remove_signal_handler(self, _signal: int) -> None:
        self.removed = True


def test_set_first_exception_only_records_once() -> None:
    first_exception: list[BaseException] = []
    stop_event = asyncio.Event()
    main_module._set_first_exception(first_exception, RuntimeError('first'), stop_event)
    main_module._set_first_exception(first_exception, RuntimeError('second'), stop_event)
    assert len(first_exception) == 1
    assert isinstance(first_exception[0], RuntimeError)
    assert str(first_exception[0]) == 'first'


async def test_producer_routes_dedupes_and_sends_sentinels(mocker: MockerFixture) -> None:
    image_post = _post('image', id_='img', post_type='image_file')
    podcast_post = _post('pod', id_='pod', post_type='podcast')
    other_post = _post('oth', id_='oth', post_type='article')
    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(
            _post('uri1'),
            _post('uri1', id_='dupe'),
            image_post,
            podcast_post,
            other_post,
        ),
    )
    yt_queue: asyncio.Queue[str | None] = asyncio.Queue()
    image_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    podcast_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    other_queue: asyncio.Queue[PostsData | None] = asyncio.Queue()
    await main_module._producer(
        'campaign',
        image_queue,
        other_queue,
        podcast_queue,
        AsyncMock(),
        asyncio.Event(),
        use_yt_dlp_for_podcasts=False,
        yt_dlp_queue=yt_queue,
    )
    assert [yt_queue.get_nowait(), yt_queue.get_nowait()] == ['uri1', None]
    assert [image_queue.get_nowait(), image_queue.get_nowait()] == [image_post, None]
    assert [podcast_queue.get_nowait(), podcast_queue.get_nowait()] == [podcast_post, None]
    assert [other_queue.get_nowait(), other_queue.get_nowait()] == [other_post, None]


async def test_producer_stops_when_stop_event_is_set(mocker: MockerFixture) -> None:
    stop_event = asyncio.Event()
    first_post = _post('uri1')
    second_post = _post('uri2', id_='2')
    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts_with_stop(stop_event, first_post,
                                                                     second_post),
    )
    yt_queue: asyncio.Queue[str | None] = asyncio.Queue()
    await main_module._producer(
        'campaign',
        asyncio.Queue(),
        asyncio.Queue(),
        asyncio.Queue(),
        AsyncMock(),
        stop_event,
        use_yt_dlp_for_podcasts=True,
        yt_dlp_queue=yt_queue,
    )
    assert [yt_queue.get_nowait(), yt_queue.get_nowait()] == ['uri1', None]


async def test_yt_worker_handles_queue_empty_and_sentinel() -> None:
    ydl = AsyncMock()
    ydl.download = AsyncMock(return_value=0)
    stop_event = asyncio.Event()
    first_exception: list[BaseException] = []
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    await queue.put('uri1')
    worker = asyncio.create_task(
        main_module._yt_dlp_worker(
            fail=False,
            first_exception=first_exception,
            stop_event=stop_event,
            ydl=ydl,
            yt_dlp_arg_limit=3,
            yt_dlp_queue=queue,
        ))
    await asyncio.sleep(0)
    await queue.put(None)
    await worker
    ydl.download.assert_awaited_once_with(('uri1',))
    assert not first_exception


async def test_workers_exit_when_stop_event_already_set() -> None:
    stop_event = asyncio.Event()
    stop_event.set()
    await main_module._yt_dlp_worker(
        fail=False,
        first_exception=[],
        stop_event=stop_event,
        ydl=AsyncMock(),
        yt_dlp_arg_limit=1,
        yt_dlp_queue=asyncio.Queue(),
    )
    await main_module._image_worker(asyncio.Queue(), [], AsyncMock(), stop_event)
    await main_module._podcast_worker([], asyncio.Queue(), AsyncMock(), stop_event)
    await main_module._other_worker([], asyncio.Queue(), stop_event)


async def test_workers_record_exceptions(mocker: MockerFixture) -> None:
    image_error = RuntimeError('image')
    podcast_error = RuntimeError('podcast')
    other_error = RuntimeError('other')
    mocker.patch('patreon_archiver.main.save_images', side_effect=image_error)
    mocker.patch('patreon_archiver.main.save_podcast', side_effect=podcast_error)
    mocker.patch('patreon_archiver.main.save_other', side_effect=other_error)

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

    await main_module._image_worker(image_queue, image_errors, AsyncMock(), image_stop)
    await main_module._podcast_worker(
        podcast_errors,
        podcast_queue,
        AsyncMock(),
        podcast_stop,
    )
    await main_module._other_worker(other_errors, other_queue, other_stop)

    assert image_stop.is_set()
    assert podcast_stop.is_set()
    assert other_stop.is_set()
    assert isinstance(image_errors[0], RuntimeError)
    assert isinstance(podcast_errors[0], RuntimeError)
    assert isinstance(other_errors[0], RuntimeError)


async def test_async_main_handles_missing_signal_support(mocker: MockerFixture) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(),
    )
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=_LoopRaising())
    await main_module._async_main(
        'chrome',
        'Default',
        'campaign',
        None,
        2,
        1,
        fail=False,
        debug=False,
        use_yt_dlp_for_podcasts=False,
    )


async def test_async_main_cancelled_without_sigint_re_raises(mocker: MockerFixture) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _cancel_posts(*_args: object, **_kwargs: object) -> AsyncGenerator[PostsData]:
        await asyncio.sleep(0)
        raise asyncio.CancelledError
        yield _post('unused')  # type: ignore[unreachable]

    mocker.patch('patreon_archiver.main.get_all_posts', side_effect=_cancel_posts)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    with pytest.raises(asyncio.CancelledError):
        await main_module._async_main(
            'chrome',
            'Default',
            'campaign',
            None,
            2,
            1,
            fail=False,
            debug=False,
            use_yt_dlp_for_podcasts=False,
        )


async def test_async_main_sigint_aborts_and_removes_handler(mocker: MockerFixture) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _slow_posts(*_args: object, **_kwargs: object) -> AsyncGenerator[PostsData]:
        await asyncio.sleep(10)
        yield _post('unused')

    loop = _LoopCalling()
    mocker.patch('patreon_archiver.main.get_all_posts', side_effect=_slow_posts)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)

    with pytest.raises(click.Abort):
        await main_module._async_main(
            'chrome',
            'Default',
            'campaign',
            None,
            2,
            1,
            fail=False,
            debug=False,
            use_yt_dlp_for_podcasts=False,
        )
    assert loop.removed
