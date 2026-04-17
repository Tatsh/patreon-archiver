"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, Mock
import asyncio
import io
import json
import signal

from niquests.exceptions import HTTPError
from patreon_archiver.main import main
from patreon_archiver.status_display import StatusDisplay
from patreon_archiver.typing import (
    IMAGES_PROCESSED,
    OTHERS_PROCESSED,
    PODCASTS_PROCESSED,
    POSTS_HANDLED,
    YT_DLP_STATUS,
    Stats,
    YTDLPState,
)
from patreon_archiver.workers import WorkerAbort
import click
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from click.testing import CliRunner
    from pytest_mock import MockerFixture


class _LoopRaising:
    def add_signal_handler(self, _signal: int, _handler: object) -> None:
        raise NotImplementedError

    def remove_signal_handler(self, _signal: int) -> None:
        _ = self
        msg = 'remove_signal_handler should not be called.'
        raise AssertionError(msg)


class _LoopCalling:
    def __init__(self) -> None:
        self.removed = False

    def add_signal_handler(self, _signal: int, handler: Callable[[], None]) -> None:
        _ = self
        handler()
        handler()

    def remove_signal_handler(self, _signal: int) -> None:
        self.removed = True


class _LoopStoring:
    def __init__(self) -> None:
        self.handlers: dict[int, Callable[[], None]] = {}
        self.removed = False

    def add_signal_handler(self, signal_: int, handler: Callable[[], None]) -> None:
        self.handlers[signal_] = handler

    def remove_signal_handler(self, _signal: int) -> None:
        self.removed = True


def test_main_no_output_dir(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mock_setup_session = mocker.patch('patreon_archiver.main.setup_session',
                                      new_callable=AsyncMock,
                                      return_value=mock_session)

    mock_run_workers = mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--browser', 'firefox', '--profile', 'TestProfile', '12345'])

    assert result.exit_code == 0
    mock_setup_session.assert_called_once_with('firefox',
                                               'TestProfile',
                                               domains={'patreon.com', 'www.patreon.com'},
                                               setup_retry=True)
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_run_workers.assert_called_once()


def test_main_with_output_dir(mocker: MockerFixture, runner: CliRunner, tmp_path: Path) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mock_setup_session = mocker.patch('patreon_archiver.main.setup_session',
                                      new_callable=AsyncMock,
                                      return_value=mock_session)

    mock_run_workers = mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--output-dir', str(tmp_path), '12345'])

    assert result.exit_code == 0
    mock_setup_session.assert_called_once_with('chrome',
                                               'Default',
                                               domains={'patreon.com', 'www.patreon.com'},
                                               setup_retry=True)
    mock_chdir.assert_called_once_with(tmp_path)
    mock_mkdir.assert_called_once()
    mock_run_workers.assert_called_once()


def test_main_http_error(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)
    response = mocker.Mock()
    error = HTTPError('', response=response)

    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock, side_effect=error)
    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['12345'])

    assert result.exit_code != 0
    mock_chdir.assert_called_once_with(Path('12345'))
    mock_mkdir.assert_called_once()


def test_main_http_error_no_response(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)
    error = HTTPError('', response=None)

    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock, side_effect=error)
    mocker.patch('patreon_archiver.main.chdir')
    mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['12345'])
    assert result.exit_code != 0


def test_main_http_error_null_content(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)
    response = mocker.Mock()
    response.content = None
    error = HTTPError('', response=response)

    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock, side_effect=error)
    mocker.patch('patreon_archiver.main.chdir')
    mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['12345'])
    assert result.exit_code != 0


def test_main_fail_flag(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)

    mock_run_workers = mocker.patch('patreon_archiver.main.run_workers',
                                    new_callable=AsyncMock,
                                    side_effect=click.Abort())
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(side_effect=Exception('DownloadError'))
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--fail', '12345'])

    assert result.exit_code != 0
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_run_workers.assert_called_once()


def test_main_fail_flag_return_code(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)

    mock_run_workers = mocker.patch('patreon_archiver.main.run_workers',
                                    new_callable=AsyncMock,
                                    side_effect=click.Abort())
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=1)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mocker.patch('patreon_archiver.main.chdir')
    mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--fail', '12345'])

    assert result.exit_code != 0
    mock_run_workers.assert_called_once()


def test_main_no_fail_flag(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)

    mock_run_workers = mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(side_effect=Exception('DownloadError'))
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['12345'])

    assert result.exit_code == 0
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_run_workers.assert_called_once()


