from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from patreon_archiver.utils import (
    UnknownMimetypeError,
    get_all_media_uris,
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
    mock_write_text.assert_called_once()  # No additional calls


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


def test_save_images(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_pdd: PostsData = {
        'attributes': {
            'url': 'http://example.com',
            'post_type': 'image_file',
            'post_metadata': {'image_order': ['id1', 'id2']},
            'post_file': {'name': '', 'url': 'http://example.com'},
        },
        'id': '123',
        'relationships': {},
    }
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_session.get.return_value.__enter__.return_value.json.side_effect = [
        {
            'data': {
                'attributes': {
                    'image_urls': {'original': 'http://image1.com'},
                    'mimetype': 'image/jpeg',
                },
                'id': 'id1',
            }
        },
        {
            'data': {
                'attributes': {
                    'image_urls': {'original': 'http://image2.com'},
                    'mimetype': 'image/png',
                },
                'id': 'id2',
            }
        },
    ]
    mock_session.get.return_value.__enter__.return_value.content = b'image content'

    save_images(mock_session, mock_pdd)
    assert mock_write_if_new.call_count == 3  # post.json + 2 images


def test_save_images_no_post_metadata(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_pdd: PostsData = {
        'attributes': {
            'url': 'http://example.com',
            'post_type': 'image_file',
            'post_metadata': None,
            'post_file': {'name': '', 'url': 'http://example.com'},
        },
        'id': '123',
        'relationships': {},
    }
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')

    save_images(mock_session, mock_pdd)
    assert mock_write_if_new.call_count == 1  # Only post.json
    mock_session.get.assert_not_called()


def test_save_other(mocker: MockerFixture) -> None:
    mock_pdd: PostsData = {
        'attributes': {'post_type': 'audio_embed', 'url': 'http://example.com'},
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


def test_process_posts(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.utils.save_images', return_value=['image1', 'image2'])
    mocker.patch('patreon_archiver.utils.save_other', return_value='other')
    mock_posts: Posts = {
        'data': [
            {
                'attributes': {
                    'post_type': 'image_file',
                    'post_metadata': None,
                    'post_file': {'name': '', 'url': 'http://example.com'},
                    'url': '',
                },
                'id': '',
                'relationships': {},
            },
            {
                'attributes': {'post_type': 'audio_embed', 'url': 'http://example.com'},
                'id': '',
                'relationships': {},
            },
            {
                'attributes': {'post_type': 'livestream_crowdcast', 'url': 'http://example.com'},
                'id': '',
                'relationships': {},
            },
        ],
        'links': {'next': None},
    }
    mock_session = mocker.MagicMock()

    result = list(process_posts(mock_posts, mock_session))
    assert result == ['image1', 'image2', 'http://example.com', 'other']


def test_process_posts_with_podcast(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_session = mocker.MagicMock()
    mock_session.get.return_value.__enter__.return_value.json.return_value = {
        'data': {
            'attributes': {
                'download_url': 'http://example.com/audio.mp3',
                'file_name': '/absolute/path/to/episode.mp3',
                'mimetype': None,
            },
            'id': 'media1',
        }
    }
    mock_session.get.return_value.__enter__.return_value.content = b'audio content'

    mock_posts: Posts = {
        'data': [
            {
                'attributes': {'post_type': 'podcast', 'url': 'http://example.com/podcast'},
                'id': '456',
                'relationships': {'media': {'data': [{'id': 'media1', 'type': 'media'}]}},
            },
        ],
        'links': {'next': None},
    }

    result = list(process_posts(mock_posts, mock_session))
    assert len(result) == 1
    result_first = result[0]
    assert isinstance(result_first, dict)
    assert result_first['target_dir'] == Path('.', 'podcasts', '456')
    assert mock_write_if_new.call_count == 2  # post.json + audio file


def test_process_posts_with_podcast_image_url(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_session = mocker.MagicMock()
    mock_session.get.return_value.__enter__.return_value.json.return_value = {
        'data': {
            'attributes': {
                'download_url': None,
                'image_urls': {'original': 'http://example.com/cover.jpg'},
                'mimetype': 'image/jpeg',
            },
            'id': 'media1',
        }
    }
    mock_session.get.return_value.__enter__.return_value.content = b'image content'

    mock_posts: Posts = {
        'data': [
            {
                'attributes': {'post_type': 'podcast', 'url': 'http://example.com/podcast'},
                'id': '789',
                'relationships': {'media': {'data': [{'id': 'media1', 'type': 'media'}]}},
            },
        ],
        'links': {'next': None},
    }

    result = list(process_posts(mock_posts, mock_session))
    assert len(result) == 1
    result_first = result[0]
    assert isinstance(result_first, dict)
    assert result_first['target_dir'] == Path('.', 'podcasts', '789')
    assert mock_write_if_new.call_count == 2  # post.json + image file
    image_call = mock_write_if_new.call_args_list[1]
    assert '01-media1.jpg' in str(image_call[0][0])


def test_save_podcast_no_media(mocker: MockerFixture) -> None:
    mocker.patch('pathlib.Path.mkdir')
    mock_write_if_new = mocker.patch('patreon_archiver.utils.write_if_new')
    mock_session = mocker.MagicMock()

    mock_pdd: PostsData = {
        'attributes': {'post_type': 'podcast', 'url': 'http://example.com/podcast'},
        'id': '999',
        'relationships': {},
    }

    result = save_podcast(mock_session, mock_pdd)
    assert result['target_dir'] == Path('.', 'podcasts', '999')
    assert mock_write_if_new.call_count == 1  # Only post.json
    mock_session.get.assert_not_called()


def test_get_all_media_uris(mocker: MockerFixture) -> None:
    mocker.patch('patreon_archiver.utils.process_posts', return_value=['uri1', 'uri2'])
    mock_session = mocker.MagicMock()
    mock_session.get.return_value.__enter__.return_value.json.side_effect = [
        {'data': [], 'links': {'next': 'next_uri'}},
        {'data': [], 'links': {}},
    ]

    uris = list(get_all_media_uris('campaign_id', session=mock_session))
    assert uris == ['uri1', 'uri2', 'uri1', 'uri2', 'uri1', 'uri2']


def test_get_all_media_uris_no_session(mocker: MockerFixture) -> None:
    mock_session = mocker.MagicMock()
    mock_session.get.return_value.__enter__.return_value.json.side_effect = [
        {'data': [], 'links': {'next': 'next_uri'}},
        {'data': [], 'links': {'next': None}},
    ]
    mocker.patch('patreon_archiver.utils.yt_dlp_utils.setup_session', return_value=mock_session)
    mocker.patch('patreon_archiver.utils.process_posts', return_value=['uri1', 'uri2'])

    uris = list(get_all_media_uris('campaign_id', browser='firefox', profile='TestProfile'))
    assert uris == ['uri1', 'uri2', 'uri1', 'uri2', 'uri1', 'uri2']
