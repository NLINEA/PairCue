from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import srt

from subflow.languages import language_matches
from subflow.services.atomic import atomic_write_text


class SubtitleLanguage(StrEnum):
    ENGLISH = "en"
    TRADITIONAL_CHINESE = "zh-TW"
    SIMPLIFIED_CHINESE = "zh-CN"
    GENERIC_CHINESE = "zh"


LANGUAGE_TAGS: dict[str, SubtitleLanguage] = {
    "en": SubtitleLanguage.ENGLISH,
    "eng": SubtitleLanguage.ENGLISH,
    "zh-tw": SubtitleLanguage.TRADITIONAL_CHINESE,
    "zht": SubtitleLanguage.TRADITIONAL_CHINESE,
    "cht": SubtitleLanguage.TRADITIONAL_CHINESE,
    "zh-hant": SubtitleLanguage.TRADITIONAL_CHINESE,
    "traditional": SubtitleLanguage.TRADITIONAL_CHINESE,
    "zh-cn": SubtitleLanguage.SIMPLIFIED_CHINESE,
    "zhs": SubtitleLanguage.SIMPLIFIED_CHINESE,
    "chs": SubtitleLanguage.SIMPLIFIED_CHINESE,
    "zh-hans": SubtitleLanguage.SIMPLIFIED_CHINESE,
    "simplified": SubtitleLanguage.SIMPLIFIED_CHINESE,
    "zh": SubtitleLanguage.GENERIC_CHINESE,
    "zho": SubtitleLanguage.GENERIC_CHINESE,
    "chi": SubtitleLanguage.GENERIC_CHINESE,
}

SUPPORTED_EXTENSIONS = {".srt"}
MUSIC_MARKS = re.compile(r"[♪♫♬♩]")
BRACKETED_EFFECT = re.compile(r"\s*[\[【][^\]】]*[\]】]\s*")
PARENTHESIZED_EFFECT = re.compile(r"\s*[（(][^）)]*[）)]\s*")
SPEAKER_TAG = re.compile(r"^\s*[\[【][^\]】]{1,40}[\]】]\s*:?\s*")
WHITESPACE = re.compile(r"[ \t]+")


@dataclass(frozen=True, slots=True)
class Sidecars:
    english: Path | None = None
    traditional_chinese: Path | None = None
    simplified_chinese: Path | None = None
    generic_chinese: Path | None = None
    bilingual: Path | None = None


def classify_sidecar(media_path: Path, subtitle_path: Path) -> SubtitleLanguage | None:
    if subtitle_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None
    prefix = f"{media_path.stem}."
    if not subtitle_path.name.startswith(prefix):
        return None
    tag = subtitle_path.name[len(prefix) : -len(subtitle_path.suffix)].lower()
    if tag in {"zh-tw.cc", "bilingual"}:
        return None
    return LANGUAGE_TAGS.get(tag)


def discover_sidecars(media_path: Path) -> Sidecars:
    values: dict[SubtitleLanguage, Path] = {}
    bilingual: Path | None = None
    for candidate in media_path.parent.glob(f"{media_path.stem}.*.srt"):
        tag = candidate.name[len(media_path.stem) + 1 : -4].lower()
        if tag in {"zh-tw.cc", "bilingual"}:
            bilingual = candidate
            continue
        language = classify_sidecar(media_path, candidate)
        if language is not None:
            values.setdefault(language, candidate)
    bare = media_path.with_suffix(".srt")
    if bare.exists():
        values.setdefault(SubtitleLanguage.ENGLISH, bare)
    return Sidecars(
        english=values.get(SubtitleLanguage.ENGLISH),
        traditional_chinese=values.get(SubtitleLanguage.TRADITIONAL_CHINESE),
        simplified_chinese=values.get(SubtitleLanguage.SIMPLIFIED_CHINESE),
        generic_chinese=values.get(SubtitleLanguage.GENERIC_CHINESE),
        bilingual=bilingual,
    )


def find_language_sidecar(
    media_path: Path,
    language: str,
    *,
    bilingual: bool = False,
) -> Path | None:
    """Find a Plex sidecar matching a requested language tag or known alias."""

    prefix_length = len(media_path.stem) + 1
    for candidate in media_path.parent.glob(f"{media_path.stem}.*.srt"):
        tag = candidate.name[prefix_length:-4]
        is_bilingual = tag.lower().endswith(".cc")
        if bilingual != is_bilingual:
            continue
        if is_bilingual:
            tag = tag[:-3]
        if language_matches(tag, language):
            return candidate
    return None


def sidecar_path(media_path: Path, language: str, *, bilingual: bool = False) -> Path:
    suffix = ".cc.srt" if bilingual else ".srt"
    return media_path.parent / f"{media_path.stem}.{language}{suffix}"


def parse_srt(path: Path) -> list[srt.Subtitle]:
    content = path.read_text(encoding="utf-8-sig", errors="strict")
    subtitles = list(srt.parse(content, ignore_errors=False))
    if not subtitles:
        raise ValueError(f"subtitle file contains no valid cues: {path.name}")
    return subtitles


def clean_spoken_dialogue(subtitles: list[srt.Subtitle]) -> list[srt.Subtitle]:
    cleaned: list[srt.Subtitle] = []
    for cue in subtitles:
        if MUSIC_MARKS.search(cue.content):
            continue
        text = SPEAKER_TAG.sub("", cue.content)
        text = BRACKETED_EFFECT.sub(" ", text)
        text = PARENTHESIZED_EFFECT.sub(" ", text)
        lines = [WHITESPACE.sub(" ", line).strip() for line in text.splitlines()]
        text = "\n".join(line for line in lines if line).strip()
        if not text:
            continue
        cleaned.append(
            srt.Subtitle(
                index=len(cleaned) + 1,
                start=cue.start,
                end=cue.end,
                content=text,
                proprietary=cue.proprietary,
            )
        )
    if not cleaned:
        raise ValueError("dialogue cleaning removed every subtitle cue")
    return cleaned


def write_srt(path: Path, subtitles: list[srt.Subtitle]) -> None:
    normalized = [
        srt.Subtitle(
            index=index,
            start=cue.start,
            end=cue.end,
            content=cue.content.strip(),
            proprietary=cue.proprietary,
        )
        for index, cue in enumerate(subtitles, start=1)
    ]
    atomic_write_text(path, srt.compose(normalized, reindex=False, strict=True))


def translated_subtitles(
    source: list[srt.Subtitle], translations: dict[int, str]
) -> list[srt.Subtitle]:
    expected = set(range(len(source)))
    if set(translations) != expected:
        missing = sorted(expected - set(translations))
        raise ValueError(f"translation coverage is incomplete; missing cue IDs: {missing[:10]}")
    return [
        srt.Subtitle(
            index=index + 1,
            start=cue.start,
            end=cue.end,
            content=translations[index].strip(),
        )
        for index, cue in enumerate(source)
    ]


def bilingual_subtitles(
    source: list[srt.Subtitle], translated: list[srt.Subtitle]
) -> list[srt.Subtitle]:
    if len(source) != len(translated):
        raise ValueError("source and translated subtitle counts differ")
    output: list[srt.Subtitle] = []
    for index, (english, chinese) in enumerate(zip(source, translated, strict=True), start=1):
        if english.start != chinese.start or english.end != chinese.end:
            raise ValueError("source and translated timings differ")
        output.append(
            srt.Subtitle(
                index=index,
                start=english.start,
                end=english.end,
                content=f"{chinese.content.strip()}\n{english.content.strip()}",
            )
        )
    return output