def test_main_with_cookies_json(mocker: MockerFixture, runner: CliRunner, tmp_path: Path) -> None:
    mock_run_workers = mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    cookies_file = tmp_path / 'cookies.json'
    cookies_data = [{
        'name': 'session_id',
        'value': 'abc123',
        'domain': '.patreon.com',
        'path': '/'
    }, {
        'name': 'auth_token',
        'value': 'xyz789',
        'domain': 'patreon.com'
    }]
    cookies_file.write_text(json.dumps(cookies_data))

    result = runner.invoke(main, ['--cookies-json', str(cookies_file), '12345'])

    assert result.exit_code == 0
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_run_workers.assert_called_once()


def test_main_raises_first_worker_exception(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _run_workers_recording_exception(_campaign_id: str,
                                               first_exception: list[BaseException], *_args: object,
                                               **_kwargs: object) -> None:
        first_exception.append(RuntimeError('worker boom'))
        await asyncio.sleep(0)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_recording_exception)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=_LoopRaising())
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)
    assert str(result.exception) == 'worker boom'


def test_main_handles_missing_signal_support(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=_LoopRaising())
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 0


def test_main_windows_signal_fallback_when_loop_handler_missing(mocker: MockerFixture,
                                                                runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    ydl.download = AsyncMock(return_value=0)
    previous_handler = object()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=_LoopRaising())
    mocker.patch('patreon_archiver.main.sys.platform', 'win32')
    mock_getsignal = mocker.patch('patreon_archiver.main.signal.getsignal',
                                  return_value=previous_handler)
    mock_signal = mocker.patch('patreon_archiver.main.signal.signal')
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 0
    assert any(call.args == (signal.SIGINT,) for call in mock_getsignal.call_args_list)
    assert any(call.args == (signal.SIGTERM,) for call in mock_getsignal.call_args_list)
    assert any(
        call.args == (signal.SIGINT, previous_handler) for call in mock_signal.call_args_list)
    assert any(
        call.args == (signal.SIGTERM, previous_handler) for call in mock_signal.call_args_list)
    assert any(call.args[0] == signal.SIGINT and callable(call.args[1])
               for call in mock_signal.call_args_list)
    windows_handler = next(call.args[1] for call in mock_signal.call_args_list
                           if call.args[0] == signal.SIGINT and callable(call.args[1]))
    assert callable(windows_handler)
    windows_handler(signal.SIGINT, None)


def test_main_windows_signal_fallback_skips_unsupported_signal(mocker: MockerFixture,
                                                               runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=_LoopRaising())
    mocker.patch('patreon_archiver.main.sys.platform', 'win32')
    original_signal = signal.signal

    def _signal_with_unsupported_sigint(sig: int, handler: Any) -> object:
        if (sig == signal.SIGINT and callable(handler)
                and '_windows_signal_handler' in getattr(handler, '__name__', '')):
            msg = 'unsupported'
            raise ValueError(msg)
        return original_signal(sig, handler)

    mocker.patch('patreon_archiver.main.signal.signal', side_effect=_signal_with_unsupported_sigint)
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 0


def test_main_cancelled_without_sigint_re_raises(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _cancel_run_workers(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        raise asyncio.CancelledError

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_cancel_run_workers)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    with pytest.raises(asyncio.CancelledError):
        runner.invoke(main, ['campaign'])


def test_main_sigint_aborts_and_removes_handler(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    display = Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _slow_run_workers(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(10)

    loop = _LoopCalling()
    mocker.patch('patreon_archiver.main.run_workers', side_effect=_slow_run_workers)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.StatusDisplay', return_value=display)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)

    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 1
    assert loop.removed
    messages = [call.args[0] for call in display.write.call_args_list]
    assert messages[0] == ('Termination requested. Finishing the in-flight work. '
                           'Press Ctrl+C (or send SIGTERM) again to force quit.')
    assert 'Force quit requested.' in messages[1]


def test_main_raises_worker_abort_as_click_abort(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _run_workers_recording_abort(_campaign_id: str, first_exception: list[BaseException],
                                           *_args: object, **_kwargs: object) -> None:
        first_exception.append(WorkerAbort())
        await asyncio.sleep(0)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_recording_abort)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=_LoopRaising())
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)


def test_main_quiet_sigint_shows_cleanup_progress(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    loop = _LoopStoring()
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)

    async def _run_workers_and_trigger_cleanup(*_args: object, **kwargs: object) -> None:
        cleanup_callback = cast('Callable[[str], None] | None', kwargs.get('on_cleanup'))
        sigint_handler = loop.handlers.get(signal.SIGINT)
        assert sigint_handler is not None
        assert cleanup_callback is not None
        sigint_handler()
        cleanup_callback('Queued yt-dlp worker shutdown sentinel.')
        await asyncio.sleep(0)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_and_trigger_cleanup)
    result = runner.invoke(main, ['--quiet', 'campaign'])
    assert result.exit_code == 1
    assert ('Termination requested. Finishing the in-flight work. '
            'Press Ctrl+C (or send SIGTERM) again to force quit.') in result.output
    assert 'Queued yt-dlp worker shutdown sentinel.' in result.output
    assert loop.removed


