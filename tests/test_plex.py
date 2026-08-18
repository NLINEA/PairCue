from pathlib import Path

import httpx
import pytest

from subflow.services.plex import PlexClient, PlexError


def test_plex_path_mapping_is_component_aware(tmp_path: Path) -> None:
    client = PlexClient(
        base_url="http://127.0.0.1:32400",
        token="token",
        plex_path_prefix="/volume1/MediaForPlex",
        media_root=tmp_path,
    )
    try:
        assert client.remap_path("/volume1/MediaForPlex/Movies/Test.mkv") == (
            tmp_path / "Movies" / "Test.mkv"
        )
        with pytest.raises(PlexError):
            client.remap_path("/volume1/MediaForPlex-Other/Test.mkv")
    finally:
        client.close()


def test_plex_metadata_scan_uses_pagination(tmp_path: Path) -> None:
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        start = int(request.headers["X-Plex-Container-Start"])
        requests.append(start)
        rows = [
            {
                "ratingKey": str(index),
                "type": "movie",
                "title": f"Movie {index}",
                "Media": [{"Part": [{"file": f"/volume1/MediaForPlex/Movie{index}.mkv"}]}],
            }
            for index in range(start, min(start + 2, 3))
        ]
        return httpx.Response(
            200,
            json={"MediaContainer": {"Metadata": rows, "totalSize": 3, "offset": start}},
        )

    client = PlexClient(
        base_url="http://127.0.0.1:32400",
        token="token",
        plex_path_prefix="/volume1/MediaForPlex",
        media_root=tmp_path,
    )
    client._client.close()
    client._client = httpx.Client(
        base_url="http://plex",
        transport=httpx.MockTransport(handler),
    )
    try:
        rows = client._paginated_metadata("/library", page_size=2)
    finally:
        client.close()

    assert len(rows) == 3
    assert requests == [0, 2]
