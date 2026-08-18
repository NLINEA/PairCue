# Changelog

## 0.1.0b11 - 2026-08-18

- Add a real platform-first product screenshot and a shorter five-second GitHub introduction so
  first-time visitors can understand PairCue before reading installation details.
- Keep the private setup token in a URL fragment only, remove it from browser history immediately,
  and send it to the local setup server through the Authorization header rather than request URLs.
- Stop persisting the optional Download Station token in browser storage; it now stays in page
  memory and must be pasted again after a refresh.
- Add response-header clickjacking protection and a server-delivered Content Security Policy to
  the visual setup wizard.
- Publish SHA-256 checksums alongside every tagged desktop release archive.

## 0.1.0b10 - 2026-08-18

- Turn first-run setup into three progressive stages: platform, first result, then only the
  settings needed for that result. The platform and its primary action now fit in a 900px desktop
  viewport instead of being buried below the marketing introduction.
- Add Kodi, Infuse, VLC, NAS, and local media as an explicit **Other players** platform choice.
- Name bilingual sidecars `Movie.mul.srt` using the ISO 639-2 multiple-languages code. Stop using
  `.cc.srt`, which Plex and Jellyfin interpret as hearing-impaired captions.
- Give Quick Pair the most prominent zero-setup path after platform selection while keeping one
  video and library automation as clear alternatives.
- Add a self-contained PairCue favicon and verify the progressive flow at desktop and mobile
  widths without remote assets, horizontal overflow, HTTP errors, or console errors.

## 0.1.0b9 - 2026-08-18

- Add **Quick Pair** to the desktop setup so a first-time user can choose two existing SRT files
  and receive a bilingual track without an account, API key, media server, or terminal command.
- Use role-specific native file windows for the spoken and learning subtitle, then reveal the
  finished file in the operating system's file manager.
- Keep Quick Pair local and origin-protected, return only the output filename to the browser, and
  limit each selected input to 16 MB.
- Never overwrite either input or an earlier paired result; use a new numbered output when a
  `.cc.srt` already exists.

## 0.1.0b8 - 2026-08-18

- Add a self-contained local dashboard with live queue totals, recent filename-only results, and a
  one-click library scan.
- Make desktop library setup verify its selected media platform before automatically opening the
  dashboard, with useful credential, network, folder, and permission failures shown in setup.
- Add a native media-folder chooser and keep failed platform checks editable instead of saving a
  configuration that cannot start.
- Hide container-only port and permission fields from desktop users while retaining them for NAS
  and home-server installs.
- Keep desktop library automation running without Docker or terminal commands and reopen an
  existing library directly on later app launches.
- Add dashboard controls to stop PairCue cleanly or return to visual setup, completing the
  returning-user loop.
- Pass the private dashboard token in a URL fragment, remove it from browser history, and keep it
  out of browser storage and static assets.
- Add narrow-screen dashboard behavior and package-level UI security tests based on rendered
  desktop and mobile QA.

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
