# PairCue security best-practices review

Review date: 2026-08-19  
Scope: PairCue source, browser UI, configuration, provider clients, media processing, tests,
Git history, GitHub workflows, dependencies, and published `v0.1.0b13` desktop archives.

## Summary

No hard-coded API key, access token, private key, local assistant context, or known vulnerable
Python dependency was found. The review identified six concrete hardening issues; all six were
fixed in the source prepared for the next release. PairCue now keeps AI use explicit, limits the
data in each request, rejects unsafe remote AI transport, validates the second AI pass before any
subtitle write, and keeps video/timing outside the translation provider.

This review is evidence of bounded checks, not a guarantee that the software has no vulnerability.

## Findings

### PC-SEC-001 — Remote AI credentials and content could use plaintext HTTP

- Severity: High
- Status: Fixed
- Evidence: `src/paircue/config.py:129-134` previously accepted `http` for every configured
  translation or transcription host. `src/paircue/config.py:162-179` now permits keyless HTTP only
  for a loopback endpoint and requires a key for remote AI providers.
- Impact: A remote HTTP endpoint could expose the provider key, subtitle dialogue, or generated
  audio to a network observer.
- Fix: Remote AI endpoints must use HTTPS. `localhost`, `127.0.0.0/8`, and `::1` remain available
  for a model running on the same device. Credentials are omitted entirely when no local key is
  configured.
- Tests: `tests/test_config.py` covers remote rejection and IPv4, IPv6, and `.localhost` cases;
  `tests/test_translator.py` confirms a keyless local request has no Authorization header.

### PC-SEC-002 — A subtitle symlink could read text outside the media library

- Severity: Medium
- Status: Fixed
- Evidence: `src/paircue/services/subtitle_files.py:128-141` now refuses symbolic links before
  reading SRT data and bounds every input to 16 MiB and 100,000 cues.
- Impact: If an attacker could place a matching symlink in a writable media directory, PairCue
  could parse a text file outside that directory and, when translation was enabled, send its text
  to the configured provider.
- Fix: Reject subtitle symlinks and oversized subtitle inputs before parsing or AI use.
- Tests: `tests/test_subtitle_files.py` covers both symlink and size-limit rejection.

### PC-SEC-003 — Crafted media could ask FFmpeg to open a network protocol

- Severity: Medium
- Status: Fixed
- Evidence: `src/paircue/services/media_tools.py:32-33,61-63,106-109,171-174` and
  `src/paircue/services/transcriber.py:24-27,114-117` now restrict FFmpeg and FFprobe inputs to
  `file,crypto,data` protocols.
- Impact: A specially constructed playlist or media container could otherwise make the local
  decoder attempt a network request, creating an SSRF or local-network probing path.
- Fix: Allow only local-media protocols for probing, embedded-subtitle extraction, audio alignment,
  and speech-generation audio extraction.
- Tests: `tests/test_media_tools.py` and `tests/test_transcriber.py` assert the whitelist reaches
  the decoder command.

### PC-SEC-004 — Translation-provider responses were not size bounded

- Severity: Medium
- Status: Fixed
- Evidence: `src/paircue/services/translator.py:163-211` streams each provider response and stops
  above 2 MiB. `src/paircue/services/translator.py:213-225` also bounds individual cue and batch
  input sizes.
- Impact: A broken or hostile compatible endpoint could return an extremely large response and
  exhaust service memory.
- Fix: Stream with a hard limit, retain redirect refusal, and reject malformed, incomplete, extra,
  duplicate, empty, or oversized data.
- Tests: `tests/test_translator.py` covers the request data contract, exact cue coverage, empty-key
  header behavior, and fail-closed final-check output.

### PC-SEC-005 — GitHub Actions used movable version tags

- Severity: Medium
- Status: Fixed
- Evidence: `.github/workflows/ci.yml:19-61` and
  `.github/workflows/desktop-release.yml:16-93` now reference full verified commit SHAs for every
  third-party action, with the major tag retained in a comment for Dependabot updates.
- Impact: A moved or compromised action tag would have changed CI or release code without a PairCue
  commit.
- Fix: Pin checkout, Python setup, artifact upload, and artifact download actions by full SHA.

### PC-SEC-006 — Desktop build cleanup paths were accepted from command-line input

- Severity: Critical in a shared or automated build environment
- Status: Fixed
- Evidence: `scripts/build_desktop.py` previously accepted custom distribution, work, and staging
  directories before recursively clearing them and smoke-testing the resulting executable.
- Impact: Although `_scoped` confined the paths to the repository, an operator or compromised CI
  invocation could redirect destructive cleanup or make the release test run an unexpected file
  created under another repository subdirectory.
- Fix: Release build directories are now fixed constants under the repository. The builder no
  longer accepts path arguments; scope checks remain as defense in depth.
- Tests: `tests/test_release.py` retains boundary tests for `_scoped`.

## AI final quality gate

The new gate is deliberately narrow:

- `src/paircue/services/translator.py:96-161` sends source text, draft translation, language names,
  style, title or episode context, and glossary only. It does not receive media bytes, timing,
  local paths, server tokens, or a key in the JSON body.
- Subtitle and context fields are declared untrusted data in the system instruction.
- Exact cue IDs, non-empty output, response size, and language-script normalization are checked
  after both passes.
- `src/paircue/services/pipeline.py` writes translated and bilingual files only after the complete
  translator call returns. A failed final check therefore produces neither output.
- Merging two existing language tracks remains local and does not silently invoke AI.

## Verification performed

- Secret scan of tracked files and complete local Git history.
- Secret scan and checksum verification of all four extracted `v0.1.0b13` desktop archives.
- Ruff, strict mypy, 154 pytest tests, and 77.69% statement coverage.
- `pip-audit`: no known vulnerable installed dependency.
- Runtime-license and documentation/link validation.
- GitHub Dependabot alerts: zero open at review time.
- GitHub secret-scanning alerts: zero open at review time; push protection is enabled.
- GitHub CodeQL default setup was enabled with extended queries for Python, JavaScript/TypeScript,
  and Actions. Its initial scan completed successfully. The new commit must be rescanned and every
  remaining result fixed or documented and dismissed before the next release is considered done.

## Residual risks and release gates

### PC-SEC-R01 — Desktop binaries are not code signed

- Severity: Medium distribution risk
- Status: Open, disclosed
- Mitigation: Releases are built by GitHub Actions, contain SHA-256 checksums, and are scanned
  before upload. README warnings tell users to download only from the official repository.
- Recommended next step: Sign and notarize macOS builds and sign Windows builds before leaving beta.

### PC-SEC-R02 — Enhanced GitHub secret-pattern options are unavailable

- Severity: Low operational gap
- Status: Open
- Evidence: Standard secret scanning and push protection are enabled. GitHub accepted but did not
  enable non-provider patterns or validity checks for this personal public repository.
- Mitigation: PairCue's own history and release scanners also check credential formats, private
  keys, local paths, and private AI-context markers without printing suspected values.

### Release gate

Do not publish the next desktop beta until CI, CodeQL, secret/history scan, dependency audit,
four-platform smoke builds, archive scan, and checksum verification are all green.
