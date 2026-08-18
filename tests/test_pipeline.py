from pathlib import Path

from subflow.models import MediaItem
from subflow.services.glossary import GlossaryStore
from subflow.services.pipeline import SubtitlePipeline
from subflow.services.state import StateStore


class NoopExtractor:
    def extract(self, media_path: Path, languages: set[str] | None = None) -> tuple[Path, ...]:
        return ()


class NoopDownloader:
    def download(self, media_path: Path, languages: set[str]) -> tuple[Path, ...]:
        return ()


class TargetDownloader(NoopDownloader):
    def __init__(self) -> None:
        self.requests: list[set[str]] = []

    def download(self, media_path: Path, languages: set[str]) -> tuple[Path, ...]:
        self.requests.append(languages)
        if "ja" not in languages:
            return ()
        output = media_path.parent / f"{media_path.stem}.ja.srt"
        output.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nこんにちは\n\n",
            encoding="utf-8",
        )
        return (output,)


class FullTranslator:
    def translate_all(
        self, subtitles: list[object], *, context: str, glossary: dict[str, str]
    ) -> dict[int, str]:
        return {index: f"翻譯 {index}" for index in range(len(subtitles))}


class PartialTranslator(FullTranslator):
    def translate_all(
        self, subtitles: list[object], *, context: str, glossary: dict[str, str]
    ) -> dict[int, str]:
        return {}


def _pipeline(
    tmp_path: Path,
    translator: object,
    *,
    target_language: str = "zh-TW",
    downloader: object | None = None,
) -> SubtitlePipeline:
    return SubtitlePipeline(
        media_root=tmp_path,
        state=StateStore(tmp_path / "state" / "subflow.sqlite3"),
        downloader=downloader or NoopDownloader(),  # type: ignore[arg-type]
        extractor=NoopExtractor(),  # type: ignore[arg-type]
        synchronizer=None,
        translator=translator,  # type: ignore[arg-type]
        glossary=GlossaryStore(tmp_path / "state" / "glossaries"),
        target_language=target_language,
    )


def _media(tmp_path: Path) -> MediaItem:
    media = tmp_path / "Movie.mkv"
    media.write_bytes(b"fake media")
    (tmp_path / "Movie.en.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nWorld\n\n",
        encoding="utf-8",
    )
    return MediaItem("1", "movie", media, "Movie")


def test_pipeline_writes_complete_atomic_outputs(tmp_path: Path) -> None:
    result = _pipeline(tmp_path, FullTranslator()).process(_media(tmp_path))

    assert result.status == "completed"
    assert (tmp_path / "Movie.zh-TW.srt").exists()
    assert (tmp_path / "Movie.zh-TW.cc.srt").exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_pipeline_does_not_publish_partial_translation(tmp_path: Path) -> None:
    result = _pipeline(tmp_path, PartialTranslator()).process(_media(tmp_path))

    assert result.status == "failed"
    assert not (tmp_path / "Movie.zh-TW.srt").exists()
    assert not (tmp_path / "Movie.zh-TW.cc.srt").exists()


def test_pipeline_uses_custom_target_language_in_output_names(tmp_path: Path) -> None:
    result = _pipeline(tmp_path, FullTranslator(), target_language="ja").process(_media(tmp_path))

    assert result.status == "completed"
    assert "to ja" in result.message
    assert (tmp_path / "Movie.ja.srt").exists()
    assert (tmp_path / "Movie.ja.cc.srt").exists()
    assert not (tmp_path / "Movie.zh-TW.srt").exists()


def test_download_only_mode_requests_the_custom_target(tmp_path: Path) -> None:
    downloader = TargetDownloader()
    result = _pipeline(
        tmp_path,
        None,
        target_language="ja",
        downloader=downloader,
    ).process(_media(tmp_path))

    assert result.status == "completed"
    assert downloader.requests == [{"ja"}]
    assert result.outputs == (tmp_path / "Movie.ja.srt",)
