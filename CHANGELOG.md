<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-04-27

### Added

- New runtime dependency on the `archiver-stats` package, which now provides the
  live statistics and status display implementation.
- Exported `IMAGES_PROCESSED`, `OTHERS_PROCESSED`, `PODCASTS_PROCESSED`,
  `POSTS_HANDLED`, and `YT_DLP_STATUS` stat-key constants, plus the `YTDLPState`
  dataclass, from `patreon_archiver.typing`.

### Changed

- `patreon_archiver.typing.Stats` is now a subclass of `archiver_stats.Stats`
  (a `MutableMapping`) rather than a dataclass with named fields. Access stats
  by key (for example `stats[POSTS_HANDLED]`) instead of by attribute.
- `patreon_archiver.status_display.StatusDisplay` is now a re-export of
  `archiver_stats.StatusDisplay`.

### Removed

- Named attributes on `Stats` such as `posts_handled`, `images_processed`, and
  `yt_dlp_current_uri`; use the exported stat-key constants with mapping access
  instead.

## [0.2.0] - 2026-04-16

### Added

- Rich-based live status display shown on standard error unless `--debug` or
  `--quiet` is passed, combining a spinner line with aligned live statistics:
  - Total posts fetched by the producer.
  - The yt-dlp URI currently being downloaded, annotated with its cumulative
    `n/total` position across the run.
  - Running processed counts for image, podcast, and other posts.
- `-q` / `--quiet` flag to suppress the live status display.
- Public `Stats` dataclass in `patreon_archiver.typing` exposing the live
  pipeline statistics surface (posts handled, per-type processed counters,
  yt-dlp URI progress).
- `OnMessage` type alias in `patreon_archiver.typing` for progress callbacks.
- Optional `on_message` and `on_cleanup` keyword parameters on worker and
  utility functions for progress and shutdown messages.

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
- yt-dlp worker now dispatches one URI per `ydl.download` call (previously
  batched up to `--yt-dlp-arg-limit` URIs) so the live display can report the
  URI currently in flight.
- Pressing Ctrl+C (or sending `SIGTERM`) during an active yt-dlp download now
  waits for the current download to finish to avoid file corruption. A
  transient warning is shown on the status line while yt-dlp is still
  running, and is cleared once the download completes. Pressing Ctrl+C (or
  sending `SIGTERM`) a second time force-quits immediately.
- Graceful shutdown listens for `SIGTERM` as well as `SIGINT`, prints a clear
  acknowledgement, and reports cleanup steps without a numbered prefix.
- On platforms without `asyncio` loop signal handlers (typically Windows),
  termination signals use a `signal.signal` fallback where supported.
- When `--debug` is not passed, `patreon_archiver` and `yt_dlp_utils` loggers
  default to WARNING so routine progress is surfaced through the live status
  display instead of log output.

### Fixed

- Handled Patreon pagination where `links.next` can be missing,
  avoiding premature failures while iterating posts.

### Removed

- Removed the `requests` dependency in favour of `niquests`.
- `utils`: removed public helpers `get_all_media_uris`, `process_posts`, `get_extension`,
  `get_shared_params`, `unique_iter`, and `write_if_new` from the public API.
- `-L` / `--yt-dlp-arg-limit` CLI option and its plumbing; yt-dlp URIs are
  now handed off one at a time, so the batch-size knob no longer applies.

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

[unreleased]: https://github.com/Tatsh/patreon-archiver/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Tatsh/patreon-archiver/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.7...v0.2.0
[0.1.7]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.1...v0.1.2
[0.1.0]: https://github.com/Tatsh/patreon-archiver/compare/v0.0.7...v0.1.0
