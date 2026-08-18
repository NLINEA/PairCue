import json
from pathlib import Path

import pytest

from paircue import diagnostics
from paircue.cli import main

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
