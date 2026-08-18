import socket
from pathlib import Path

import httpx
import pytest

from paircue import cli
from paircue.config import PairCueSettings
from paircue.desktop_service import DesktopService

TOKEN = "d" * 40


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_desktop_service_opens_a_protected_dashboard_and_honours_edit(tmp_path: Path) -> None:
    settings = PairCueSettings(
        platform="filesystem",
        media_root=tmp_path,
        state_dir=tmp_path / "state",
        source_language="ja",
        target_language="en",
        api_host="127.0.0.1",
        api_port=_available_port(),
        api_token=TOKEN,
    )
    service = DesktopService(settings)
    service.start()

    headers = {"Authorization": f"Bearer {TOKEN}"}
    with httpx.Client(base_url=f"http://127.0.0.1:{settings.api_port}") as client:
        page = client.get("/")
        assert client.get("/v1/status").status_code == 401
        context = client.get("/v1/dashboard-context", headers=headers)
        edited = client.post("/v1/desktop/edit", headers=headers)

    assert page.status_code == 200
    assert context.json()["desktop"] is True
    assert context.json()["source_language"] == "ja"
    assert edited.status_code == 200
    assert service.wait() == "edit"


def test_desktop_dashboard_url_keeps_its_token_in_the_fragment(tmp_path: Path) -> None:
    settings = PairCueSettings(
        platform="filesystem",
        media_root=tmp_path,
        state_dir=tmp_path / "state",
        api_port=9292,
        api_token="token with spaces" + "x" * 32,
    )

    url = DesktopService(settings).url

    assert url.startswith("http://127.0.0.1:9292/#token=")
    assert "token with spaces" not in url
    assert "token%20with%20spaces" in url


def test_desktop_settings_use_the_selected_host_folder_and_private_state(tmp_path: Path) -> None:
    media = tmp_path / "Media"
    media.mkdir()
    config = tmp_path / "paircue.env"
    config.write_text(
        f'MEDIA_PATH="{media}"\n'
        'PAIRCUE_PLATFORM="filesystem"\n'
        'PAIRCUE_SOURCE_LANGUAGE="ja"\n'
        'PAIRCUE_TARGET_LANGUAGE="en"\n'
        f'PAIRCUE_API_TOKEN="{TOKEN}"\n',
        encoding="utf-8",
    )

    settings = cli._desktop_library_settings(config)

    assert settings.media_root == media
    assert settings.state_dir == tmp_path / "state"
    assert settings.api_host == "127.0.0.1"


def test_desktop_settings_reject_a_missing_media_folder(tmp_path: Path) -> None:
    config = tmp_path / "paircue.env"
    config.write_text(
        'MEDIA_PATH="/definitely/not/a/paircue/library"\n'
        'PAIRCUE_PLATFORM="filesystem"\n',
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        cli._desktop_library_settings(config)


def test_desktop_main_reopens_an_existing_library_without_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "Media"
    media.mkdir()
    config = tmp_path / "paircue.env"
    config.write_text(f'MEDIA_PATH="{media}"\n', encoding="utf-8")
    observed: list[tuple[Path, bool]] = []
    monkeypatch.setattr(cli, "_default_setup_output", lambda: config)
    monkeypatch.setattr(
        cli,
        "_run_desktop_library",
        lambda path, reopen_setup: observed.append((path, reopen_setup)) or 0,
    )

    assert cli.desktop_main() == 0
    assert observed == [(config, True)]


def test_desktop_main_reopens_setup_for_a_damaged_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "paircue.env"
    config.write_text('MEDIA_PATH="unterminated\n', encoding="utf-8")
    monkeypatch.setattr(cli, "_default_setup_output", lambda: config)
    setup_calls: list[bool] = []
    monkeypatch.setattr(
        cli,
        "_setup",
        lambda *, no_open: setup_calls.append(no_open) or 0,
    )

    assert cli.desktop_main() == 0
    assert setup_calls == [False]
