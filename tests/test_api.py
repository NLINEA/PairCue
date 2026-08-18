from fastapi.testclient import TestClient

from paircue.api import create_core_app
from paircue.config import PairCueSettings

TOKEN = "a" * 32


class DummyRuntime:
    def __init__(self) -> None:
        self.started = False
        self.rating_keys: list[str] = []

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def scan_now(self) -> int:
        return 3

    def submit_rating_key(self, rating_key: str) -> bool:
        self.rating_keys.append(rating_key)
        return True

    def submit_item_id(self, item_id: str) -> bool:
        self.rating_keys.append(item_id)
        return True


def _client(runtime: DummyRuntime) -> TestClient:
    settings = PairCueSettings(
        api_token=TOKEN,
        webhook_enabled=True,
        trusted_hosts="testserver",
    )
    return TestClient(create_core_app(settings, runtime))  # type: ignore[arg-type]


def _jellyfin_client(runtime: DummyRuntime) -> TestClient:
    settings = PairCueSettings(
        platform="jellyfin",
        server_url="http://jellyfin:8096",
        server_token="server-token",
        server_user_id="user-id",
        server_path_prefix="/media",
        api_token=TOKEN,
        webhook_enabled=True,
        trusted_hosts="testserver",
    )
    return TestClient(create_core_app(settings, runtime))  # type: ignore[arg-type]


def test_health_is_public_but_scan_is_protected() -> None:
    runtime = DummyRuntime()
    with _client(runtime) as client:
        assert client.get("/health").status_code == 200
        assert client.post("/v1/scan").status_code == 401
        response = client.post("/v1/scan", headers={"Authorization": f"Bearer {TOKEN}"})
        assert response.json() == {"queued": True, "message": "queued 3 item(s)"}


def test_webhook_validates_payload_and_queues_rating_key() -> None:
    runtime = DummyRuntime()
    with _client(runtime) as client:
        response = client.post(
            "/v1/webhooks/plex",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"event": "library.new", "Metadata": {"ratingKey": "123"}},
        )

    assert response.status_code == 200
    assert runtime.rating_keys == ["123"]


def test_webhook_rejects_unknown_rating_key_shape() -> None:
    runtime = DummyRuntime()
    with _client(runtime) as client:
        response = client.post(
            "/v1/webhooks/plex",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"event": "library.new", "Metadata": {"ratingKey": "../etc/passwd"}},
        )

    assert response.status_code == 400
    assert runtime.rating_keys == []


def test_jellyfin_webhook_queues_added_movie() -> None:
    runtime = DummyRuntime()
    with _jellyfin_client(runtime) as client:
        response = client.post(
            "/v1/webhooks/jellyfin",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "NotificationType": "ItemAdded",
                "ItemId": "a1b2-c3d4",
                "ItemType": "Movie",
            },
        )

    assert response.status_code == 200
    assert runtime.rating_keys == ["a1b2-c3d4"]


def test_inactive_platform_webhook_is_hidden() -> None:
    runtime = DummyRuntime()
    with _client(runtime) as client:
        response = client.post(
            "/v1/webhooks/jellyfin",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={
                "NotificationType": "ItemAdded",
                "ItemId": "a1b2",
                "ItemType": "Movie",
            },
        )

    assert response.status_code == 404
    assert runtime.rating_keys == []
