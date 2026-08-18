from pathlib import Path

import pytest

from paircue.config import PairCueSettings
from paircue.factory import build_media_source
from paircue.services.filesystem import FilesystemSource
from paircue.services.media_browser import EmbyClient, JellyfinClient
from paircue.services.plex import PlexClient


@pytest.mark.parametrize(
    ("platform", "expected_type"),
    [
        ("jellyfin", JellyfinClient),
        ("emby", EmbyClient),
    ],
)
def test_factory_selects_media_server_connector(
    tmp_path: Path,
    platform: str,
    expected_type: type[JellyfinClient] | type[EmbyClient],
) -> None:
    settings = PairCueSettings(
        platform=platform,
        server_url="http://media-server:8096",
        server_token="s" * 16,
        server_user_id="user-id",
        server_path_prefix="/media",
        media_root=tmp_path,
    )

    source = build_media_source(settings)
    try:
        assert isinstance(source, expected_type)
    finally:
        source.close()


def test_factory_selects_filesystem_source(tmp_path: Path) -> None:
    source = build_media_source(PairCueSettings(platform="filesystem", media_root=tmp_path))

    assert isinstance(source, FilesystemSource)


def test_factory_keeps_legacy_plex_connector(tmp_path: Path) -> None:
    source = build_media_source(
        PairCueSettings(
            plex_url="http://plex:32400",
            plex_token="p" * 16,
            plex_path_prefix="/media",
            media_root=tmp_path,
        )
    )
    try:
        assert isinstance(source, PlexClient)
    finally:
        source.close()
