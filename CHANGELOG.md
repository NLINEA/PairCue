# Changelog

## 0.1.0b7 - 2026-08-18

- Make platform selection the first setup decision, before choosing a one-video trial or
  full-library automation.
- Keep the first video's file selection, processing progress, failure guidance, and completed
  bilingual result in one visual setup journey.
- Add self-contained macOS, Windows, and Linux desktop release builds so first-time users do not
  need Python or terminal commands.
- Store desktop settings in the operating system's private application-data folder while retaining
  working-directory configuration for source installs.
- Include a runtime SBOM, Python license, and collected dependency license files in every desktop
  archive without bundling FFmpeg, models, media, or subtitles.
- Treat missing video tools as optional until speech transcription is enabled and add native video
  filters plus a second Linux file-picker fallback.
- Add a no-console-safe desktop entry point so double-click launches do not depend on terminal
  streams being present.

## 0.1.0b6 - 2026-08-18

- Add `paircue setup`, a packaged private visual wizard that saves a ready-to-use `paircue.env`
  through a token-protected localhost connection without analytics or browser storage.
- Open the setup wizard when `paircue` is run without a subcommand, so first-time users do not need
  to learn the CLI structure.
- Add `paircue learn` for running the complete subtitle pipeline on one local video without a
  media server or persistent state database.
- Make the onboarding journey start with one video, then graduate to full-library automation.
- Show video-tool readiness in the local setup page and reveal the finished subtitle in the native
  file manager after the first guided run.
- Search for both configured languages in no-translation mode and merge them when timing coverage
  passes the confidence threshold.
- Use one environment file for Docker host and PairCue settings, with the status API bound to a
  localhost-only published port.

## 0.1.0b5 - 2026-08-18

- Complete the fallback chain from existing subtitle to exact-hash search, metadata search,
  timestamped speech transcription, translation, and bilingual SRT.
- Add bounded FLAC segmentation for OpenAI-compatible transcription endpoints with atomic
  all-or-nothing output.
- Add `paircue pair` for a zero-configuration two-SRT trial.
- Add `paircue doctor` for secret-safe configuration and dependency checks.
- Add a protected `/v1/status` endpoint with queue counts and recent filename-only results.
- Centralize runtime version headers and close owned HTTP clients during shutdown.

## 0.1.0b4 - 2026-08-18

- Replace Subliminal with an independently written OpenSubtitles REST API adapter.
- Replace ffsubsync with PairCue's own conservative audio-alignment implementation.
- Add runtime license policy enforcement, third-party notices, CycloneDX SBOM generation, DCO
  checks, and contribution provenance rules.
