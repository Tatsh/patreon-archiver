from typing import Any, Iterable, Mapping

def parse_options(
    argv: list[str] | None = ...
) -> tuple[Any, Any, Iterable[str], Mapping[str, Any]]:
    ...


class YoutubeDL:
    def __init__(self, options: Mapping[str, Any]) -> None:
        ...

    def __enter__(self) -> YoutubeDL:
        ...

    def __exit__(self) -> None:
        ...

    def download(self, urls: list[str]) -> None:
        ...
