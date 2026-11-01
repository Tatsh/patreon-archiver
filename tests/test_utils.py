"""Tests for utility helpers."""

from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast
from unittest.mock import AsyncMock, Mock
import logging

from niquests import Response
from niquests.exceptions import HTTPError, RequestException
import pytest

from patreon_archiver.constants import MEDIA_URI
from patreon_archiver.utils import (
    UnknownMimetypeError,
    get_all_posts,
    save_images,
    save_other,
    save_podcast,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from patreon_archiver.typing import PostsData


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


@pytest.mark.asyncio
@pytest.mark.parametrize('podcast', [False, True])
@pytest.mark.parametrize(('method', 'error'),
                         [('get', RequestException('Connection failed')),
                          ('raise_for_status', HTTPError('Forbidden')),
                          ('json', JSONDecodeError('Invalid JSON', '<html>', 0))])
async def test_save_media_recovers_from_metadata_errors(method: Literal['get', 'raise_for_status',
                                                                        'json'], error: Exception,
                                                        *, podcast: bool,
                                                        mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes', autospec=True)
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)
    mock_warning = mocker.spy(logging.getLogger('patreon_archiver.utils'), 'warning')
    post = _image_post(image_order=['failed', 'valid'])
    save = save_images
    target = Path('images', '123', '02-valid.jpg')
    if podcast:
        post = _podcast_post(media_id='failed')
        post['relationships']['media']['data'].append({'id': 'valid', 'type': 'media'})
        save = save_podcast
        target = Path('podcasts', '456', 'valid-episode.mp3')
    download_url = 'http://example.com/media'
    failed = AsyncMock(spec=Response)
    if method != 'get':
        getattr(failed, method).side_effect = error
    valid = AsyncMock(spec=Response)
    valid.json.return_value = {
        'data': {
            'attributes': {
                'download_url': download_url,
                'file_name': 'episode.mp3'
            } if podcast else {
                'image_urls': {
                    'original': download_url
                },
                'mimetype': 'image/jpeg'
            },
            'id': 'valid'
        }
    }
    download = AsyncMock(spec=Response)
    download.content = b'media content'
    session = AsyncMock()
    session.get.side_effect = [error if method == 'get' else failed, valid, download]

    await save(session, post)

    mock_write_bytes.assert_called_once_with(target, b'media content')
    assert session.get.await_args_list == [
        mocker.call(f'{MEDIA_URI}/failed'),
        mocker.call(f'{MEDIA_URI}/valid'),
        mocker.call(download_url)
    ]
    mock_warning.assert_called_once_with(
        'Skipping media `%s` in post `%s` after a metadata request failure (%s).', 'failed',
        post['id'], error)


async def test_save_images_writes_post_and_images(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    unavailable = AsyncMock(spec=Response)
    unavailable.json.return_value = {}
    media1 = AsyncMock(spec=Response)
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
    media2 = AsyncMock(spec=Response)
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
    session.get = AsyncMock(
        side_effect=[unavailable, media1, image_response, media2, image_response])

    await save_images(session, _image_post(image_order=['missing', 'id1', 'id2']))
    assert mock_write_bytes.call_count == 2


async def test_save_images_covers_webp_and_gif(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media1 = AsyncMock(spec=Response)
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
    media2 = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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


@pytest.mark.parametrize('metadata', [None, {'other': True}, {'image_order': None}])
async def test_save_images_without_metadata(metadata: dict[str, object] | None,
                                            mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)
    session = AsyncMock()

    post = _image_post(image_order=None)
    cast('dict[str, object]', post['attributes'])['post_metadata'] = metadata
    await save_images(session, post)
    mock_write_text.assert_called_once()
    session.get.assert_not_called()


async def test_save_images_raises_for_unknown_mimetype(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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

    media_response = AsyncMock(spec=Response)
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


async def test_save_images_reports_messages(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)
    messages: list[str] = []
    await save_images(AsyncMock(),
                      _image_post(id_='cb', image_order=None),
                      on_message=messages.append)
    assert messages == ['Processing image post cb...', 'Saved image post cb.']


def test_save_other_reports_messages(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.mkdir')
    messages: list[str] = []
    save_other(cast(
        'PostsData', {
            'attributes': {
                'post_type': 'audio_embed',
                'url': 'http://example.com'
            },
            'id': 'cb',
            'relationships': {}
        }),
               on_message=messages.append)
    assert messages == ['Processing post cb...', 'Saved post cb.']


async def test_save_podcast_reports_messages(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mocker.patch('pathlib.Path.write_text')
    mocker.patch('pathlib.Path.write_bytes')
    mocker.patch('anyio.Path.mkdir', new_callable=AsyncMock)
    messages: list[str] = []
    post = cast(
        'PostsData', {
            'attributes': {
                'post_type': 'podcast',
                'url': 'http://example.com/podcast'
            },
            'id': 'cb',
            'relationships': {}
        })
    await save_podcast(AsyncMock(), post, on_message=messages.append)
    assert messages == ['Processing podcast post cb...', 'Saved podcast post cb.']


async def test_get_all_posts_reports_pagination_messages(mocker: MockerFixture) -> None:
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
                'next': None
            }
        })
    response2.raise_for_status = mocker.Mock()

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[response1, response2])
    messages: list[str] = []
    posts = [
        x async for x in get_all_posts('campaign_id', session=session, on_message=messages.append)
    ]
    assert [x['id'] for x in posts] == ['1', '2']
    assert messages == ['Fetching next page of posts...']
