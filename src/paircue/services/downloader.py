from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from babelfish import Language
from subliminal import download_best_subtitles, save_subtitles, scan_video

from paircue.languages import observed_language_tag
from paircue.services.atomic import atomic_write_bytes

log = logging.getLogger(__name__)


class SubliminalDownloader:
    def __init__(self, providers: tuple[str, ...], temporary_root: Path) -> None:
        self.providers = providers
        self.temporary_root = temporary_root
        self.temporary_root.mkdir(parents=True, exist_ok=True)

    def download(self, media_path: Path, languages: set[str]) -> tuple[Path, ...]:
        if not languages:
            return ()
        requested_by_language: dict[Language, str] = {}
        for tag in languages:
            try:
                requested_by_language[Language.fromietf(tag)] = tag
            except (AttributeError, ValueError):
                log.warning("subtitle downloader does not recognize language tag %s", tag)
        if not requested_by_language:
            return ()
        video = scan_video(str(media_path))
        found = download_best_subtitles(
            {video},
            set(requested_by_language),
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
                prefix = f"{media_path.stem}."
                if not candidate.name.startswith(prefix):
                    continue
                observed = candidate.name[len(prefix) : -4]
                try:
                    language = Language.fromietf(observed)
                except (AttributeError, ValueError):
                    continue
                requested_tag = requested_by_language.get(language)
                if requested_tag is None:
                    normalized = observed_language_tag(observed)
                    requested_tag = next(
                        (
                            tag
                            for known, tag in requested_by_language.items()
                            if observed_language_tag(str(known)) == normalized
                        ),
                        None,
                    )
                if requested_tag is None:
                    continue
                target = media_path.parent / f"{media_path.stem}.{requested_tag}.srt"
                atomic_write_bytes(target, candidate.read_bytes())
                outputs.append(target)
                log.info("downloaded %s subtitle for %s", requested_tag, media_path.name)
        return tuple(outputs)
