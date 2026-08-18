from __future__ import annotations

import logging
from pathlib import Path

import srt
from opencc import OpenCC

from subflow.models import MediaItem, ProcessResult
from subflow.services.downloader import SubliminalDownloader
from subflow.services.glossary import GlossaryStore
from subflow.services.locks import KeyedLockPool
from subflow.services.media_tools import (
    EmbeddedSubtitleExtractor,
    SubtitleSynchronizer,
    ensure_media_path,
)
from subflow.services.state import StateStore, media_fingerprint
from subflow.services.subtitle_files import (
    SubtitleLanguage,
    bilingual_subtitles,
    clean_spoken_dialogue,
    discover_sidecars,
    parse_srt,
    translated_subtitles,
    write_srt,
)
from subflow.services.translator import CompleteTranslator

log = logging.getLogger(__name__)


class SubtitlePipeline:
    def __init__(
        self,
        *,
        media_root: Path,
        state: StateStore,
        downloader: SubliminalDownloader,
        extractor: EmbeddedSubtitleExtractor,
        synchronizer: SubtitleSynchronizer | None,
        translator: CompleteTranslator | None,
        glossary: GlossaryStore,
        clean_english_output: bool = True,
    ) -> None:
        self.media_root = media_root
        self.state = state
        self.downloader = downloader
        self.extractor = extractor
        self.synchronizer = synchronizer
        self.translator = translator
        self.glossary = glossary
        self.clean_english_output = clean_english_output
        self.locks = KeyedLockPool()
        self._traditional = OpenCC("s2twp")

    def process(self, item: MediaItem) -> ProcessResult:
        try:
            media_path = ensure_media_path(item.path, self.media_root)
            fingerprint = media_fingerprint(media_path)
        except Exception as exc:
            return ProcessResult("failed", f"{type(exc).__name__}: {exc}")
        with self.locks.acquire(str(media_path)):
            self.state.record(media_path, fingerprint, "processing", item.context_label)
            try:
                result = self._process_locked(item, media_path)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.state.record(media_path, fingerprint, "failed", message)
                log.exception("subtitle processing failed for %s", item.context_label)
                return ProcessResult("failed", message)
            self.state.record(media_path, fingerprint, result.status, result.message)
            return result

    def _process_locked(self, item: MediaItem, media_path: Path) -> ProcessResult:
        self.extractor.extract(media_path)
        sidecars = discover_sidecars(media_path)
        downloaded_english: Path | None = None

        if sidecars.english is None:
            downloaded = self.downloader.download(media_path, {SubtitleLanguage.ENGLISH})
            downloaded_english = next(
                (path for path in downloaded if path.name.endswith(".en.srt")), None
            )
            if downloaded_english is not None and self.synchronizer is not None:
                self.synchronizer.sync(media_path, downloaded_english)
            sidecars = discover_sidecars(media_path)

        if sidecars.traditional_chinese is not None:
            return ProcessResult(
                "skipped",
                "Traditional Chinese subtitle already exists",
                (sidecars.traditional_chinese,),
            )

        if self.translator is None:
            downloaded = self.downloader.download(
                media_path,
                {
                    SubtitleLanguage.TRADITIONAL_CHINESE,
                    SubtitleLanguage.SIMPLIFIED_CHINESE,
                },
            )
            for path in downloaded:
                if self.synchronizer is not None:
                    self.synchronizer.sync(media_path, path)
            sidecars = discover_sidecars(media_path)
            if sidecars.traditional_chinese is not None:
                return ProcessResult(
                    "completed",
                    "downloaded Traditional Chinese subtitle",
                    (sidecars.traditional_chinese,),
                )
            simplified = sidecars.simplified_chinese or sidecars.generic_chinese
            if simplified is not None:
                output = self._convert_to_traditional(media_path, simplified)
                return ProcessResult("completed", "converted subtitle to zh-TW", (output,))
            raise RuntimeError("no Chinese subtitle was found and translation is disabled")

        if sidecars.english is None:
            raise RuntimeError("no English subtitle is available for translation")

        english = clean_spoken_dialogue(parse_srt(sidecars.english))
        glossary = self.glossary.load(item.show_title or item.title)
        translations = self.translator.translate_all(
            english,
            context=item.context_label,
            glossary=glossary,
        )
        chinese = translated_subtitles(english, translations)
        bilingual = bilingual_subtitles(english, chinese)

        zh_path = media_path.parent / f"{media_path.stem}.zh-TW.srt"
        bilingual_path = media_path.parent / f"{media_path.stem}.zh-TW.cc.srt"
        # Each file is atomic, and zh-TW is written last so it acts as the completion marker.
        if self.clean_english_output:
            write_srt(sidecars.english, english)
        write_srt(bilingual_path, bilingual)
        write_srt(zh_path, chinese)
        return ProcessResult(
            "completed",
            f"translated {len(english)} subtitle cues",
            (zh_path, bilingual_path),
        )

    def _convert_to_traditional(self, media_path: Path, source_path: Path) -> Path:
        source = parse_srt(source_path)
        converted = [
            srt.Subtitle(
                index=cue.index,
                start=cue.start,
                end=cue.end,
                content=self._traditional.convert(cue.content),
                proprietary=cue.proprietary,
            )
            for cue in source
        ]
        output = media_path.parent / f"{media_path.stem}.zh-TW.srt"
        write_srt(output, converted)
        return output
