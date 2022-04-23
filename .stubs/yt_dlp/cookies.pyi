from http.cookiejar import Cookie
from typing import Any, Sequence


def extract_cookies_from_browser(browser: str,
                                 profile: str = ...,
                                 logger: Any = ...,
                                 *,
                                 keyring: Any = ...) -> Sequence[Cookie]:
    ...
