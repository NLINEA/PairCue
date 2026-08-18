import json
import threading
from pathlib import Path

import pytest

from paircue import diagnostics
from paircue.cli import main
from paircue.config import PairCueSettings
from paircue.models import MediaItem, ProcessResult
from paircue.setup_server import SetupState

SOURCE = """1
00:00:00,000 --> 00:00:02,000
Hello world

"""

TARGET = """1
00:00:00,050 --> 00:00:01,000
你好

2
00:00:01,000 --> 00:00:02,050
世界

"""


class RecordingPipeline:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.items: list[MediaItem] = []
        self.closed = False

    def process(self, item: MediaItem) -> ProcessResult:
        self.items.append(item)
        self.output.write_text(TARGET, encoding="utf-8")
        return ProcessResult("completed", "created learning track", (self.output,))

    def close(self) -> None:
        self.closed = True


def test_pair_command_creates_bilingual_srt(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "movie.en.srt"
    target = tmp_path / "movie.zh-TW.srt"
    output = tmp_path / "movie.zh-TW.cc.srt"
    source.write_text(SOURCE, encoding="utf-8")
    target.write_text(TARGET, encoding="utf-8")

    result = main(["pair", str(source), str(target), "-o", str(output)])

    assert result == 0
    assert output.exists()
    assert "你好\n世界\nHello world" in output.read_text(encoding="utf-8")
    assert "100%/100% matched" in capsys.readouterr().out


def test_pair_command_will_not_overwrite_an_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "movie.en.srt"
    target = tmp_path / "movie.zh-TW.srt"
    source.write_text(SOURCE, encoding="utf-8")
    target.write_text(TARGET, encoding="utf-8")

    result = main(["pair", str(source), str(target), "-o", str(source)])

    assert result == 2
    assert "must not overwrite" in capsys.readouterr().err


def test_setup_command_opens_packaged_private_wizard(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(["setup", "--no-open"])

    assert result == 0
    assert capsys.readouterr().out.strip().endswith("/paircue/setup/index.html")


def test_bare_paircue_opens_setup_and_reports_saved_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "paircue.env"
    state = SetupState(threading.Event(), output_path=output, mode="library")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("paircue.cli.run_setup_wizard", lambda assets, target: state)

    result = main([])

    assert result == 0
    assert f"Saved private configuration: {output}" in capsys.readouterr().out


def test_bare_paircue_continues_from_setup_to_native_video_picker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = tmp_path / "paircue.env"
    config.write_text(
        'PAIRCUE_PLATFORM="filesystem"\n'
        'PAIRCUE_SOURCE_LANGUAGE="ja"\n'
        'PAIRCUE_TARGET_LANGUAGE="en"\n',
        encoding="utf-8",
    )
    media = tmp_path / "Lesson.mkv"
    media.write_bytes(b"video")
    output = tmp_path / "Lesson.en.cc.srt"
    state = SetupState(threading.Event(), output_path=config, mode="single")
    pipeline = RecordingPipeline(output)
    picker_calls = 0

    def choose_media() -> Path:
        nonlocal picker_calls
        picker_calls += 1
        return media

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("paircue.cli.run_setup_wizard", lambda assets, target: state)
    monkeypatch.setattr("paircue.cli._choose_media_path", choose_media)
    monkeypatch.setattr("paircue.cli.build_pipeline", lambda settings: pipeline)
    revealed: list[Path] = []
    monkeypatch.setattr("paircue.cli._reveal_path", revealed.append)

    result = main([])

    assert result == 0
    assert picker_calls == 1
    assert pipeline.closed is True
    assert pipeline.items[0].path == media
    assert revealed == [output]
    captured = capsys.readouterr().out
    assert "Choose one video" in captured
    assert f"created: {output}" in captured


def test_learn_command_runs_one_local_video_without_a_media_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    media = tmp_path / "Japanese Film.mkv"
    media.write_bytes(b"video")
    output = tmp_path / "Japanese Film.en.cc.srt"
    pipeline = RecordingPipeline(output)
    observed_settings: list[PairCueSettings] = []

    def fake_build(settings: PairCueSettings) -> RecordingPipeline:
        observed_settings.append(settings)
        return pipeline

    monkeypatch.setattr("paircue.cli.build_pipeline", fake_build)
    monkeypatch.setattr("paircue.cli._choose_media_path", lambda: media)

    result = main(
        [
            "learn",
            "--from",
            "ja",
            "--to",
            "en",
            "--order",
            "source-first",
            "--title",
            "Japanese Film",
            "--year",
            "2024",
        ]
    )

    assert result == 0
    assert pipeline.closed is True
    assert pipeline.items == [
        MediaItem("local", "movie", media, "Japanese Film", year=2024)
    ]
    assert observed_settings[0].platform == "filesystem"
    assert observed_settings[0].media_root == tmp_path
    assert observed_settings[0].source_language == "ja"
    assert observed_settings[0].target_language == "en"
    assert observed_settings[0].bilingual_order == "source-first"
    assert str(output) in capsys.readouterr().out


def test_doctor_json_reports_readiness_without_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    media = tmp_path / "media"
    state = tmp_path / "state"
    media.mkdir()
    state.mkdir()
    monkeypatch.setenv("PAIRCUE_PLATFORM", "filesystem")
    monkeypatch.setenv("PAIRCUE_MEDIA_ROOT", str(media))
    monkeypatch.setenv("PAIRCUE_STATE_DIR", str(state))
    monkeypatch.setenv("PAIRCUE_OPENSUBTITLES_API_KEY", "should-not-leak")
    monkeypatch.setattr(diagnostics.shutil, "which", lambda command: f"/usr/bin/{command}")

    result = main(["doctor", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["ready"] is True
    assert "should-not-leak" not in json.dumps(payload)
    assert any(check["name"] == "FFmpeg" for check in payload["checks"])


def test_doctor_json_redacts_invalid_configuration_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(
        "PAIRCUE_TRANSCRIPTION_BASE_URL",
        "https://private-user:private-password@example.com/v1",
    )

    result = main(["doctor", "--json"])

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert result == 1
    assert payload["ready"] is False
    assert "private-user" not in output
    assert "private-password" not in output
    assert "input" not in payload["configuration_errors"][0]
