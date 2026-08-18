from pathlib import Path

from paircue.services.subtitle_files import (
    merge_bilingual_subtitles,
    parse_srt,
    write_srt,
)


def test_owned_demo_output_is_generated_by_paircue(tmp_path: Path) -> None:
    examples = Path(__file__).parents[1] / "examples"
    merged = merge_bilingual_subtitles(
        parse_srt(examples / "demo.en.srt"),
        parse_srt(examples / "demo.es.srt"),
    )
    generated = tmp_path / "demo.mul.srt"

    write_srt(generated, merged.subtitles)

    assert generated.read_text(encoding="utf-8").rstrip() == (
        examples / "demo.mul.srt"
    ).read_text(encoding="utf-8").rstrip()