def test_main_quiet_sigterm_shows_cleanup_progress(mocker: MockerFixture,
                                                   runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    loop = _LoopStoring()
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)

    async def _run_workers_and_trigger_cleanup(*_args: object, **kwargs: object) -> None:
        cleanup_callback = cast('Callable[[str], None] | None', kwargs.get('on_cleanup'))
        sigterm_handler = loop.handlers.get(signal.SIGTERM)
        assert sigterm_handler is not None
        assert cleanup_callback is not None
        sigterm_handler()
        cleanup_callback('Queued other worker shutdown sentinel.')
        await asyncio.sleep(0)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_and_trigger_cleanup)
    result = runner.invoke(main, ['--quiet', 'campaign'])
    assert result.exit_code == 1
    assert ('Termination requested. Finishing the in-flight work. '
            'Press Ctrl+C (or send SIGTERM) again to force quit.') in result.output
    assert 'Queued other worker shutdown sentinel.' in result.output
    assert loop.removed


def test_main_sigint_with_active_yt_dlp_uri_warns_to_wait(mocker: MockerFixture,
                                                          runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    display = Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.StatusDisplay', return_value=display)
    loop = _LoopStoring()
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)

    async def _run_workers_touch_uri(*_args: object, **kwargs: object) -> None:
        stats = cast('Stats | None', kwargs.get('stats'))
        idle_event = cast('asyncio.Event | None', kwargs.get('yt_dlp_idle_event'))
        yt_dlp_state = cast('YTDLPState | None', kwargs.get('yt_dlp_state'))
        assert stats is not None
        assert idle_event is not None
        assert yt_dlp_state is not None
        yt_dlp_state.current_uri = 'https://example.com/video/42'
        yt_dlp_state.total_uris = 1
        yt_dlp_state.current_index = 1
        stats[YT_DLP_STATUS] = yt_dlp_state.render()
        idle_event.clear()
        sigint_handler = loop.handlers.get(signal.SIGINT)
        assert sigint_handler is not None
        sigint_handler()
        await asyncio.sleep(0)
        yt_dlp_state.current_uri = None
        stats[YT_DLP_STATUS] = yt_dlp_state.render()
        idle_event.set()
        for _ in range(5):
            await asyncio.sleep(0.01)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_touch_uri)
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 1
    display.write.assert_not_called()
    set_messages = [call.args[0] for call in display.set_message.call_args_list]
    assert ('yt-dlp is still processing a post. Quitting now may corrupt the file. Press '
            'Ctrl+C (or send SIGTERM) again to force quit.') in set_messages
    assert ('Termination requested. Finishing the in-flight work. Press Ctrl+C '
            '(or send SIGTERM) again to force quit.') in set_messages


def test_main_uses_spinner_and_callback_updates(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    display = Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    fake_stderr = Mock()
    fake_stderr.isatty.return_value = True
    mocker.patch('patreon_archiver.main.sys.stderr', fake_stderr)
    mocker.patch('patreon_archiver.main.StatusDisplay', return_value=display)

    async def _run_workers_with_update(*_args: object, **kwargs: object) -> None:
        progress_callback = cast('Callable[[str], None] | None', kwargs.get('on_message'))
        cleanup_callback = cast('Callable[[str], None] | None', kwargs.get('on_cleanup'))
        assert progress_callback is not None
        assert cleanup_callback is not None
        progress_callback('queued')
        cleanup_callback('cleaned')
        await asyncio.sleep(0)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_with_update)
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 0
    display.start.assert_called_once()
    display.stop.assert_called_once()
    display.set_message.assert_any_call('queued')
    display.write.assert_not_called()


