# SubFlow

SubFlow is a Plex-first subtitle automation companion for Traditional Chinese viewers. It finds or
extracts an English subtitle, synchronizes it, translates every cue with an OpenAI-compatible model,
and writes Plex-friendly Traditional Chinese and bilingual sidecars.

> Beta software. Back up a small test library before enabling it on your full media collection.

## What it writes

- `Movie.en.srt` — English base when one is downloaded or extracted.
- `Movie.zh-TW.srt` — Traditional Chinese.
- `Movie.zh-TW.cc.srt` — Traditional Chinese above English.

Translation is all-or-nothing: SubFlow does not publish an output when even one cue is missing.
By default, the English sidecar is also rewritten atomically with non-dialogue cues removed; set
`SUBFLOW_CLEAN_ENGLISH_OUTPUT=false` to preserve it exactly.

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
translation cache, `zh-HK`, richer status reporting, and faster incremental Plex scans.

SubFlow is an independent project and is not affiliated with Plex, Synology, subtitle providers, or
translation model providers.

## License

MIT
