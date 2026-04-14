from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
import json

from niquests.exceptions import HTTPError
from patreon_archiver.main import main

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def test_main_no_output_dir(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_session = AsyncMock()
    mock_session.cookies = []
    mock_setup_session = mocker.patch(
        'patreon_archiver.main.setup_session',
        new_callable=AsyncMock,
        return_value=mock_session,
    )

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        raise error
        yield  # type: ignore[unreachable]

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        raise error
        yield  # type: ignore[unreachable]

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        raise error
        yield  # type: ignore[unreachable]

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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

    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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
    async def _mock_uris(*_args: object, **_kwargs: object) -> AsyncGenerator[str]:  # noqa: RUF029
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.main.get_all_media_uris', side_effect=_mock_uris)
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
