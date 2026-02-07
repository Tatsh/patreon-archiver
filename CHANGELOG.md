<!-- markdownlint-configure-file {"MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6]

### Added

- `-P` / `--use-yt-dlp-for-podcasts` flag to send podcast media URLs to yt-dlp instead of using
  the built-in podcast handler.

### Fixed

- `utils`: fixed `yield from save_images` bug that yielded dict keys instead of `SaveInfo` objects.
- `main`: Handle yt-dlp non-zero return codes when `--fail` is passed.

### Changed

- `main`: session is now always created before calling `get_all_media_uris`, and cookies are passed
  to yt-dlp.
- `main`: removed referer header workaround (yt-dlp/yt-dlp#13263 is resolved).
- `main`: added `yt_dlp_utils` and `urllib3` logger configuration.
- `utils`: `get_all_media_uris` now requires a `session` parameter and accepts optional
  `process_podcasts`. `process_posts` accepts `process_podcasts` to yield podcast URIs to yt-dlp
  when disabled.

## [0.1.5]

### Added

- The CLI now accepts `--cookie-json FILE` argument, where the file is a JSON array of objects with
  keys `name`, `value`, `domain`, `path`. This takes precedence over reading cookies from the
  browser.
- With the above flag, podcasts can be downloaded (due to a user-agent issue that will be resolved
  in a future release).
- typing: added Podcast related typing.
- utils: added `save_podcast` function.
- Now building AArch64 AppImage.

Thanks to @Qualify5303 for the new flag and podcast support.

### Changed

- utils: `process_posts` handles podcasts.

## [0.1.4]

### Added

- Attestation.

## [0.1.3]

### Fixed

- Add referer header until yt-dlp/yt-dlp#13263 is in a release of yt-dlp.

## [0.1.2]

### Changed

- Use retry feature of `yt_dlp_utils.setup_session`.

## [0.1.0]

### Changed

- Moved a lot of general functionality to `utils`.
- Cleaner log messages.

[unreleased]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Tatsh/patreon-archiver/compare/v0.1.1...v0.1.2
[0.1.0]: https://github.com/Tatsh/patreon-archiver/compare/v0.0.7...v0.1.0
