# Changelog

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
