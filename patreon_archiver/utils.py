from os.path import isfile
from pathlib import Path
from types import FrameType
from typing import (Iterator, Literal, Mapping, Optional, Sequence, TypeVar,
                    Union)
import logging
import sys

from loguru import logger
import click

from .constants import FIELDS, SHARED_PARAMS

__all__ = ('UnknownMimetypeError', 'chunks', 'get_extension',
           'get_shared_params', 'write_if_new')


def write_if_new(target: Union[Path, str],
                 content: Union[str, bytes],
                 mode: str = 'w') -> None:
    if not isfile(target):
        with click.open_file(str(target), mode) as f:
            f.write(content)


class UnknownMimetypeError(Exception):
    pass


def get_extension(mimetype: str) -> Literal['png', 'jpg']:
    if mimetype == 'image/jpeg':
        return 'jpg'
    if mimetype == 'image/png':
        return 'png'
    raise UnknownMimetypeError(mimetype)


def get_shared_params(campaign_id: str) -> Mapping[str, str]:
    return {
        **SHARED_PARAMS,
        **{f'fields[{x}]': y
           for x, y in FIELDS.items()},
        **{
            'filter[campaign_id]': campaign_id,
        },
    }


T = TypeVar('T')


def chunks(l: Sequence[T], n: int) -> Iterator[Iterator[T]]:
    for i in range(0, len(l), n):
        yield iter(l[i:i + n])


class InterceptHandler(logging.Handler):  # pragma: no cover
    """Intercept handler taken from Loguru's documentation."""
    def emit(self, record: logging.LogRecord) -> None:
        level: Union[str, int]
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # Find caller from where originated the logged message
        frame: Optional[FrameType] = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage())


def setup_log_intercept_handler() -> None:  # pragma: no cover
    """Sets up Loguru to intercept records from the logging module."""
    logging.basicConfig(handlers=(InterceptHandler(),), level=0)


def setup_logging(debug: Optional[bool] = False) -> None:
    """Shared function to enable logging."""
    if debug:  # pragma: no cover
        setup_log_intercept_handler()
        logger.enable('')
    else:
        logger.configure(handlers=(dict(
            format='<level>{message}</level>',
            level='INFO',
            sink=sys.stderr,
        ),))
