# Patreon Archiver

Download Patreon content. Video content will be saved using yt-dlp. You
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

```
Usage: patreon-archiver [OPTIONS] CAMPAIGN_ID

Options:
  -o, --output-dir TEXT           Output directory
  -b, --browser TEXT              Browser to read cookies from
  -p, --profile TEXT              Browser profile
  -x, --fail                      Do not continue processing after a failed
                                  yt-dlp command.
  -L, --yt-dlp-arg-limit INTEGER  Number of media URIs to pass to yt-dlp at a
                                  time.
  -d, --debug                     Enable debug output
  --help                          Show this message and exit.
```

## How to get the campaign ID

1. Go to the content creator's main page.
2. View the source and search for `patreon-media/p/campaign/`.
3. After the `/` there should be a number, as in
   `patreon-media/p/campaign/12345678`. In that case the campaign ID is
   `12345678`.
