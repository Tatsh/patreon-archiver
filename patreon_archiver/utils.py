from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, AnyStr, Literal, TypeVar
import logging

from .constants import FIELDS, SHARED_PARAMS

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

__all__ = ('UnknownMimetypeError', 'YoutubeDLLogger', 'get_extension', 'get_shared_params',
           'unique_iter', 'write_if_new')

T = TypeVar('T')
logger = logging.getLogger(__name__)


def write_if_new(target: Path | str, content: AnyStr, mode: str = 'w') -> None:
    target = Path(target)
    if not target.is_file():
        if 'b' in mode:
            assert isinstance(content, bytes)
            target.write_bytes(content)
        else:
            assert isinstance(content, str)
            target.write_text(content, encoding='utf-8')


class UnknownMimetypeError(Exception):
    pass


def get_extension(mimetype: str) -> Literal['png', 'jpg', 'webp', 'gif']:
    if mimetype == 'image/jpeg':
        return 'jpg'
    if mimetype == 'image/png':
        return 'png'
    if mimetype == 'image/webp':
        return 'webp'
    if mimetype == 'image/gif':
        return 'gif'
    raise UnknownMimetypeError(mimetype)


def get_shared_params(campaign_id: str) -> Mapping[str, str]:
    return {
        **SHARED_PARAMS,
        **{
            f'fields[{x}]': y
            for x, y in FIELDS.items()
        },
        'filter[campaign_id]': campaign_id,
    }


def unique_iter(seq: Iterable[T]) -> Iterator[T]:
    """https://stackoverflow.com/a/480227/374110."""
    seen: set[T] = set()
    seen_add = seen.add
    return (x for x in seq if not (x in seen or seen_add(x)))


class YoutubeDLLogger:
    def debug(self, message: str) -> None:
        if message.startswith('[debug] '):
            logger.debug(message)
        else:
            logger.info(message)

    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        logger.warning(message)

    def error(self, message: str) -> None:
        logger.error(message)
