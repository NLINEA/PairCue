from __future__ import annotations

import logging
from pathlib import Path

import srt
from opencc import OpenCC

from paircue.languages import opencc_profile
from paircue.models import MediaItem, ProcessResult
from paircue.services.downloader import SubtitleDownloader
from paircue.services.glossary import GlossaryStore
from paircue.services.locks import KeyedLockPool
from paircue.services.media_tools import (
    EmbeddedSubtitleExtractor,
    SubtitleSynchronizer,
    ensure_media_path,
)
from paircue.services.state import StateStore, media_fingerprint
from paircue.services.subtitle_files import (
    Sidecars,
    bilingual_subtitles,
    clean_spoken_dialogue,
    discover_sidecars,
    find_language_sidecar,
    merge_bilingual_subtitles,
    parse_srt,
    sidecar_path,
    translated_subtitles,
    write_srt,
)
from paircue.services.translator import CompleteTranslator

log = logging.getLogger(__name__)

TRADITIONAL_CHINESE_TARGETS = {"zh-TW", "zh-HK", "zh-Hant"}
SIMPLIFIED_CHINESE_TARGETS = {"zh-CN", "zh-Hans"}


class SubtitlePipeline:
    def __init__(
        self,
        *,
        media_root: Path,
        state: StateStore,
        downloader: SubtitleDownloader,
        extractor: EmbeddedSubtitleExtractor,
        synchronizer: SubtitleSynchronizer | None,
        translator: CompleteTranslator | None,
        glossary: GlossaryStore,
        clean_source_output: bool = True,
        source_language: str = "en",
        target_language: str = "zh-TW",
        bilingual_order: str = "target-first",
        bilingual_merge_tolerance_ms: int = 350,
        bilingual_merge_min_match_ratio: float = 0.7,
    ) -> None:
        self.media_root = media_root
        self.state = state
        self.downloader = downloader
        self.extractor = extractor
        self.synchronizer = synchronizer
        self.translator = translator
        self.glossary = glossary
        self.clean_source_output = clean_source_output
        self.source_language = source_language
        self.target_language = target_language
        self.bilingual_order = bilingual_order
        self.bilingual_merge_tolerance_ms = bilingual_merge_tolerance_ms
        self.bilingual_merge_min_match_ratio = bilingual_merge_min_match_ratio
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
        self.extractor.extract(media_path, {self.source_language, *self._download_targets()})
        target = find_language_sidecar(media_path, self.target_language)
        bilingual = find_language_sidecar(media_path, self.target_language, bilingual=True)
        if target is not None and bilingual is not None:
            return ProcessResult(
                "skipped",
                f"{self.target_language} output already exists",
                (target, bilingual),
            )

        source_path = find_language_sidecar(media_path, self.source_language)
        merge_attempted = False
        if source_path is not None and target is not None:
            merge_attempted = True
            try:
                return self._merge_existing_pair(media_path, source_path, target)
            except ValueError as exc:
                log.warning("existing subtitle pair could not be merged: %s", exc)

        if self.translator is None:
            if target is not None:
                message = (
                    f"kept {self.target_language} subtitle; bilingual timing match was too low"
                    if merge_attempted
                    else f"{self.target_language} subtitle already exists"
                )
                return ProcessResult(
                    "completed",
                    message,
                    (target,),
                )
            downloaded = self.downloader.download(item, self._download_targets())
            for path in downloaded:
                if self.synchronizer is not None:
                    self.synchronizer.sync(media_path, path)
            target = find_language_sidecar(media_path, self.target_language)
            if target is not None:
                source_path = find_language_sidecar(media_path, self.source_language)
                if source_path is not None and not merge_attempted:
                    try:
                        return self._merge_existing_pair(media_path, source_path, target)
                    except ValueError as exc:
                        log.warning("downloaded subtitle pair could not be merged: %s", exc)
                return ProcessResult(
                    "completed",
                    f"downloaded {self.target_language} subtitle",
                    (target,),
                )
            sidecars = discover_sidecars(media_path)
            conversion_source = self._conversion_source(sidecars)
            if conversion_source is not None and self._target_converter is not None:
                output = self._convert_to_target(media_path, conversion_source)
                source_path = find_language_sidecar(media_path, self.source_language)
                if source_path is not None:
                    try:
                        return self._merge_existing_pair(media_path, source_path, output)
                    except ValueError as exc:
                        log.warning("converted subtitle pair could not be merged: %s", exc)
                return ProcessResult(
                    "completed",
                    f"converted subtitle to {self.target_language}",
                    (output,),
                )
            raise RuntimeError(
                f"no {self.target_language} subtitle was found and translation is disabled"
            )

        if source_path is None:
            self.downloader.download(item, {self.source_language})
            source_path = find_language_sidecar(media_path, self.source_language)
        if source_path is None:
            raise RuntimeError(f"no {self.source_language} subtitle is available for translation")
        if target is not None and not merge_attempted:
            try:
                return self._merge_existing_pair(media_path, source_path, target)
            except ValueError as exc:
                log.warning("existing subtitle pair could not be merged: %s", exc)
        synchronized = False
        if self.synchronizer is not None:
            synchronized = self.synchronizer.sync(media_path, source_path)

        source = clean_spoken_dialogue(parse_srt(source_path))
        glossary = self.glossary.load(item.show_title or item.title)
        translations = self.translator.translate_all(
            source,
            context=item.context_label,
            glossary=glossary,
        )
        translated = translated_subtitles(source, translations)
        bilingual_output = bilingual_subtitles(
            source,
            translated,
            order=self.bilingual_order,
        )

        translated_path = sidecar_path(media_path, self.target_language)
        bilingual_path = sidecar_path(media_path, self.target_language, bilingual=True)
        # Each file is atomic; bilingual is last so it marks a complete learning-language pair.
        if self.clean_source_output:
            write_srt(source_path, source)
        write_srt(translated_path, translated)
        write_srt(bilingual_path, bilingual_output)
        action = "aligned and translated" if synchronized else "translated"
        return ProcessResult(
            "completed",
            f"{action} {len(source)} cues from {self.source_language} to {self.target_language}",
            (translated_path, bilingual_path),
        )

    def _merge_existing_pair(
        self,
        media_path: Path,
        source_path: Path,
        target_path: Path,
    ) -> ProcessResult:
        if self.synchronizer is not None:
            self.synchronizer.sync(media_path, source_path)
            self.synchronizer.sync(media_path, target_path)
        source = clean_spoken_dialogue(parse_srt(source_path))
        target = clean_spoken_dialogue(parse_srt(target_path))
        merged = merge_bilingual_subtitles(
            source,
            target,
            order=self.bilingual_order,
            tolerance_ms=self.bilingual_merge_tolerance_ms,
            min_match_ratio=self.bilingual_merge_min_match_ratio,
        )
        bilingual_path = sidecar_path(media_path, self.target_language, bilingual=True)
        if self.clean_source_output:
            write_srt(source_path, source)
        write_srt(bilingual_path, merged.subtitles)
        return ProcessResult(
            "completed",
            "merged existing subtitle tracks "
            f"({merged.source_match_ratio:.0%}/{merged.target_match_ratio:.0%} matched)",
            (target_path, bilingual_path),
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
