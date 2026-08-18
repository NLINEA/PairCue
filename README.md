# PairCue

**Two languages. One perfectly timed track.**

Turn a private movie library into a language-learning library. PairCue finds or generates source
subtitles, aligns them to the media, translates them, and writes one reusable bilingual SRT for
Plex, Jellyfin, Emby, Kodi, Infuse, VLC, or a plain media folder.

`existing subtitle → official search → speech transcription → translation → bilingual SRT`

Choose any source and learning language; English to Traditional Chinese is only the default, not a
limitation. PairCue creates standard sidecar files instead of requiring a browser extension or a
custom video player.

> Beta software. Back up a small test library before enabling it on your full media collection.

## Start with the smallest win

From the checked-out project folder, install PairCue with Python 3.11 or newer:

```bash
python3 -m pip install .
```

### Already have two subtitle files?

Already have two subtitle files from the same movie? Create a learning track without configuring a
media server, API key, or database:

```bash
paircue pair Movie.ja.srt Movie.en.srt -o Movie.en.cc.srt
```

PairCue matches by time, including one-to-many cue differences, and refuses low-confidence pairs.
Use `--order source-first` to reverse the two lines. Nothing is uploaded by this command.

### Want to try the complete flow on one video?

Open the private visual setup wizard—there is no command to remember beyond the product name:

```bash
paircue
```

Choose **Try one video**, select the two languages, and tell PairCue whether you already have zero,
one, or two subtitle tracks. Fields for search or translation appear only when they are needed.
Press **Save and choose a video**. The wizard talks
only to the PairCue process on your own device and has no analytics, account, or stored browser
form data. It writes the file for you and backs up an older configuration before replacement.
After saving, PairCue opens the system file chooser automatically. Pick one video and the first run
starts—there is no path or second command to type. It reveals the completed subtitle in Finder or
the file manager. Later runs use `paircue learn --config paircue.env`.

The setup page also checks whether FFmpeg and FFprobe are available before the first video. PairCue
does not bundle those tools, preserving a clear license boundary. Two existing SRT tracks can still
be merged without them.

`paircue learn` needs no media server or persistent database. It uses existing sidecars first,
then the enabled search, speech-generation, and translation fallbacks, and writes the result beside
the video. When no filename is supplied, PairCue opens the system file chooser. Use `--title` and
`--year` only when the filename is not useful for metadata search.

## What it writes

- `Movie.<source>.srt` — synchronized source subtitle when one is downloaded or extracted.
- `Movie.<target>.srt` — translated learning language.
- `Movie.<target>.cc.srt` — both languages on the same cue timing.

With the default `zh-TW` setting, the last two files are `Movie.zh-TW.srt` and
`Movie.zh-TW.cc.srt`.

Translation is all-or-nothing: PairCue does not publish bilingual output when even one cue is
missing. By default, the source sidecar is also rewritten atomically with non-dialogue cues removed;
set `PAIRCUE_CLEAN_SOURCE_OUTPUT=false` to preserve the text exactly.

## Automate the library after one video works

Run `paircue` again and choose **Automate my library**. The saved `paircue.env` contains
both Docker host settings and PairCue settings, so there is only one file to manage. Put it beside
`docker-compose.yml`, then run:

```bash
docker compose --env-file paircue.env build core
docker compose --env-file paircue.env run --rm core paircue doctor
docker compose --env-file paircue.env up -d core
```

Polling is the default and the status port binds only to `127.0.0.1`. Start with a test library or a
copy of a few media files. This repository provides a Dockerfile for local builds; PairCue does not
publish an official prebuilt container image.

After startup, view queue and recent results through the protected status endpoint:

```bash
curl -H "Authorization: Bearer <token from paircue.env>" http://127.0.0.1:9292/v1/status
```

It reports filenames rather than full media-library paths.

## Supported platforms

| Platform | Discovery | Event trigger |
|---|---|---|
| Plex | Authenticated library API | Polling or native webhook |
| Jellyfin | Authenticated user-items API | Polling or Webhook Plugin `ItemAdded` event |
| Emby | Authenticated user-items API | Polling or `ItemAdded` webhook |
| Any NAS or local media folder | Recursive video-file scan | Polling |

Kodi, Infuse, VLC, and other players can read the resulting standard SRT sidecars when they access
the same media files. They do not need a separate PairCue integration.

Select exactly one source in `paircue.env`.

Plex:

```dotenv
PAIRCUE_PLATFORM=plex
PAIRCUE_SERVER_URL=http://plex:32400
PAIRCUE_SERVER_TOKEN=your-plex-token
PAIRCUE_SERVER_PATH_PREFIX=/volume1/Media
```

