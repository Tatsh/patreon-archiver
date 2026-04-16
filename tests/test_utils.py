"""Tests for utility helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

from patreon_archiver.utils import (
    UnknownMimetypeError,
    get_all_media_uris,
    get_all_posts,
    get_extension,
    process_posts,
    save_images,
    save_other,
    save_podcast,
    unique_iter,
    write_if_new,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from patreon_archiver.typing import Posts, PostsData
    from pytest_mock import MockerFixture


def test_write_if_new_creates_file(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')

    write_if_new('test.txt', 'content')
    mock_write_text.assert_called_once_with('content', encoding='utf-8')
    mock_write_bytes.assert_not_called()

    write_if_new('test.bin', b'binary content', mode='wb')
    mock_write_bytes.assert_called_once_with(b'binary content')
    mock_write_text.assert_called_once()  # No additional calls.


def test_write_if_new_mismatched_mode(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=False)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')
    write_if_new(
        'test.bin',
        123,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        mode='wb')
    mock_write_bytes.assert_not_called()
    mock_write_text.assert_not_called()


def test_write_if_new_does_not_overwrite(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.is_file', return_value=True)
    mock_write_text = mocker.patch('pathlib.Path.write_text')
    mock_write_bytes = mocker.patch('pathlib.Path.write_bytes')

    write_if_new('test.txt', 'content')
    mock_write_text.assert_not_called()
    mock_write_bytes.assert_not_called()


def test_get_extension_valid() -> None:
    assert get_extension('image/jpeg') == 'jpg'
    assert get_extension('image/png') == 'png'
    assert get_extension('image/webp') == 'webp'
    assert get_extension('image/gif') == 'gif'


def test_get_extension_invalid() -> None:
    with pytest.raises(UnknownMimetypeError):
        get_extension('application/json')


def test_unique_iter() -> None:
    input_list = [1, 2, 2, 3, 1]
    assert list(unique_iter(input_list)) == [1, 2, 3]


async def test_save_images(mocker: MockerFixture) -> None:
    mock_response = AsyncMock()
    mock_response.json = Mock(side_effect=[
        {
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image1.com'
                    },
                    'mimetype': 'image/jpeg',
                },
                'id': 'id1',
            },
        },
        {
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image2.com'
                    },
                    'mimetype': 'image/png',
                },
                'id': 'id2',
            },
        },
    ])
    mock_response.content = b'image content'
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    mock_pdd: PostsData = {
        'attributes': {
            'url': 'http://example.com',
            'post_type': 'image_file',
            'post_metadata': {
                'image_order': ['id1', 'id2']
            },
            'post_file': {
                'name': '',
                'url': 'http://example.com'
            },
        },
        'id': '123',
        'relationships': {},
    }
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')

    await save_images(mock_session, mock_pdd)
    assert mock_write_if_new.call_count == 3  # post.json + 2 images


async def test_save_images_null_content(mocker: MockerFixture) -> None:
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'image_urls': {
                        'original': 'http://image1.com'
                    },
                    'mimetype': 'image/jpeg',
                },
                'id': 'id1',
            },
        })
    mock_img_response = AsyncMock()
    mock_img_response.content = None
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_response, mock_img_response])
    mock_pdd: PostsData = {
        'attributes': {
            'url': 'http://example.com',
            'post_type': 'image_file',
            'post_metadata': {
                'image_order': ['id1']
            },
            'post_file': {
                'name': '',
                'url': 'http://example.com'
            },
        },
        'id': '124',
        'relationships': {},
    }
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')

    await save_images(mock_session, mock_pdd)
    assert mock_write_if_new.call_count == 1  # Only `post.json`; the image is skipped.


async def test_save_images_no_post_metadata(mocker: MockerFixture) -> None:
    mock_session = AsyncMock()
    mock_pdd: PostsData = {
        'attributes': {
            'url': 'http://example.com',
            'post_type': 'image_file',
            'post_metadata': None,
            'post_file': {
                'name': '',
                'url': 'http://example.com'
            },
        },
        'id': '123',
        'relationships': {},
    }
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')

    await save_images(mock_session, mock_pdd)
    assert mock_write_if_new.call_count == 1  # Only `post.json`.
    mock_session.get.assert_not_called()


def test_save_other(mocker: MockerFixture) -> None:
    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'audio_embed',
            'url': 'http://example.com'
        },
        'id': '123',
        'relationships': {},
    }
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')

    save_other(mock_pdd)
    mock_write_if_new.assert_called_once_with(
        Path('other', 'audio_embed-123.json'),
        '{\n  "attributes": {\n    "post_type": "audio_embed",\n    "url": "http://example.com"\n'
        '  },\n  "id": "123",\n  "relationships": {}\n}\n',
    )


async def test_process_posts(mocker: MockerFixture) -> None:
    mock_save_info = {'post_data_dict': {}, 'target_dir': Path('images', '123')}
    mocker.patch('patreon_archiver.utils.save_images',
                 new_callable=AsyncMock,
                 return_value=mock_save_info)
    mocker.patch('patreon_archiver.utils.save_other', return_value='other')
    mock_posts: Posts = {
        'data': [
            {
                'attributes': {
                    'post_type': 'image_file',
                    'post_metadata': None,
                    'post_file': {
                        'name': '',
                        'url': 'http://example.com'
                    },
                    'url': '',
                },
                'id': '',
                'relationships': {},
            },
            {
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'http://example.com'
                },
                'id': '',
                'relationships': {},
            },
            {
                'attributes': {
                    'post_type': 'livestream_crowdcast',
                    'url': 'http://example.com'
                },
                'id': '',
                'relationships': {},
            },
        ],
        'links': {
            'next': None
        },
    }
    mock_session = AsyncMock()

    result = [x async for x in process_posts(mock_posts, mock_session)]
    assert result == [mock_save_info, 'http://example.com', 'other']


async def test_process_posts_with_podcast(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': '/absolute/path/to/episode.mp3',
                    'mimetype': None,
                },
                'id': 'media1',
            },
        })
    mock_response.content = b'audio content'
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    mock_posts: Posts = {
        'data': [{
            'attributes': {
                'post_type': 'podcast',
                'url': 'http://example.com/podcast'
            },
            'id': '456',
            'relationships': {
                'media': {
                    'data': [{
                        'id': 'media1',
                        'type': 'media'
                    }]
                }
            },
        }],
        'links': {
            'next': None
        },
    }

    result = [x async for x in process_posts(mock_posts, mock_session)]
    assert len(result) == 1
    result_first = result[0]
    assert isinstance(result_first, dict)
    assert result_first['target_dir'] == Path('.', 'podcasts', '456')
    assert mock_write_if_new.call_count == 2  # `post.json` and the audio file.


async def test_process_posts_with_podcast_image_url(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': {
                        'original': 'http://example.com/cover.jpg'
                    },
                    'mimetype': 'image/jpeg',
                },
                'id': 'media1',
            },
        })
    mock_response.content = b'image content'
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    mock_posts: Posts = {
        'data': [{
            'attributes': {
                'post_type': 'podcast',
                'url': 'http://example.com/podcast'
            },
            'id': '789',
            'relationships': {
                'media': {
                    'data': [{
                        'id': 'media1',
                        'type': 'media'
                    }]
                }
            },
        }],
        'links': {
            'next': None
        },
    }

    result = [x async for x in process_posts(mock_posts, mock_session)]
    assert len(result) == 1
    result_first = result[0]
    assert isinstance(result_first, dict)
    assert result_first['target_dir'] == Path('.', 'podcasts', '789')
    assert mock_write_if_new.call_count == 2  # `post.json` and the image file.
    image_call = mock_write_if_new.call_args_list[1]
    assert '01-media1.jpg' in str(image_call[0][0])


async def test_save_podcast_null_content(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': 'episode.mp3',
                    'mimetype': None,
                },
                'id': 'media1',
            },
        })
    mock_dl_response = AsyncMock()
    mock_dl_response.content = None
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_response, mock_dl_response])

    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'podcast',
            'url': 'http://example.com/podcast'
        },
        'id': '222',
        'relationships': {
            'media': {
                'data': [{
                    'id': 'media1',
                    'type': 'media'
                }]
            }
        },
    }

    result = await save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '222')
    assert mock_write_if_new.call_count == 1  # Only `post.json`.


async def test_save_podcast_image_null_content(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': {
                        'original': 'http://example.com/cover.jpg'
                    },
                    'mimetype': 'image/jpeg',
                },
                'id': 'media1',
            },
        })
    mock_img_response = AsyncMock()
    mock_img_response.content = None
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_response, mock_img_response])

    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'podcast',
            'url': 'http://example.com/podcast'
        },
        'id': '333',
        'relationships': {
            'media': {
                'data': [{
                    'id': 'media1',
                    'type': 'media'
                }]
            }
        },
    }

    result = await save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '333')
    assert mock_write_if_new.call_count == 1  # Only `post.json`.


async def test_save_podcast_image_url_no_original(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': {
                        'original': None
                    },
                    'mimetype': None,
                },
                'id': 'media1',
            },
        })
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'podcast',
            'url': 'http://example.com/podcast'
        },
        'id': '111',
        'relationships': {
            'media': {
                'data': [{
                    'id': 'media1',
                    'type': 'media'
                }]
            }
        },
    }

    result = await save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '111')
    assert mock_write_if_new.call_count == 1  # Only `post.json`.


async def test_save_podcast_no_download_url_no_image_urls(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': None,
                    'image_urls': None,
                    'mimetype': None,
                },
                'id': 'media1',
            },
        })
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'podcast',
            'url': 'http://example.com/podcast'
        },
        'id': '444',
        'relationships': {
            'media': {
                'data': [{
                    'id': 'media1',
                    'type': 'media'
                }]
            }
        },
    }

    result = await save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '444')
    assert mock_write_if_new.call_count == 1  # Only `post.json`.


async def test_save_podcast_no_file_name(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_response = AsyncMock()
    mock_response.json = Mock(
        return_value={
            'data': {
                'attributes': {
                    'download_url': 'http://example.com/audio.mp3',
                    'file_name': None,
                    'mimetype': None,
                },
                'id': 'media1',
            },
        })
    mock_response.content = b'audio content'
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)

    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'podcast',
            'url': 'http://example.com/podcast'
        },
        'id': '555',
        'relationships': {
            'media': {
                'data': [{
                    'id': 'media1',
                    'type': 'media'
                }]
            }
        },
    }

    result = await save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '555')
    assert mock_write_if_new.call_count == 2  # `post.json` and the audio file.
    audio_call = mock_write_if_new.call_args_list[1]
    assert 'media1-media1' in str(audio_call[0][0])


async def test_save_podcast_no_media(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_session = AsyncMock()

    mock_pdd: PostsData = {
        'attributes': {
            'post_type': 'podcast',
            'url': 'http://example.com/podcast'
        },
        'id': '999',
        'relationships': {},
    }

    result = await save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '999')
    assert mock_write_if_new.call_count == 1  # Only `post.json`.
    mock_session.get.assert_not_called()


async def test_process_posts_podcast_not_processed(mocker: MockerFixture) -> None:
    mock_session = AsyncMock()
    mock_posts: Posts = {
        'data': [{
            'attributes': {
                'post_type': 'podcast',
                'url': 'http://example.com/podcast'
            },
            'id': '456',
            'relationships': {
                'media': {
                    'data': [{
                        'id': 'media1',
                        'type': 'media'
                    }]
                }
            },
        }],
        'links': {
            'next': None
        },
    }

    result = [x async for x in process_posts(mock_posts, mock_session, process_podcasts=False)]
    assert result == ['http://example.com/podcast']


async def test_get_all_media_uris_filters_non_strings(mocker: MockerFixture) -> None:
    async def _mock_process_posts(  # noqa: RUF029
            *_args: object, **_kwargs: object) -> AsyncGenerator[object]:
        yield 'uri1'
        yield {'post_data_dict': {}, 'target_dir': Path()}

    mocker.patch('patreon_archiver.utils.process_posts', side_effect=_mock_process_posts)
    resp1 = AsyncMock()
    resp1.json = Mock(return_value={'data': [], 'links': {'next': 'next_uri'}})
    resp1.raise_for_status = mocker.Mock()
    resp2 = AsyncMock()
    resp2.json = Mock(return_value={'data': [], 'links': {'next': None}})
    resp2.raise_for_status = mocker.Mock()
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[resp1, resp2])

    uris = [x async for x in get_all_media_uris('campaign_id', session=mock_session)]
    assert uris == ['uri1', 'uri1']


async def test_get_all_media_uris(mocker: MockerFixture) -> None:
    async def _mock_process_posts(  # noqa: RUF029
            *_args: object, **_kwargs: object) -> AsyncGenerator[str]:
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.utils.process_posts', side_effect=_mock_process_posts)
    resp1 = AsyncMock()
    resp1.json = Mock(return_value={'data': [], 'links': {'next': 'next_uri'}})
    resp1.raise_for_status = mocker.Mock()
    resp2 = AsyncMock()
    resp2.json = Mock(return_value={'data': [], 'links': {}})
    resp2.raise_for_status = mocker.Mock()
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[resp1, resp2])

    uris = [x async for x in get_all_media_uris('campaign_id', session=mock_session)]
    assert uris == ['uri1', 'uri2', 'uri1', 'uri2']


async def test_get_all_media_uris_next_none(mocker: MockerFixture) -> None:
    async def _mock_process_posts(  # noqa: RUF029
            *_args: object, **_kwargs: object) -> AsyncGenerator[str]:
        yield 'uri1'
        yield 'uri2'

    mocker.patch('patreon_archiver.utils.process_posts', side_effect=_mock_process_posts)
    resp1 = AsyncMock()
    resp1.json = Mock(return_value={'data': [], 'links': {'next': 'next_uri'}})
    resp1.raise_for_status = mocker.Mock()
    resp2 = AsyncMock()
    resp2.json = Mock(return_value={'data': [], 'links': {'next': None}})
    resp2.raise_for_status = mocker.Mock()
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[resp1, resp2])

    uris = [x async for x in get_all_media_uris('campaign_id', session=mock_session)]
    assert uris == ['uri1', 'uri2', 'uri1', 'uri2']


async def test_get_all_posts_next_key_missing(mocker: MockerFixture) -> None:
    resp1 = AsyncMock()
    resp1.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri1'
                },
                'id': '1',
                'relationships': {},
            }],
            'links': {
                'next': 'next_uri'
            },
        })
    resp1.raise_for_status = mocker.Mock()
    resp2 = AsyncMock()
    resp2.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri2'
                },
                'id': '2',
                'relationships': {},
            }],
            'links': {},
        })
    resp2.raise_for_status = mocker.Mock()
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[resp1, resp2])

    posts = [x async for x in get_all_posts('campaign_id', session=mock_session)]
    assert [x['id'] for x in posts] == ['1', '2']


async def test_get_all_posts_next_none(mocker: MockerFixture) -> None:
    resp1 = AsyncMock()
    resp1.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri1'
                },
                'id': '1',
                'relationships': {},
            }],
            'links': {
                'next': None
            },
        })
    resp1.raise_for_status = mocker.Mock()
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=resp1)

    posts = [x async for x in get_all_posts('campaign_id', session=mock_session)]
    assert [x['id'] for x in posts] == ['1']


async def test_get_all_posts_multiple_pages_with_next(mocker: MockerFixture) -> None:
    resp1 = AsyncMock()
    resp1.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri1'
                },
                'id': '1',
                'relationships': {},
            }],
            'links': {
                'next': 'page2'
            },
        })
    resp1.raise_for_status = mocker.Mock()

    resp2 = AsyncMock()
    resp2.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri2'
                },
                'id': '2',
                'relationships': {},
            }],
            'links': {
                'next': 'page3'
            },
        })
    resp2.raise_for_status = mocker.Mock()

    resp3 = AsyncMock()
    resp3.json = Mock(
        return_value={
            'data': [{
                'attributes': {
                    'post_type': 'audio_embed',
                    'url': 'uri3'
                },
                'id': '3',
                'relationships': {},
            }],
            'links': {
                'next': None
            },
        })
    resp3.raise_for_status = mocker.Mock()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[resp1, resp2, resp3])

    posts = [x async for x in get_all_posts('campaign_id', session=mock_session)]
    assert [x['id'] for x in posts] == ['1', '2', '3']
