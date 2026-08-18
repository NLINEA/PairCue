# Contributing

Thank you for helping improve PairCue.

1. Open an issue before a large behavioral or architectural change.
2. Add or update tests for bug fixes and features.
3. Run `ruff check .` and `pytest` before opening a pull request.
4. Keep Download Station credentials and code paths isolated from the subtitle service.
5. Never commit media, subtitles you do not have permission to share, tokens, passwords, or logs
   containing private library information.
6. Do not copy, port, translate, or closely adapt source code from another subtitle product. Build
   from PairCue's specifications, standards, and official API documentation.
7. Follow [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md). New runtime dependencies must pass the
   license gate and include an updated notice when appropriate.
8. Sign every commit with `git commit -s`. The sign-off certifies the
   [Developer Certificate of Origin](https://developercertificate.org/); contributors remain
   responsible for the provenance of AI-assisted changes as well.

Pull requests containing copied code, unlicensed media or subtitle samples, or dependencies with
unknown provenance will not be accepted.
