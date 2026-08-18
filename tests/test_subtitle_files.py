from datetime import timedelta
from pathlib import Path

import pytest
import srt

from paircue.services.subtitle_files import (
    SubtitleLanguage,
    bilingual_subtitles,
    clean_spoken_dialogue,
    discover_sidecars,
    find_language_sidecar,
    merge_bilingual_subtitles,
    sidecar_path,
    translated_subtitles,
)


def test_simplified_is_not_misclassified_as_traditional(tmp_path: Path) -> None:
    media = tmp_path / "Movie.mkv"
    media.write_bytes(b"video")
    (tmp_path / "Movie.zh-CN.srt").write_text("x", encoding="utf-8")

    sidecars = discover_sidecars(media)

    assert sidecars.simplified_chinese == tmp_path / "Movie.zh-CN.srt"
    assert sidecars.traditional_chinese is None


def test_spoken_dialogue_cleanup_keeps_alignment() -> None:
    cues = [
        srt.Subtitle(1, timedelta(seconds=0), timedelta(seconds=1), "♪ theme song ♪"),
        srt.Subtitle(
            2,
            timedelta(seconds=1),
            timedelta(seconds=2),
            "[NARRATOR]: Hello [door slams] who is there?",
        ),
    ]

    cleaned = clean_spoken_dialogue(cues)

    assert len(cleaned) == 1
    assert cleaned[0].index == 1
    assert cleaned[0].content == "Hello who is there?"
    assert cleaned[0].start == timedelta(seconds=1)


def test_translation_and_bilingual_require_exact_coverage() -> None:
    source = [srt.Subtitle(1, timedelta(0), timedelta(seconds=1), "Hello")]
    chinese = translated_subtitles(source, {0: "你好"})
    bilingual = bilingual_subtitles(source, chinese)

    assert chinese[0].content == "你好"
    assert bilingual[0].content == "你好\nHello"

    source_first = bilingual_subtitles(source, chinese, order="source-first")
    assert source_first[0].content == "Hello\n你好"


def test_language_enum_uses_plex_sidecar_names() -> None:
    assert SubtitleLanguage.TRADITIONAL_CHINESE.value == "zh-TW"
    assert SubtitleLanguage.SIMPLIFIED_CHINESE.value == "zh-CN"


def test_custom_language_sidecar_matches_common_three_letter_tag(tmp_path: Path) -> None:
    media = tmp_path / "Movie.mkv"
    media.write_bytes(b"video")
    japanese = tmp_path / "Movie.jpn.srt"
    japanese.write_text("x", encoding="utf-8")

    assert find_language_sidecar(media, "ja") == japanese


def test_bilingual_sidecar_uses_standard_multiple_languages_tag(tmp_path: Path) -> None:
    media = tmp_path / "Movie.mkv"
    media.write_bytes(b"video")
    bilingual = tmp_path / "Movie.mul.srt"
    bilingual.write_text("x", encoding="utf-8")
    misleading_cc = tmp_path / "Movie.en.cc.srt"
    misleading_cc.write_text("x", encoding="utf-8")

    assert sidecar_path(media, "en", bilingual=True) == bilingual
    assert find_language_sidecar(media, "en", bilingual=True) == bilingual
    assert find_language_sidecar(media, "en") is None


def test_time_based_merge_handles_one_to_many_segmentation() -> None:
    source = [srt.Subtitle(1, timedelta(0), timedelta(seconds=2), "Hello world")]
    target = [
        srt.Subtitle(1, timedelta(0), timedelta(seconds=1), "你好"),
        srt.Subtitle(2, timedelta(seconds=1), timedelta(seconds=2), "世界"),
    ]

    merged = merge_bilingual_subtitles(source, target)

    assert merged.source_match_ratio == 1
    assert merged.target_match_ratio == 1
    assert len(merged.subtitles) == 1
    assert merged.subtitles[0].content == "你好\n世界\nHello world"
    assert merged.subtitles[0].start == timedelta(0)
    assert merged.subtitles[0].end == timedelta(seconds=2)


def test_time_based_merge_rejects_unrelated_timelines() -> None:
    source = [srt.Subtitle(1, timedelta(0), timedelta(seconds=1), "Hello")]
    target = [srt.Subtitle(1, timedelta(seconds=10), timedelta(seconds=11), "你好")]

    with pytest.raises(ValueError, match="timing match is too low"):
        merge_bilingual_subtitles(source, target)
