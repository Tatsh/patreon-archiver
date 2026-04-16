"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
import asyncio
import json

from niquests.exceptions import HTTPError
from patreon_archiver.main import main
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

    result = runner.invoke(main, ['-L', '1', '12345'])

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
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=session)

    async def _slow_run_workers(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(10)

    loop = _LoopCalling()
    mocker.patch('patreon_archiver.main.run_workers', side_effect=_slow_run_workers)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=ydl)
    mocker.patch('patreon_archiver.main.asyncio.get_running_loop', return_value=loop)

    result = runner.invoke(main, ['campaign'])
    assert result.exit_code == 1
    assert loop.removed
