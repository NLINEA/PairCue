from pathlib import Path

import pytest

from subflow.services import downloader as downloader_module
from subflow.services.downloader import SubliminalDownloader


def test_downloader_preserves_the_requested_language_tag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "Movie.mkv"
    media.write_bytes(b"video")
    video = object()

    monkeypatch.setattr(downloader_module, "scan_video", lambda _: video)

    def fake_download(
        videos: set[object],
        languages: set[object],
        **_: object,
    ) -> dict[object, list[object]]:
        assert videos == {video}
        assert {str(language) for language in languages} == {"ja"}
        return {video: [object()]}

    def fake_save(_: object, found: list[object], **kwargs: object) -> list[object]:
        directory = Path(str(kwargs["directory"]))
        (directory / "Movie.ja.srt").write_bytes(b"subtitle")
        return found

    monkeypatch.setattr(downloader_module, "download_best_subtitles", fake_download)
    monkeypatch.setattr(downloader_module, "save_subtitles", fake_save)
    downloader = SubliminalDownloader(("example",), tmp_path / "temporary")

    outputs = downloader.download(media, {"ja"})

    assert outputs == (tmp_path / "Movie.ja.srt",)
    assert outputs[0].read_bytes() == b"subtitle"


def test_downloader_ignores_an_unknown_but_safe_language_tag(tmp_path: Path) -> None:
    downloader = SubliminalDownloader(("example",), tmp_path / "temporary")

    assert downloader.download(tmp_path / "Movie.mkv", {"zz"}) == ()
