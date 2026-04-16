"""Tests for utility helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock, Mock

from patreon_archiver.utils import (
    UnknownMimetypeError,
    get_all_posts,
    save_images,
    save_other,
    save_podcast,
)
import pytest

if TYPE_CHECKING:
    from patreon_archiver.typing import PostsData
    from pytest_mock import MockerFixture


def _image_post(*, id_: str = '123', image_order: list[str] | None = None) -> PostsData:
    return cast(
        'PostsData', {
            'attributes': {
                'url': 'http://example.com',
                'post_type': 'image_file',
                'post_metadata': None if image_order is None else {
                    'image_order': image_order
                },
                'post_file': {
                    'name': '',
                    'url': 'http://example.com'
                }
            },
            'id': id_,
            'relationships': {}
        })


def _podcast_post(*, id_: str = '456', media_id: str = 'media1') -> PostsData:
    return cast(
        'PostsData', {
            'attributes': {
                'post_type': 'podcast',
                'url': 'http://example.com/podcast'
            },
            'id': id_,
            'relationships': {
                'media': {
                    'data': [{
                        'id': media_id,
                        'type': 'media'
                    }]
                }
            }
        })


async def test_save_images_writes_post_and_images(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media1 = AsyncMock()
    media1.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image1.com'
                    },
                    'mimetype': 'image/jpeg'
                },
                'id': 'id1'
            }
        })
    media2 = AsyncMock()
    media2.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image2.com'
                    },
                    'mimetype': 'image/png'
                },
                'id': 'id2'
            }
        })
    image_response = AsyncMock()
    image_response.content = b'image content'
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media1, image_response, media2, image_response])

    await save_images(session, _image_post(image_order=['id1', 'id2']))
    assert mock_write_bytes.call_count == 2


async def test_save_images_covers_webp_and_gif(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media1 = AsyncMock()
    media1.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image1.com'
                    },
                    'mimetype': 'image/webp'
                },
                'id': 'id1'
            }
        })
    media2 = AsyncMock()
    media2.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image2.com'
                    },
                    'mimetype': 'image/gif'
                },
                'id': 'id2'
            }
        })
    image_response = AsyncMock()
    image_response.content = b'image content'
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media1, image_response, media2, image_response])

    await save_images(session, _image_post(image_order=['id1', 'id2']))
    assert mock_write_bytes.call_count == 2


async def test_save_images_skips_null_content(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image1.com'
                    },
                    'mimetype': 'image/jpeg'
                },
                'id': 'id1'
            }
        })
    image_response = AsyncMock()
    image_response.content = None
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, image_response])

    await save_images(session, _image_post(id_='124', image_order=['id1']))
    mock_write_text.assert_called_once()
    mock_write_bytes.assert_not_called()


async def test_save_images_without_metadata(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)
    session = AsyncMock()

    await save_images(session, _image_post(image_order=None))
    mock_write_text.assert_called_once()
    session.get.assert_not_called()


async def test_save_images_raises_for_unknown_mimetype(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image1.com'
                    },
                    'mimetype': 'application/json'
                },
                'id': 'id1'
            }
        })
    image_response = AsyncMock()
    image_response.content = b'image content'
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, image_response])

    with pytest.raises(UnknownMimetypeError, match='application/json'):
        await save_images(session, _image_post(image_order=['id1']))


def test_save_other_writes_json(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.mkdir')
    save_other(
        cast(
            'PostsData', {
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'http://example.com'
                },
                'id': '123',
                'relationships': {}
            }))
    mock_write_text.assert_called_once()


def test_save_other_skips_existing_file(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=True)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.mkdir')
    save_other(
        cast(
            'PostsData', {
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'http://example.com'
                },
                'id': '123',
                'relationships': {}
            }))
    mock_write_text.assert_not_called()


async def test_save_podcast_audio_download(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': '/absolute/path/to/episode.mp3',
                    'mimetype': None
                },
                'id': 'media1'
            }
        })
    audio_response = AsyncMock()
    audio_response.content = b'audio'
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, audio_response])

    result = await save_podcast(session, _podcast_post(id_='456'))
    assert result['target_dir'] == Path('.', 'podcasts', '456')
    assert mock_write_text.call_count == 1
    assert mock_write_bytes.call_count == 1


async def test_save_podcast_audio_null_content(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': 'episode.mp3',
                    'mimetype': None
                },
                'id': 'media1'
            }
        })
    audio_response = AsyncMock()
    audio_response.content = None
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, audio_response])

    await save_podcast(session, _podcast_post(id_='222'))
    assert mock_write_text.call_count == 1
    mock_write_bytes.assert_not_called()


async def test_save_podcast_audio_non_binary_content_is_ignored(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': 'episode.mp3',
                    'mimetype': None
                },
                'id': 'media1'
            }
        })
    audio_response = AsyncMock()
    audio_response.content = 123
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, audio_response])

    await save_podcast(session, _podcast_post(id_='223'))
    assert mock_write_text.call_count == 1
    mock_write_bytes.assert_not_called()


async def test_save_podcast_image_fallback(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': {
                        'original': 'http://example.com/cover.jpg'
                    },
                    'mimetype': 'image/jpeg'
                },
                'id': 'media1'
            }
        })
    image_response = AsyncMock()
    image_response.content = b'image'
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, image_response])

    await save_podcast(session, _podcast_post(id_='789'))
    assert mock_write_text.call_count == 1
    assert mock_write_bytes.call_count == 1


async def test_save_podcast_image_null_content(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': {
                        'original': 'http://example.com/cover.jpg'
                    },
                    'mimetype': 'image/jpeg'
                },
                'id': 'media1'
            }
        })
    image_response = AsyncMock()
    image_response.content = None
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, image_response])

    await save_podcast(session, _podcast_post(id_='333'))
    assert mock_write_text.call_count == 1
    mock_write_bytes.assert_not_called()


async def test_save_podcast_no_original_image_or_download(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': {
                        'original': None
                    },
                    'mimetype': None
                },
                'id': 'media1'
            }
        })
    session = AsyncMock()
    session.get = AsyncMock(return_value=media_response)

    await save_podcast(session, _podcast_post(id_='111'))
    assert mock_write_text.call_count == 1
    mock_write_bytes.assert_not_called()


async def test_save_podcast_no_download_url_and_no_image_urls(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': None,
                    'mimetype': None
                },
                'id': 'media1'
            }
        })
    session = AsyncMock()
    session.get = AsyncMock(return_value=media_response)

    await save_podcast(session, _podcast_post(id_='444'))
    assert mock_write_text.call_count == 1
    mock_write_bytes.assert_not_called()


async def test_save_podcast_no_file_name_uses_media_id(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock()
    media_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': None,
                    'mimetype': None
                },
                'id': 'media1'
            }
        })
    audio_response = AsyncMock()
    audio_response.content = b'audio content'
    session = AsyncMock()
    session.get = AsyncMock(side_effect=[media_response, audio_response])

    await save_podcast(session, _podcast_post(id_='555'))
    assert mock_write_text.call_count == 1
    assert mock_write_bytes.call_count == 1


async def test_save_podcast_no_media(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    session = AsyncMock()
    post = cast(
        'PostsData', {
            'attributes': {
                'post_type': 'podcast',
                'url': 'http://example.com/podcast'
            },
            'id': '999',
            'relationships': {}
        })
    await save_podcast(session, post)
    mock_write_text.assert_called_once()
    session.get.assert_not_called()


async def test_get_all_posts_next_key_missing(mocker: MockerFixture) -> None:
    response1 = AsyncMock()
    response1.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri1'
                },
                'id': '1',
                'relationships': {}
            }],
            'links': {
                'next': 'next_uri'
            }
        })
    response1.raise_for_status = mocker.Mock()

    response2 = AsyncMock()
    response2.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri2'
                },
                'id': '2',
                'relationships': {}
            }],
            'links': {}
        })
    response2.raise_for_status = mocker.Mock()

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[response1, response2])

    posts = [x async for x in get_all_posts('campaign_id', session=session)]
    assert [x['id'] for x in posts] == ['1', '2']


async def test_get_all_posts_next_none(mocker: MockerFixture) -> None:
    response = AsyncMock()
    response.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri1'
                },
                'id': '1',
                'relationships': {}
            }],
            'links': {
                'next': None
            }
        })
    response.raise_for_status = mocker.Mock()

    session = AsyncMock()
    session.get = AsyncMock(return_value=response)

    posts = [x async for x in get_all_posts('campaign_id', session=session)]
    assert [x['id'] for x in posts] == ['1']


async def test_get_all_posts_multiple_pages_with_next(mocker: MockerFixture) -> None:
    response1 = AsyncMock()
    response1.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri1'
                },
                'id': '1',
                'relationships': {}
            }],
            'links': {
                'next': 'page2'
            }
        })
    response1.raise_for_status = mocker.Mock()

    response2 = AsyncMock()
    response2.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri2'
                },
                'id': '2',
                'relationships': {}
            }],
            'links': {
                'next': 'page3'
            }
        })
    response2.raise_for_status = mocker.Mock()

    response3 = AsyncMock()
    response3.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri3'
                },
                'id': '3',
                'relationships': {}
            }],
            'links': {
                'next': None
            }
        })
    response3.raise_for_status = mocker.Mock()

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[response1, response2, response3])

    posts = [x async for x in get_all_posts('campaign_id', session=session)]
    assert [x['id'] for x in posts] == ['1', '2', '3']
