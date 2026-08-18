from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from babelfish import Language
from subliminal import download_best_subtitles, save_subtitles, scan_video

from subflow.services.atomic import atomic_write_bytes
from subflow.services.subtitle_files import SubtitleLanguage, classify_sidecar

log = logging.getLogger(__name__)

SUBLIMINAL_LANGUAGES = {
    SubtitleLanguage.ENGLISH: Language("eng"),
    SubtitleLanguage.TRADITIONAL_CHINESE: Language("zho", country="TW"),
    SubtitleLanguage.SIMPLIFIED_CHINESE: Language("zho", country="CN"),
    SubtitleLanguage.GENERIC_CHINESE: Language("zho"),
}


class SubliminalDownloader:
    def __init__(self, providers: tuple[str, ...], temporary_root: Path) -> None:
        self.providers = providers
        self.temporary_root = temporary_root
        self.temporary_root.mkdir(parents=True, exist_ok=True)

    def download(self, media_path: Path, languages: set[SubtitleLanguage]) -> tuple[Path, ...]:
        if not languages:
            return ()
        video = scan_video(str(media_path))
        requested = {SUBLIMINAL_LANGUAGES[language] for language in languages}
        found = download_best_subtitles(
            {video},
            requested,
            providers=list(self.providers),
            only_one=True,
        ).get(video, [])
        if not found:
            return ()

        outputs: list[Path] = []
        with tempfile.TemporaryDirectory(dir=self.temporary_root) as directory:
            save_subtitles(
                video,
                found,
                single=False,
                directory=directory,
                encoding="utf-8",
                subtitle_format="srt",
                extension="srt",
                language_format="ietf",
            )
            for candidate in Path(directory).glob("*.srt"):
                language = classify_sidecar(media_path, candidate)
                if language is None or language not in languages:
                    continue
                target = media_path.parent / f"{media_path.stem}.{language.value}.srt"
                atomic_write_bytes(target, candidate.read_bytes())
                outputs.append(target)
                log.info("downloaded %s subtitle for %s", language.value, media_path.name)
        return tuple(outputs)
