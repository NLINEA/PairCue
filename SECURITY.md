# Security policy

## Supported versions

Only the newest beta or stable release receives security fixes.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Use GitHub private vulnerability reporting after
the repository is published. Include the affected version, impact, reproduction steps, and any
suggested mitigation. Never include live media-server, NAS, or translation credentials.

## Deployment boundary

PairCue is designed for a trusted home network. Do not expose either service directly to the public
internet. Use a VPN or an authenticated reverse proxy and keep the bearer tokens separate.

The visual setup wizard binds to a random `127.0.0.1` port and accepts configuration writes only
with its one-time URL token and matching local Origin. It loads no remote assets. Generated
`paircue.env` files and automatic backups use owner-only permissions; they contain secrets and must
never be committed or shared.

Desktop Quick Pair accepts actions only from the tokenized same-origin setup page. Its two SRT
inputs are read directly from paths returned by native operating-system file windows, are limited
to 16 MB each, and are never uploaded. The browser receives only the new output filename.

Frozen desktop apps store that file under `~/Library/Application Support/PairCue` on macOS,
`%APPDATA%\\PairCue` on Windows, or `$XDG_CONFIG_HOME/paircue` (normally `~/.config/paircue`) on
Linux. Source installs retain `paircue.env` in the folder where setup was started.

The dashboard also binds to `127.0.0.1` by default. Desktop launches pass its bearer token in the
URL fragment, which is not sent in the HTTP request, then remove it from browser history before the
first authenticated API call. The page keeps the token in memory only and displays filenames rather
than full media paths. Do not expose the dashboard port directly to the internet.

When transcription is enabled, PairCue sends extracted audio chunks to the configured endpoint.
When translation is enabled, it sends subtitle dialogue to the configured endpoint. These features
are disabled or unconfigured by default; review the provider's access, retention, and privacy terms
before enabling either one.
