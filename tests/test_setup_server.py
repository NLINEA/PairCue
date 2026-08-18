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
    assert repeated.status_code == 409
    assert output.read_text(encoding="utf-8") == VALID_CONFIG
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    backup = server.state.backup_path
    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "old configuration\n"
    assert server.state.saved.is_set()
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