Jellyfin (use `PAIRCUE_PLATFORM=emby` and the Emby URL for Emby):

```dotenv
PAIRCUE_PLATFORM=jellyfin
PAIRCUE_SERVER_URL=http://jellyfin:8096
PAIRCUE_SERVER_TOKEN=your-api-key
PAIRCUE_SERVER_USER_ID=your-user-id
PAIRCUE_SERVER_PATH_PREFIX=/media
```

No media server:

```dotenv
PAIRCUE_PLATFORM=filesystem
```

`PAIRCUE_SERVER_PATH_PREFIX` is the library path seen by Plex, Jellyfin, or Emby. `MEDIA_PATH` in
`paircue.env` is the same library path on the Docker host; it is mounted as
`PAIRCUE_MEDIA_ROOT=/media` inside PairCue. Existing `PAIRCUE_PLEX_*` variables remain accepted for
backward compatibility.

Polling needs no webhook setup. For faster Jellyfin or Emby events, send authenticated JSON to
`/v1/webhooks/jellyfin` or `/v1/webhooks/emby` with this contract:

```json
{"NotificationType":"ItemAdded","ItemId":"the-item-id","ItemType":"Movie"}
```

The request must include `Content-Type: application/json` and
`Authorization: Bearer <PAIRCUE_API_TOKEN>`. Jellyfin's official
[Webhook Plugin](https://jellyfin.org/docs/general/server/notifications/) supports custom generic
templates; Emby documents its authenticated server API in the
[Emby REST API guide](https://dev.emby.media/doc/restapi/).

## Translation providers

The default example uses GLM through the z.ai OpenAI-compatible endpoint. Any compatible endpoint
can be configured with `PAIRCUE_TRANSLATION_BASE_URL`, `PAIRCUE_TRANSLATION_API_KEY`, and
`PAIRCUE_TRANSLATION_MODEL`. A second compatible provider can be configured as fallback.

Subtitle text is sent to the configured translation provider. Users are responsible for reviewing
that provider's privacy policy and terms.

## Automatic subtitle search and download

PairCue has a small, independently written adapter for the documented OpenSubtitles.com REST API.
It does not use Subliminal, scrape provider pages, or copy another subtitle product's client code.
It computes the lightweight OpenSubtitles file hash and tries an exact release match before falling
back to title, year, season, and episode metadata. Create your own OpenSubtitles API consumer, then
set:

```dotenv
PAIRCUE_SUBTITLE_DOWNLOAD_ENABLED=true
PAIRCUE_OPENSUBTITLES_API_KEY=your-api-key
```

An OpenSubtitles account login is optional; if used, set both
`PAIRCUE_OPENSUBTITLES_USERNAME` and `PAIRCUE_OPENSUBTITLES_PASSWORD`. Search/download is disabled
when no API key is configured. API quotas, provider terms, and the right to use downloaded subtitle
content remain the user's responsibility.

## Generate subtitles when search finds nothing

When translation is enabled but no source subtitle exists, PairCue can extract the first audio
track into bounded FLAC chunks and call an OpenAI-compatible transcription endpoint. It requests
segment timestamps, validates every returned cue, joins chunk timelines, and publishes the source
SRT only after every chunk succeeds.

```dotenv
PAIRCUE_TRANSCRIPTION_ENABLED=true
PAIRCUE_TRANSCRIPTION_BASE_URL=https://api.openai.com/v1
PAIRCUE_TRANSCRIPTION_API_KEY=your-api-key
PAIRCUE_TRANSCRIPTION_MODEL=whisper-1
```

`whisper-1` is the safe default because the documented API supports `verbose_json` segment
timestamps for that model. A compatible self-hosted endpoint can be used instead. Transcription is
off by default: when enabled, extracted audio is sent to the configured endpoint, so review its
privacy, retention, pricing, and model terms first.

## Language-learning pairs

Set source and target [BCP-47 language tags](https://www.rfc-editor.org/info/bcp47) in
`paircue.env`. For Japanese dialogue with English learning subtitles:

```dotenv
PAIRCUE_SOURCE_LANGUAGE=ja
PAIRCUE_TARGET_LANGUAGE=en
PAIRCUE_BILINGUAL_ORDER=target-first
```

Common examples include `zh-TW`, `zh-HK`, `zh-Hant`, `zh-CN`, `ja`, `ko`, `es`, `fr`, and
`pt-BR`. Language names are detected automatically. `target-first` places the learning language on
top; use `source-first` to reverse the two lines. For a language or regional style that needs more
direction, add:

```dotenv
PAIRCUE_TARGET_LANGUAGE_NAME=Traditional Chinese (Hong Kong)
PAIRCUE_TARGET_LANGUAGE_STYLE=natural Cantonese-influenced Hong Kong wording suitable for subtitles
```

English can be either the source or target, so pairs such as `en → zh-HK`, `ja → en`, `ko → en`,
and `es → fr` are supported. Source and target must differ. When AI translation is disabled,
PairCue asks OpenSubtitles for the configured target language; Chinese targets can also fall back
to safe OpenCC script conversion.

| Learning goal | Source | Target | Bilingual result |
|---|---|---|---|
| Learn English from Japanese media | `ja` | `en` | English + Japanese |
| Learn Japanese with an English base | `en` | `ja` | Japanese + English |
| Watch with Hong Kong Traditional Chinese | `en` | `zh-HK` | zh-HK + English |

## Merge two existing subtitle languages

When both configured sidecars already exist, for example `Movie.ja.srt` and `Movie.en.srt`, PairCue
synchronizes both tracks and creates `Movie.en.cc.srt` without calling the translation provider.
It matches cues by time rather than subtitle number, so one Japanese cue can safely pair with two
shorter English cues, or the reverse.

The merger requires at least 70% timing coverage in both tracks by default. It will not publish a
misaligned bilingual file when confidence is lower. If AI translation is enabled, PairCue falls
back to translating the synchronized source track; otherwise it keeps the valid single-language
file. Advanced thresholds can be adjusted in `paircue.env`:

```dotenv
PAIRCUE_BILINGUAL_MERGE_TOLERANCE_MS=350
PAIRCUE_BILINGUAL_MERGE_MIN_MATCH_RATIO=0.7
```

## Automatic synchronization

With `PAIRCUE_SYNC_ENABLED=true` (the default), PairCue decodes temporary mono PCM through the
user-installed FFmpeg, then uses PairCue's own activity detector and FFT cross-correlation to
estimate the subtitle offset. It does not depend on ffsubsync. The translated and bilingual cues
inherit the synchronized source timings exactly. A conservative confidence threshold and maximum
offset are configurable; replacement is atomic, and PairCue keeps the original timing when it
cannot confirm a match.

```dotenv
PAIRCUE_SYNC_MAX_OFFSET_SECONDS=120
PAIRCUE_SYNC_MIN_CONFIDENCE=0.24
```

## Optional Download Station UI

Download Station is retained as an isolated optional service. It does not receive the media-server
token, translation key, state volume, or media-library mount.

Copy `downloads.env.example` to `downloads.env` and use a different generated API token before
starting it.

```bash
docker compose --env-file paircue.env --profile downloads up -d downloads
```

The default binding is `127.0.0.1:9293`. Keep it behind a VPN or trusted reverse proxy when remote
access is needed. Open the page, enter the separate Download Station API token, and then add a
magnet or upload a small `.torrent` file.

## Security defaults

- Secrets are read from environment variables and are never accepted in URLs.
- Privileged API routes require a bearer token of at least 32 characters.
- Interactive API docs, CORS, proxy-header trust, and debug mode are disabled.
- Paths returned by any media server must map below `PAIRCUE_MEDIA_ROOT`.
- Subprocesses use argument arrays and never invoke a shell.
- Subtitle and state writes are atomic; job execution is deduplicated and locked per media path.
- Existing language tracks require confidence-scored timing coverage before bilingual publication.
- The Docker services drop Linux capabilities and run without root privileges.

See [SECURITY.md](SECURITY.md) for private vulnerability reporting guidance.

## Development

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
pytest
python scripts/check_runtime_licenses.py
```

For configuration checks without displaying secrets:

```bash
paircue doctor
paircue doctor --json
```

The design and trade-offs are documented in [ARCHITECTURE.md](ARCHITECTURE.md). Release changes are
listed in [CHANGELOG.md](CHANGELOG.md).

## Project status

The beta intentionally targets one media server or filesystem root and one worker. Its product
wedge is complete private-library automation: ordinary subtitle managers focus on acquiring a
single subtitle, while browser learning extensions focus on Netflix or YouTube. PairCue produces a
portable, synchronized bilingual learning file for media you already own. Planned follow-ups
include a translation cache, per-library language-learning profiles, richer status reporting, and
faster incremental scans.

PairCue is an independent project and is not affiliated with Plex, Jellyfin, Emby, Synology,
subtitle providers, or translation model providers. PairCue application logic is independently
implemented; contributions copied or closely adapted from other subtitle products are not
accepted.

## License

[MIT](LICENSE). See [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependency, FFmpeg, service, and content
boundaries. This is project documentation, not legal advice.
