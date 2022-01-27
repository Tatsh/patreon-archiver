from typing import Any, Optional, Sequence, TypedDict


class EntryPoints(TypedDict, total=False):
    console_scripts: Sequence[str]


def setup(*,
          author: str,
          author_email: str,
          description: str,
          license: str,
          long_description: str,
          name: str,
          url: str,
          version: str,
          classifiers: Optional[Sequence[str]] = ...,
          download_url: Optional[str] = ...,
          entry_points: Optional[EntryPoints] = ...,
          keywords: Optional[Sequence[str]] = ...,
          maintainer: Optional[str] = ...,
          maintainer_email: Optional[str] = ...,
          obsoletes: Optional[Sequence[str]] = ...,
          platforms: Optional[Sequence[str]] = ...,
          provides: Optional[Sequence[str]] = ...,
          requires: Optional[Sequence[str]] = ...,
          script_name: Optional[str] = ...,
          scripts_args: Optional[Sequence[str]] = ...,
          test_suite: Optional[str] = ...,
          tests_require: Optional[Sequence[str]] = ...,
          **kwargs: Any) -> None:
    ...


def find_packages(where: Optional[str] = ...,
                  include: Optional[Sequence[str]] = ...,
                  exclude: Optional[Sequence[str]] = ...) -> Sequence[str]:
    ...
