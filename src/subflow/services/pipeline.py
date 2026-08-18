from __future__ import annotations

import logging
from pathlib import Path

import srt
from opencc import OpenCC

from subflow.languages import opencc_profile
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
    Sidecars,
    bilingual_subtitles,
    clean_spoken_dialogue,
    discover_sidecars,
    find_language_sidecar,
    parse_srt,
    sidecar_path,
    translated_subtitles,
    write_srt,
)
from subflow.services.translator import CompleteTranslator

log = logging.getLogger(__name__)

TRADITIONAL_CHINESE_TARGETS = {"zh-TW", "zh-HK", "zh-Hant"}
SIMPLIFIED_CHINESE_TARGETS = {"zh-CN", "zh-Hans"}


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
        target_language: str = "zh-TW",
    ) -> None:
        self.media_root = media_root
        self.state = state
        self.downloader = downloader
        self.extractor = extractor
        self.synchronizer = synchronizer
        self.translator = translator
        self.glossary = glossary
        self.clean_english_output = clean_english_output
        self.target_language = target_language
        self.locks = KeyedLockPool()
        profile = opencc_profile(target_language)
        self._target_converter = OpenCC(profile) if profile is not None else None

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
        self.extractor.extract(media_path, {"en", *self._download_targets()})
        target = find_language_sidecar(media_path, self.target_language)
        if target is not None:
            return ProcessResult(
                "skipped",
                f"{self.target_language} subtitle already exists",
                (target,),
            )

        if self.translator is None:
            downloaded = self.downloader.download(media_path, self._download_targets())
            for path in downloaded:
                if self.synchronizer is not None:
                    self.synchronizer.sync(media_path, path)
            target = find_language_sidecar(media_path, self.target_language)
            if target is not None:
                return ProcessResult(
                    "completed",
                    f"downloaded {self.target_language} subtitle",
                    (target,),
                )
            sidecars = discover_sidecars(media_path)
            conversion_source = self._conversion_source(sidecars)
            if conversion_source is not None and self._target_converter is not None:
                output = self._convert_to_target(media_path, conversion_source)
                return ProcessResult(
                    "completed",
                    f"converted subtitle to {self.target_language}",
                    (output,),
                )
            raise RuntimeError(
                f"no {self.target_language} subtitle was found and translation is disabled"
            )

        sidecars = discover_sidecars(media_path)
        if sidecars.english is None:
            downloaded = self.downloader.download(media_path, {"en"})
            downloaded_english = next(
                (path for path in downloaded if path.name.endswith(".en.srt")), None
            )
            if downloaded_english is not None and self.synchronizer is not None:
                self.synchronizer.sync(media_path, downloaded_english)
            sidecars = discover_sidecars(media_path)

        if sidecars.english is None:
            raise RuntimeError("no English subtitle is available for translation")

        english = clean_spoken_dialogue(parse_srt(sidecars.english))
        glossary = self.glossary.load(item.show_title or item.title)
        translations = self.translator.translate_all(
            english,
            context=item.context_label,
            glossary=glossary,
        )
        translated = translated_subtitles(english, translations)
        bilingual = bilingual_subtitles(english, translated)

        translated_path = sidecar_path(media_path, self.target_language)
        bilingual_path = sidecar_path(media_path, self.target_language, bilingual=True)
        # Each file is atomic; the target-only file is written last as the completion marker.
        if self.clean_english_output:
            write_srt(sidecars.english, english)
        write_srt(bilingual_path, bilingual)
        write_srt(translated_path, translated)
        return ProcessResult(
            "completed",
            f"translated {len(english)} subtitle cues to {self.target_language}",
            (translated_path, bilingual_path),
        )

    def _download_targets(self) -> set[str]:
        targets = {self.target_language}
        if self.target_language in TRADITIONAL_CHINESE_TARGETS:
            targets.update({"zh-CN", "zh"})
        elif self.target_language in SIMPLIFIED_CHINESE_TARGETS:
            targets.update({"zh-TW", "zh"})
        return targets

    def _conversion_source(self, sidecars: Sidecars) -> Path | None:
        if self.target_language in TRADITIONAL_CHINESE_TARGETS:
            return sidecars.simplified_chinese or sidecars.generic_chinese
        if self.target_language in SIMPLIFIED_CHINESE_TARGETS:
            return sidecars.traditional_chinese or sidecars.generic_chinese
        return None

    def _convert_to_target(self, media_path: Path, source_path: Path) -> Path:
        if self._target_converter is None:
            raise ValueError(f"no script converter is available for {self.target_language}")
        source = parse_srt(source_path)
        converted = [
            srt.Subtitle(
                index=cue.index,
                start=cue.start,
                end=cue.end,
                content=self._target_converter.convert(cue.content),
                proprietary=cue.proprietary,
            )
            for cue in source
        ]
        output = sidecar_path(media_path, self.target_language)
        write_srt(output, converted)
        return output