def test_main_debug_disables_spinner(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mock_isatty = mocker.patch('patreon_archiver.main.sys.stderr.isatty', return_value=True)
    mock_display = mocker.patch('patreon_archiver.main.StatusDisplay')
    result = runner.invoke(main, ['--debug', 'campaign'])
    assert result.exit_code == 0
    mock_isatty.assert_not_called()
    mock_display.assert_not_called()


def test_main_quiet_disables_spinner(mocker: MockerFixture, runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.run_workers', new_callable=AsyncMock)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mock_isatty = mocker.patch('patreon_archiver.main.sys.stderr.isatty', return_value=True)
    mock_display = mocker.patch('patreon_archiver.main.StatusDisplay')
    result = runner.invoke(main, ['--quiet', 'campaign'])
    assert result.exit_code == 0
    mock_isatty.assert_not_called()
    mock_display.assert_not_called()


def test_status_display_writes_message_and_stats() -> None:
    stats = Stats()
    stats[POSTS_HANDLED] = 9
    stats[IMAGES_PROCESSED] = 1
    stats[OTHERS_PROCESSED] = 2
    stats[PODCASTS_PROCESSED] = 3
    yt_dlp_state = YTDLPState(current_index=2,
                              current_uri='https://example.com/post/42',
                              total_uris=5)
    stats[YT_DLP_STATUS] = yt_dlp_state.render()
    stream = io.StringIO()
    display = StatusDisplay(stats, stream=stream)
    display.start()
    try:
        display.set_message('Working...')
        display.refresh()
        display.write('persistent line')
    finally:
        display.stop()
    output = stream.getvalue()
    assert 'persistent line' in output


def test_status_display_shows_idle_yt_dlp_line() -> None:
    stats = Stats()
    stream = io.StringIO()
    display = StatusDisplay(stats, stream=stream)
    display.start()
    try:
        display.refresh()
    finally:
        display.stop()


def test_main_quiet_sigint_with_active_yt_dlp_echoes_warning(mocker: MockerFixture,
                                                             runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    loop = _LoopStoring()
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)

    async def _run_workers_active_uri(*_args: object, **kwargs: object) -> None:
        idle_event = cast('asyncio.Event | None', kwargs.get('yt_dlp_idle_event'))
        assert idle_event is not None
        idle_event.clear()
        sigint_handler = loop.handlers.get(signal.SIGINT)
        assert sigint_handler is not None
        sigint_handler()
        await asyncio.sleep(0)
        idle_event.set()
        for _ in range(5):
            await asyncio.sleep(0.01)

    mocker.patch('patreon_archiver.main.run_workers', side_effect=_run_workers_active_uri)
    result = runner.invoke(main, ['--quiet', 'campaign'])
    assert result.exit_code == 1
    assert ('yt-dlp is still processing a post. Quitting now may corrupt the file. Press '
            'Ctrl+C (or send SIGTERM) again to force quit.') in result.output
    assert ('Termination requested. Finishing the in-flight work. Press Ctrl+C '
            '(or send SIGTERM) again to force quit.') in result.output


def test_main_warning_task_cancelled_before_idle_fires(mocker: MockerFixture,
                                                       runner: CliRunner) -> None:
    session = AsyncMock()
    session.cookies = []
    ydl = AsyncMock()
    ydl.ydl = mocker.Mock()
    display = Mock()
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.StatusDisplay', return_value=display)
    loop = _LoopStoring()
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)

    async def _run_workers_active_uri_never_idle(*_args: object, **kwargs: object) -> None:
        idle_event = cast('asyncio.Event | None', kwargs.get('yt_dlp_idle_event'))
        assert idle_event is not None
        idle_event.clear()
        sigint_handler = loop.handlers.get(signal.SIGINT)
        assert sigint_handler is not None
        sigint_handler()
        await asyncio.sleep(0)

    mocker.patch('patreon_archiver.main.run_workers',
                 side_effect=_run_workers_active_uri_never_idle)
    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 1
    set_messages = [call.args[0] for call in display.set_message.call_args_list]
    assert ('yt-dlp is still processing a post. Quitting now may corrupt the file. Press '
            'Ctrl+C (or send SIGTERM) again to force quit.') in set_messages
    assert ('Termination requested. Finishing the in-flight work. Press Ctrl+C '
            '(or send SIGTERM) again to force quit.') not in set_messages
    display.stop.assert_called_once()
