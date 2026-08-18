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

When transcription is enabled, PairCue sends extracted audio chunks to the configured endpoint.
When translation is enabled, it sends subtitle dialogue to the configured endpoint. These features
are disabled or unconfigured by default; review the provider's access, retention, and privacy terms
before enabling either one.
