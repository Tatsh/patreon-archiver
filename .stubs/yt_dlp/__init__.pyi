from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple


def parse_options(
    argv: Optional[List[str]] = ...
) -> Tuple[Any, Any, Iterable[str], Mapping[str, Any]]:
    ...


class YoutubeDL:
    def __init__(self, options: Mapping[str, Any]) -> None:
        ...

    def __enter__(self) -> YoutubeDL:
        ...

    def __exit__(self) -> None:
        ...

    def download(self, urls: Sequence[str]) -> None:
        ...
