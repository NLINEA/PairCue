# Security policy

## Supported versions

Only the newest beta or stable release receives security fixes.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Use GitHub private vulnerability reporting after
the repository is published. Include the affected version, impact, reproduction steps, and any
suggested mitigation. Never include live Plex, NAS, or translation credentials.

## Deployment boundary

SubFlow is designed for a trusted home network. Do not expose either service directly to the public
internet. Use a VPN or an authenticated reverse proxy and keep the bearer tokens separate.

