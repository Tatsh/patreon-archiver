<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.1/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CLI progress feedback via `yaspin` unless `--debug` or `--quiet` is passed.
- `-q` / `--quiet` flag to disable spinner updates.
- Optional `on_message` and `on_cleanup` keyword parameters on worker and
  utility functions for progress and shutdown messages.
- `OnMessage` type alias in `typing`.

### Changed

- When `--debug` is not passed, `patreon_archiver` and `yt_dlp_utils` loggers
  default to WARNING so routine progress uses the spinner instead.
- Graceful shutdown listens for `SIGTERM` as well as `SIGINT`, prints a clear
  acknowledgement, and reports cleanup steps without a numbered prefix.
- On platforms without `asyncio` loop signal handlers (typically Windows),
  termination signals use a `signal.signal` fallback where supported.

## [0.2.0] - 2026-04-16

### Changed

- Migrated from synchronous `requests` to async `niquests` with `anyio`,
  making the core archiving logic fully asynchronous.
- The `yt-dlp-utils` dependency now uses the `[asyncio]` extra.
- Reworked the archiving pipeline to process posts via dedicated async workers
  for yt-dlp, images, podcasts, and other post types, and to stop cleanly on
  interruption.
- `typing`: added exported aliases, including `PostAttributes` and `Links`,
  and exported
  `MEDIA_POST_TYPES` from constants.

### Fixed

- Handled Patreon pagination where `links.next` can be missing,
  avoiding premature failures while iterating posts.

### Removed

- Removed the `requests` dependency in favour of `niquests`.
- `utils`: removed public helpers `get_all_media_uris`, `process_posts`, `get_extension`,
  `get_shared_params`, `unique_iter`, and `write_if_new` from the public API.

## [0.1.7] - 2026-04-13

### Fixed

- Fixed Python 3.10 compatibility: import `NotRequired` from
  `typing_extensions` instead of `typing`.
- Fixed Python 3.10 compatibility: replace `datetime.UTC` with
  `datetime.timezone.utc` in documentation configuration.
- Fixed Python 3.10/3.11 compatibility: add backport of `itertools.batched`
  for versions before 3.12.

## [0.1.6]

### Added

- `-P` / `--use-yt-dlp-for-podcasts` flag to send podcast media URLs to
  yt-dlp instead of using the built-in podcast handler.

### Fixed

- `utils`: fixed `yield from save_images` bug that yielded dict keys instead
  of `SaveInfo` objects.
- `main`: handled yt-dlp non-zero return codes when `--fail` is passed.

### Changed

- `main`: session is now always created before calling `get_all_media_uris`,
  and cookies are passed to yt-dlp.
- `main`: removed referer header workaround (yt-dlp/yt-dlp#13263 is resolved).
- `main`: added `yt_dlp_utils` and `urllib3` logger configuration.
- `utils`: `get_all_media_uris` now requires a `session` parameter and accepts
  optional `process_podcasts`. `process_posts` accepts `process_podcasts` to
  yield podcast URIs to yt-dlp when disabled.

## [0.1.5]

### Added

- The CLI now accepts `--cookie-json FILE` argument, where the file is a JSON
  array of objects with keys `name`, `value`, `domain`, `path`. This takes
  precedence over reading cookies from the browser.
- With the above flag, podcasts can be downloaded (due to a user-agent issue
  that will be resolved in a future release).
- `typing`: added podcast-related typing.
- `utils`: added the `save_podcast` function.
- Added AArch64 AppImage builds.

Thanks to @Qualify5303 for the new flag and podcast support.

### Changed

- `utils`: `process_posts` handles podcasts.

## [0.1.4]

### Added

- Attestation.

## [0.1.3]

### Fixed

- Added a referer header until yt-dlp/yt-dlp#13263 is included in a yt-dlp release.

## [0.1.2]

### Changed

- Used the retry feature of `yt_dlp_utils.setup_session`.

## [0.1.0]

### Changed

- Moved a lot of general functionality to `utils`.
- Cleaner log messages.

[unreleased]: https://github.com/Tatsh/patreon-archiver/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.7...v0.2.0
[0.1.7]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.1...v0.1.2
[0.1.0]: https://github.com/Tatsh/patreon-archiver/compare/v0.0.7...v0.1.0
