from pathlib import Path

import httpx
import pytest

from subflow.services.media_browser import EmbyClient, JellyfinClient
from subflow.services.media_source import MediaSourceError


def test_jellyfin_scans_paginated_movies_and_episodes(tmp_path: Path) -> None:
    starts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/Users/user-id/Items"
        assert request.headers["Authorization"].startswith("MediaBrowser Client=")
        assert request.headers["X-Emby-Token"] == "api-token"
        start = int(request.url.params["StartIndex"])
        starts.append(start)
        rows = [
            {
                "Id": "movie-1",
                "Type": "Movie",
                "Name": "First Movie",
                "ProductionYear": 2025,
                "Path": "/srv/media/Movies/First.mkv",
            },
            {
                "Id": "episode-1",
                "Type": "Episode",
                "Name": "Pilot",
                "SeriesName": "Learning Show",
                "ParentIndexNumber": 1,
                "IndexNumber": 1,
                "Path": "/srv/media/Shows/Learning Show/S01E01.mkv",
            },
        ][start : start + 1]
        return httpx.Response(
            200,
            json={"Items": rows, "TotalRecordCount": 2, "StartIndex": start},
        )

    client = JellyfinClient(
        base_url="http://jellyfin:8096",
        token="api-token",
        user_id="user-id",
        server_path_prefix="/srv/media",
        media_root=tmp_path,
        transport=httpx.MockTransport(handler),
    )
    try:
        items = client._paginated_items(page_size=1)
    finally:
        client.close()

    assert starts == [0, 1]
    assert [item.item_id for item in items] == ["movie-1", "episode-1"]
    assert items[0].path == tmp_path / "Movies" / "First.mkv"
    assert items[1].context_label == "Learning Show S01E01"


def test_emby_adds_the_official_api_prefix_and_maps_windows_paths(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/emby/Users/user/Items/item-1"
        return httpx.Response(
            200,
            json={
                "Id": "item-1",
                "Type": "Movie",
                "Name": "Windows Movie",
                "Path": r"D:\Media\Movies\Windows.mkv",
            },
        )

    client = EmbyClient(
        base_url="http://emby:8096",
        token="api-token",
        user_id="user",
        server_path_prefix=r"d:\media",
        media_root=tmp_path,
        transport=httpx.MockTransport(handler),
    )
    try:
        item = client.item_for_id("item-1")
    finally:
        client.close()

    assert item is not None
    assert item.path == tmp_path / "Movies" / "Windows.mkv"


def test_media_browser_rejects_out_of_root_paths(tmp_path: Path) -> None:
    client = JellyfinClient(
        base_url="http://jellyfin:8096",
        token="api-token",
        user_id="user",
        server_path_prefix="/srv/media",
        media_root=tmp_path,
    )
    try:
        with pytest.raises(MediaSourceError, match="outside"):
            client.remap_path("/srv/media-other/Movie.mkv")
        with pytest.raises(MediaSourceError, match="traversal"):
            client.remap_path("/srv/media/../secret/Movie.mkv")
    finally:
        client.close()
