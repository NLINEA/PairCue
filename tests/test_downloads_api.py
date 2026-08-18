from pathlib import Path

from fastapi.testclient import TestClient

from paircue.config import DownloadStationSettings
from paircue.downloads_api import create_downloads_app

TOKEN = "b" * 32


class FakeDownloadStation:
    def __init__(self) -> None:
        self.magnets: list[str] = []

    def list_tasks(self) -> list[dict[str, str]]:
        return [{"title": "safe title", "status": "downloading"}]

    def add_magnet(self, uri: str) -> bool:
        self.magnets.append(uri)
        return True


def _client(tmp_path: Path, backend: FakeDownloadStation) -> TestClient:
    settings = DownloadStationSettings(
        username="download-user",
        password="password",
        api_token=TOKEN,
        watch_dir=tmp_path,
        trusted_hosts="testserver",
    )
    return TestClient(create_downloads_app(settings, backend))  # type: ignore[arg-type]


def test_download_tasks_require_separate_token(tmp_path: Path) -> None:
    backend = FakeDownloadStation()
    with _client(tmp_path, backend) as client:
        assert client.get("/v1/tasks").status_code == 401
        response = client.get("/v1/tasks", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.json()["tasks"][0]["title"] == "safe title"


def test_magnet_is_validated(tmp_path: Path) -> None:
    backend = FakeDownloadStation()
    with _client(tmp_path, backend) as client:
        invalid = client.post(
            "/v1/magnets",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"uri": "https://example.com/file"},
        )
        valid = client.post(
            "/v1/magnets",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"uri": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"},
        )

    assert invalid.status_code == 422
    assert valid.status_code == 200
    assert len(backend.magnets) == 1


def test_torrent_upload_uses_generated_filename(tmp_path: Path) -> None:
    backend = FakeDownloadStation()
    with _client(tmp_path, backend) as client:
        response = client.post(
            "/v1/torrents",
            headers={"Authorization": f"Bearer {TOKEN}"},
            files={"file": ("unsafe-name.torrent", b"d4:infode", "application/x-bittorrent")},
        )

    assert response.status_code == 200
    stored = list(tmp_path.glob("*.torrent"))
    assert len(stored) == 1
    assert stored[0].name != "unsafe-name.torrent"
