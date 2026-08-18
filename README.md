# SubFlow

**Automatically aligned bilingual subtitles for Plex — learn English or another language while
you watch.**

SubFlow creates automatically aligned bilingual subtitles for Plex. Choose a source language and a
learning language; SubFlow finds or extracts the source subtitle, synchronizes it to the media,
translates every cue with an OpenAI-compatible model, and writes Plex-friendly single-language and
bilingual sidecars. English to Traditional Chinese is the default, but neither language is fixed.

> Beta software. Back up a small test library before enabling it on your full media collection.

## What it writes

- `Movie.<source>.srt` — synchronized source subtitle when one is downloaded or extracted.
- `Movie.<target>.srt` — translated learning language.
- `Movie.<target>.cc.srt` — both languages on the same cue timing.

With the default `zh-TW` setting, the last two files are `Movie.zh-TW.srt` and
`Movie.zh-TW.cc.srt`.

Translation is all-or-nothing: SubFlow does not publish bilingual output when even one cue is
missing. By default, the source sidecar is also rewritten atomically with non-dialogue cues removed;
set `SUBFLOW_CLEAN_SOURCE_OUTPUT=false` to preserve the text exactly.

## Quick start

1. Copy `.env.example` to `.env` and set the NAS mount paths and UID/GID.
2. Copy `subflow.env.example` to `subflow.env` and fill in Plex and translation settings.
3. Build the image with `docker compose build core`.
4. Generate the API token with `docker run --rm subflow:0.1.0-beta.1 subflow generate-token`.
5. Start the subtitle service:

   ```bash
   docker compose up -d core
   ```

Polling is the default, so no inbound port is required. Start with a test library or a copy of a
few media files.

## Translation providers

The default example uses GLM through the z.ai OpenAI-compatible endpoint. Any compatible endpoint
can be configured with `SUBFLOW_TRANSLATION_BASE_URL`, `SUBFLOW_TRANSLATION_API_KEY`, and
`SUBFLOW_TRANSLATION_MODEL`. A second compatible provider can be configured as fallback.

Subtitle text is sent to the configured translation provider. Users are responsible for reviewing
that provider's privacy policy and terms.

## Language-learning pairs

Set source and target [BCP-47 language tags](https://www.rfc-editor.org/info/bcp47) in
`subflow.env`. For Japanese dialogue with English learning subtitles:

```dotenv
SUBFLOW_SOURCE_LANGUAGE=ja
SUBFLOW_TARGET_LANGUAGE=en
SUBFLOW_BILINGUAL_ORDER=target-first
```

Common examples include `zh-TW`, `zh-HK`, `zh-Hant`, `zh-CN`, `ja`, `ko`, `es`, `fr`, and
`pt-BR`. Language names are detected automatically. `target-first` places the learning language on
top; use `source-first` to reverse the two lines. For a language or regional style that needs more
direction, add:

```dotenv
SUBFLOW_TARGET_LANGUAGE_NAME=Traditional Chinese (Hong Kong)
SUBFLOW_TARGET_LANGUAGE_STYLE=natural Cantonese-influenced Hong Kong wording suitable for subtitles
```

English can be either the source or target, so pairs such as `en → zh-HK`, `ja → en`, `ko → en`,
and `es → fr` are supported. Source and target must differ. When AI translation is disabled,
SubFlow asks subtitle providers for the configured target language; Chinese targets can also fall
back to safe OpenCC script conversion.

| Learning goal | Source | Target | Bilingual result |
|---|---|---|---|
| Learn English from Japanese media | `ja` | `en` | English + Japanese |
| Learn Japanese with an English base | `en` | `ja` | Japanese + English |
| Watch with Hong Kong Traditional Chinese | `en` | `zh-HK` | zh-HK + English |

## Automatic synchronization

With `SUBFLOW_SYNC_ENABLED=true` (the default), SubFlow runs ffsubsync against the media before
translation. The translated and bilingual cues inherit the synchronized source timings exactly.
ffsubsync's low-confidence safeguard is enabled, and replacement is atomic; if synchronization
cannot be confirmed, SubFlow keeps the original timing and continues translation.

## Optional Download Station UI

Download Station is retained as an isolated optional service. It does not receive the Plex token,
translation key, state volume, or media-library mount.

Copy `downloads.env.example` to `downloads.env` and use a different generated API token before
starting it.

```bash
docker compose --profile downloads up -d downloads
```

The default binding is `127.0.0.1:9293`. Keep it behind a VPN or trusted reverse proxy when remote
access is needed. Open the page, enter the separate Download Station API token, and then add a
magnet or upload a small `.torrent` file.

## Security defaults

- Secrets are read from environment variables and are never accepted in URLs.
- Privileged API routes require a bearer token of at least 32 characters.
- Interactive API docs, CORS, proxy-header trust, and debug mode are disabled.
- Plex paths must resolve below `SUBFLOW_MEDIA_ROOT`.
- Subprocesses use argument arrays and never invoke a shell.
- Subtitle and state writes are atomic; job execution is deduplicated and locked per media path.
- The Docker services drop Linux capabilities and run without root privileges.

See [SECURITY.md](SECURITY.md) for private vulnerability reporting guidance.

## Development

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[sync,dev]'
ruff check .
pytest
```

The design and trade-offs are documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## Project status

The first beta intentionally targets one Plex server and one worker. Planned follow-ups include a
translation cache, per-library language-learning profiles, richer status reporting, and faster
incremental Plex scans.

SubFlow is an independent project and is not affiliated with Plex, Synology, subtitle providers, or
translation model providers.

## License

MIT
