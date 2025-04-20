# patreon-archiver

[![QA](https://github.com/Tatsh/patreon-archiver/actions/workflows/qa.yml/badge.svg)](https://github.com/Tatsh/patreon-archiver/actions/workflows/qa.yml)
[![Tests](https://github.com/Tatsh/patreon-archiver/actions/workflows/tests.yml/badge.svg)](https://github.com/Tatsh/patreon-archiver/actions/workflows/tests.yml)
[![Coverage Status](https://coveralls.io/repos/github/Tatsh/patreon-archiver/badge.svg?branch=master)](https://coveralls.io/github/Tatsh/patreon-archiver?branch=master)
[![Documentation Status](https://readthedocs.org/projects/patreon-archiver/badge/?version=latest)](https://patreon-archiver.readthedocs.org/?badge=latest)
[![PyPI - Version](https://img.shields.io/pypi/v/patreon-archiver)](https://pypi.org/project/patreon-archiver/)
[![GitHub tag (with filter)](https://img.shields.io/github/v/tag/Tatsh/patreon-archiver)](https://github.com/Tatsh/patreon-archiver/tags)
[![License](https://img.shields.io/github/license/Tatsh/patreon-archiver)](https://github.com/Tatsh/patreon-archiver/blob/master/LICENSE.txt)
[![GitHub commits since latest release (by SemVer including pre-releases)](https://img.shields.io/github/commits-since/Tatsh/patreon-archiver/v0.0.7/master)](https://github.com/Tatsh/patreon-archiver/compare/v0.0.7...master)

Save Patreon content you have access to.

## Installation

### Poetry

```shell
poetry add patreon-archiver
```

### Pip

```shell
pip install patreon-archiver
```

## Configuration

Video content will be saved using yt-dlp. You
should ensure that you are logged into Patreon in the appropriate browser
profile.

Recommendations in `~/.config/yt-dlp/config` or equivalent file:

```plain
--cookies-from-browser chrome:Default

--add-metadata
--all-subs
--convert-subs srt
--embed-chapters
--embed-metadata
--embed-subs
--embed-thumbnail
--geo-bypass
--merge-output-format mkv
--no-overwrites
--sub-langs all
--write-info-json
--write-subs

--download-archive ~/somewhere-safe
```

## Usage

Run `patreon-archiver`. At minimum, campaign ID of the Patreon content
creator is required. See help with `--help`.

```plain
Usage: patreon-archiver [OPTIONS] CAMPAIGN_ID

Options:
  -o, --output-dir TEXT           Output directory
  -b, --browser TEXT              Browser to read cookies from
  -p, --profile TEXT              Browser profile
  -x, --fail                      Do not continue processing after a failed
                                  yt-dlp command.
  -L, --yt-dlp-arg-limit INTEGER  Number of media URIs to pass to yt-dlp at a
                                  time.
  -S, --sleep-time INTEGER        Number of seconds to wait between requests
  -d, --debug                     Enable debug output
  --help                          Show this message and exit.
```

## How to get the campaign ID

1. Go to the content creator's main page.
2. View the source and search for `patreon-media/p/campaign/`.
3. After the `/` there should be a number, as in
   `patreon-media/p/campaign/12345678`. In that case the campaign ID is
   `12345678`.
