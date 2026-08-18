from datetime import timedelta
from pathlib import Path

import srt

from subflow.services.subtitle_files import (
    SubtitleLanguage,
    bilingual_subtitles,
    clean_spoken_dialogue,
    discover_sidecars,
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


def test_language_enum_uses_plex_sidecar_names() -> None:
    assert SubtitleLanguage.TRADITIONAL_CHINESE.value == "zh-TW"
    assert SubtitleLanguage.SIMPLIFIED_CHINESE.value == "zh-CN"
