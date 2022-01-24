from os.path import isfile
from pathlib import Path
from typing import Iterator, Literal, Mapping, Sequence, TypeVar, Union

from .constants import FIELDS, SHARED_PARAMS, USER_AGENT

__all__ = ('UnknownMimetypeError', 'chunks', 'get_extension',
           'get_shared_headers', 'get_shared_params', 'write_if_new')


def write_if_new(target: Union[Path, str],
                 content: Union[str, bytes],
                 mode: str = 'w') -> None:
    if not isfile(target):
        with open(target, mode) as f:
            f.write(content)


class UnknownMimetypeError(Exception):
    pass


def get_extension(mimetype: str) -> Literal['png', 'jpg']:
    if mimetype == 'image/jpeg':
        return 'jpg'
    if mimetype == 'image/png':
        return 'png'
    raise UnknownMimetypeError(mimetype)


def get_shared_headers(campaign_id: str) -> Mapping[str, str]:
    return {
        'user-agent':
        USER_AGENT,
        'content-type':
        'application/vnd.api+json',
        'referer': ('https://www.patreon.com/m/'
                    f'{campaign_id}/posts?sort=published_at'),
        'accept-language':
        'en,en-GB;q=0.9,en-US;q=0.8',
        'accept':
        '*/*',
        'authority':
        'www.patreon.com',
        'pragma':
        'no-cache',
        'cache-control':
        'no-cache',
        'dnt':
        '1',
    }


def get_shared_params(campaign_id: str) -> Mapping[str, str]:
    return {
        **SHARED_PARAMS,
        **{f'fields[{x}]': y
           for x, y in FIELDS.items()},
        **{
            'fields[campaign_id]': campaign_id,
        },
    }


T = TypeVar('T')


def chunks(l: Sequence[T], n: int) -> Iterator[Sequence[T]]:
    for i in range(0, len(l), n):
        yield l[i:i + n]
