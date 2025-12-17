from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from patreon_archiver.main import main
from requests import HTTPError

if TYPE_CHECKING:
    from click.testing import CliRunner
    from pytest_mock import MockerFixture


def test_main_no_output_dir(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_get_all_media_uris = mocker.patch(
        'patreon_archiver.main.get_all_media_uris', return_value=['uri1', 'uri2']
    )
    mock_get_yt_dlp_downloader = mocker.patch(
        'patreon_archiver.main.yt_dlp_utils.get_configured_yt_dlp'
    )
    mock_ydl = mocker.Mock()
    mock_get_yt_dlp_downloader.return_value = mock_ydl
    mock_ydl.download = mocker.Mock()

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--browser', 'firefox', '--profile', 'TestProfile', '12345'])

    assert result.exit_code == 0
    mock_get_all_media_uris.assert_called_once_with(
        '12345', browser='firefox', profile='TestProfile'
    )
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()


def test_main_with_output_dir(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_get_all_media_uris = mocker.patch(
        'patreon_archiver.main.get_all_media_uris', return_value=['uri1', 'uri2']
    )
    mock_get_yt_dlp_downloader = mocker.patch(
        'patreon_archiver.main.yt_dlp_utils.get_configured_yt_dlp'
    )
    mock_ydl = mocker.Mock()
    mock_get_yt_dlp_downloader.return_value = mock_ydl
    mock_ydl.download = mocker.Mock()

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--output-dir', '/tmp/output', '12345'])  # noqa: S108

    assert result.exit_code == 0
    mock_get_all_media_uris.assert_called_once_with('12345', browser='chrome', profile='Default')
    mock_chdir.assert_called_once_with(Path('/tmp/output'))  # noqa: S108
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()


def test_main_http_error(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_get_all_media_uris = mocker.patch('patreon_archiver.main.get_all_media_uris')
    response = mocker.Mock()
    error = HTTPError('', response=response)
    mock_get_all_media_uris.side_effect = mocker.Mock(side_effect=error)
    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['12345'])

    assert result.exit_code != 0
    mock_get_all_media_uris.assert_called_once_with('12345', browser='chrome', profile='Default')
    mock_chdir.assert_called_once_with(Path('12345'))
    mock_mkdir.assert_called_once()


def test_main_fail_flag(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_get_all_media_uris = mocker.patch(
        'patreon_archiver.main.get_all_media_uris', return_value=['uri1', 'uri2']
    )
    mock_get_yt_dlp_downloader = mocker.patch(
        'patreon_archiver.main.yt_dlp_utils.get_configured_yt_dlp'
    )
    mock_ydl = mocker.Mock()
    mock_get_yt_dlp_downloader.return_value = mock_ydl
    mock_ydl.download = mocker.Mock(side_effect=Exception('DownloadError'))

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['--fail', '12345'])

    assert result.exit_code != 0
    mock_get_all_media_uris.assert_called_once_with('12345', browser='chrome', profile='Default')
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()


def test_main_no_fail_flag(mocker: MockerFixture, runner: CliRunner) -> None:
    mock_get_all_media_uris = mocker.patch(
        'patreon_archiver.main.get_all_media_uris', return_value=['uri1', 'uri2']
    )
    mock_get_yt_dlp_downloader = mocker.patch(
        'patreon_archiver.main.yt_dlp_utils.get_configured_yt_dlp'
    )
    mock_ydl = mocker.Mock()
    mock_get_yt_dlp_downloader.return_value = mock_ydl
    mock_ydl.download = mocker.Mock(side_effect=Exception('DownloadError'))

    mock_chdir = mocker.patch('patreon_archiver.main.chdir')
    mock_mkdir = mocker.patch('pathlib.Path.mkdir')

    result = runner.invoke(main, ['-L', '1', '12345'])

    assert result.exit_code == 0
    mock_get_all_media_uris.assert_called_once_with('12345', browser='chrome', profile='Default')
    mock_chdir.assert_called_once()
    mock_mkdir.assert_called_once()
    mock_ydl.download.assert_called()
