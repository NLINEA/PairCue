import stat
import threading
from pathlib import Path

import httpx

import paircue
from paircue.setup_server import SetupHTTPServer

VALID_CONFIG = """PAIRCUE_PLATFORM="filesystem"
PAIRCUE_SOURCE_LANGUAGE="en"
PAIRCUE_TARGET_LANGUAGE="ja"
"""

SINGLE_JELLYFIN_CONFIG = """PAIRCUE_PLATFORM="jellyfin"
PAIRCUE_SOURCE_LANGUAGE="en"
PAIRCUE_TARGET_LANGUAGE="ja"
"""


def test_setup_server_serves_local_assets_and_saves_with_backup(tmp_path: Path) -> None:
    assets = Path(paircue.__file__).with_name("setup")
    output = tmp_path / "paircue.env"
    output.write_text("old configuration\n", encoding="utf-8")
    server = SetupHTTPServer(assets, output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=server.origin) as client:
            page = client.get("/")
            readiness = client.get("/readiness")
            forbidden = client.post(
                "/config?token=wrong",
                headers={"Origin": server.origin},
                json={"config": VALID_CONFIG},
            )
            saved = client.post(
                f"/config?token={server.token}",
                headers={"Origin": server.origin},
                json={"config": VALID_CONFIG, "mode": "single"},
            )
            wrong_progress = client.get("/progress?token=wrong")
            pending_progress = client.get(f"/progress?token={server.token}")
            completed_output = tmp_path / "Private Movie.ja.cc.srt"
            server.state.update_progress(
                "completed",
                "created bilingual subtitles",
                (completed_output,),
            )
            completed_progress = client.get(f"/progress?token={server.token}")
            repeated = client.post(
                f"/config?token={server.token}",
                headers={"Origin": server.origin},
                json={"config": VALID_CONFIG, "mode": "single"},
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert page.status_code == 200
    assert "PairCue Setup" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert readiness.status_code == 200
    assert set(readiness.json()) == {"ready", "ffmpeg", "ffprobe"}
    assert forbidden.status_code == 403
    assert saved.status_code == 200
    assert saved.json()["saved"] is True
    assert saved.json()["location"] == str(tmp_path)
    assert wrong_progress.status_code == 403
    assert pending_progress.json()["phase"] == "saved"
    assert pending_progress.json()["terminal"] is False
    assert completed_progress.json() == {
        "phase": "completed",
        "message": "created bilingual subtitles",
        "outputs": ["Private Movie.ja.cc.srt"],
        "terminal": True,
    }
    assert str(tmp_path) not in completed_progress.text
    assert repeated.status_code == 409
    assert output.read_text(encoding="utf-8") == VALID_CONFIG
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    backup = server.state.backup_path
    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "old configuration\n"
    assert server.state.saved.is_set()
    assert server.state.delivered.is_set()
    assert server.state.mode == "single"


def test_setup_server_rejects_cross_origin_and_oversized_requests(tmp_path: Path) -> None:
    assets = Path(paircue.__file__).with_name("setup")
    output = tmp_path / "paircue.env"
    server = SetupHTTPServer(assets, output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=server.origin) as client:
            cross_origin = client.post(
                f"/config?token={server.token}",
                headers={"Origin": "https://example.com"},
                json={"config": "unsafe\n"},
            )
            invalid_config = client.post(
                f"/config?token={server.token}",
                headers={"Origin": server.origin},
                json={
                    "config": 'PAIRCUE_SOURCE_LANGUAGE="en"\n'
                    'PAIRCUE_TARGET_LANGUAGE="en"\n'
                },
            )
            oversized = client.post(
                f"/config?token={server.token}",
                headers={"Origin": server.origin, "Content-Type": "application/json"},
                content=b"x" * (64 * 1024 + 1),
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert cross_origin.status_code == 403
    assert invalid_config.status_code == 400
    assert oversized.status_code == 413
    assert not output.exists()


def test_single_video_setup_remembers_platform_without_requiring_server_credentials(
    tmp_path: Path,
) -> None:
    assets = Path(paircue.__file__).with_name("setup")
    output = tmp_path / "paircue.env"
    server = SetupHTTPServer(assets, output)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=server.origin) as client:
            saved = client.post(
                f"/config?token={server.token}",
                headers={"Origin": server.origin},
                json={"config": SINGLE_JELLYFIN_CONFIG, "mode": "single"},
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert saved.status_code == 200
    assert output.read_text(encoding="utf-8") == SINGLE_JELLYFIN_CONFIG
