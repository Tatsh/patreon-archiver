"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
import asyncio
import json

from niquests.exceptions import HTTPError
from patreon_archiver.main import main

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def _post(url: str, *, id_: str = 'id1', post_type: str = 'audio_embed') -> dict[str, object]:
    return {
        'attributes': {
            'post_type': post_type,
            'url': url,
        },
        'id': id_,
        'relationships': {},
    }


async def _yield_posts(*posts: dict[str, object]) -> AsyncGenerator[dict[str, object]]:
    await asyncio.sleep(0)
    for post in posts:
        yield post


async def _raise_http_error(error: HTTPError) -> AsyncGenerator[dict[str, object]]:
    await asyncio.sleep(0)
    raise error
    yield _post('unused')  # type: ignore[unreachable]


def test_main_no_output_dir(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mock_setup_session = mocker.patch(
        'patreon_archiver.main.setup_session',
        new_callable=AsyncMock,
        return_value=mock_session,
    )

    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), _post('uri2', id_='id2')),
    )
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--browser', 'firefox', '--profile', 'TestProfile', '12345'])

    assert result.exit_code == 0
    mock_setup_session.assert_called_once_with(
        'firefox',
        'TestProfile',
        domains={'patreon.com', 'www.patreon.com'},
        setup_retry=True,
    )
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()


def test_main_with_output_dir(mocker: MockerFixture, runner: CliRunner, tmp_path: Path) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mock_setup_session = mocker.patch(
        'patreon_archiver.main.setup_session',
        new_callable=AsyncMock,
        return_value=mock_session,
    )

    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), _post('uri2', id_='id2')),
    )
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--output-dir', str(tmp_path), '12345'])

    assert result.exit_code == 0
    mock_setup_session.assert_called_once_with(
        'chrome',
        'Default',
        domains={'patreon.com', 'www.patreon.com'},
        setup_retry=True,
    )
    mock_chdir.assert_called_once_with(tmp_path)
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()


def test_main_http_error(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)
    response = mocker.Mock()
    error = HTTPError('', response=response)

    mocker.patch('patreon_archiver.main.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _raise_http_error(error))
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

    mocker.patch('patreon_archiver.main.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _raise_http_error(error))
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

    mocker.patch('patreon_archiver.main.get_all_posts',
                 side_effect=lambda *_args, **_kwargs: _raise_http_error(error))
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

    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), _post('uri2', id_='id2')),
    )
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
    mock_ydl.download.assert_called()


def test_main_fail_flag_return_code(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)

    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), _post('uri2', id_='id2')),
    )
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=1)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mocker.patch('patreon_archiver.main.chdir')
    mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--fail', '12345'])

    assert result.exit_code != 0
    mock_ydl.download.assert_called()


def test_main_no_fail_flag(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mocker.patch('patreon_archiver.main.setup_session',
                 new_callable=AsyncMock,
                 return_value=mock_session)

    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), _post('uri2', id_='id2')),
    )
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
    mock_ydl.download.assert_called()


def test_main_with_cookies_json(mocker: MockerFixture, runner: CliRunner, tmp_path: Path) -> None:
    mocker.patch(
        'patreon_archiver.main.get_all_posts',
        side_effect=lambda *_args, **_kwargs: _yield_posts(_post('uri1'), _post('uri2', id_='id2')),
    )
    mock_ydl = AsyncMock()
    mock_ydl.ydl = mocker.Mock()
    mock_ydl.download = AsyncMock(return_value=0)
    mocker.patch('patreon_archiver.main.get_configured_yt_dlp', return_value=mock_ydl)

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    cookies_file = tmp_path / 'cookies.json'
    cookies_data = [
        {
            'name': 'session_id',
            'value': 'abc123',
            'domain': '.patreon.com',
            'path': '/'
        },
        {
            'name': 'auth_token',
            'value': 'xyz789',
            'domain': 'patreon.com'
        },
    ]
    cookies_file.write_text(json.dumps(cookies_data))

    result = runner.invoke(main, ['--cookies-json', str(cookies_file), '12345'])

    assert result.exit_code == 0
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()
