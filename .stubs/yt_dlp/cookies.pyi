from enum import Enum
from http.cookiejar import Cookie
from typing import Protocol, Sequence


class _LinuxKeyring(Enum):
    KWALLET4 = ...
    KWALLET5 = ...
    KWALLET6 = ...
    GNOME_KEYRING = ...
    BASIC_TEXT = ...


class LoggerProtocol(Protocol):
    def debug(self, message: str) -> None:
        ...

    def info(self, message: str) -> None:
        ...

    def warning(self, message: str) -> None:
        ...

    def error(self, message: str) -> None:
        ...


def extract_cookies_from_browser(
        browser: str,
        profile: str = ...,
        logger: LoggerProtocol = ...,
        *,
        keyring: _LinuxKeyring = ...) -> Sequence[Cookie]:
    ...
