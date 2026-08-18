# PairCue Desktop beta

PairCue Desktop lets you start without installing Python or learning terminal commands.

1. Open **PairCue**.
2. First, choose where you watch: Plex, Jellyfin, Emby, Kodi, Infuse, VLC, or a media folder.
3. Choose the result you want first: combine two SRTs, try one video, or automate the library.
4. PairCue then shows only the settings needed for that result.

Already have two SRT files? Press **Choose two SRTs**, choose the spoken subtitle and then the
learning subtitle. PairCue creates a new bilingual `.mul.srt` locally, highlights it in the file
manager, and does not require you to finish setup or add any API key.
PairCue then ends that app run cleanly; reopen it whenever you want to pair another set.

For one video, PairCue opens the system file picker and reports progress in the same setup page. A
successful bilingual `.mul.srt` is highlighted in Finder or your file manager. `mul` means
multiple languages and avoids falsely marking the result as hearing-impaired captions.

For library automation, PairCue checks the selected platform and media folder before opening its
private local dashboard. The dashboard shows work in progress and recent results without revealing
full library paths. It can scan immediately, stop PairCue, or return to setup. Reopen the app later
to go straight back to the dashboard. No Docker or terminal command is required for this desktop
flow. Use **Choose folder** instead of typing a path; a failed connection check stays on the setup
page so the address or credential can be corrected before anything is saved.

The beta builds are not yet code-signed. macOS may require right-clicking the app and choosing
**Open** the first time; Windows SmartScreen may show an unrecognized-publisher warning. Do not
download PairCue from unofficial mirrors.

FFmpeg and FFprobe are not bundled because their effective license depends on how they were built.
PairCue can still merge two existing SRT tracks or search and translate downloaded subtitles
without them. Embedded-track extraction, audio synchronization, and speech generation require a
separate FFmpeg installation.

PairCue has no analytics or PairCue account. Provider features use credentials from your own
provider accounts, and the setup stores them only in your private local configuration.
