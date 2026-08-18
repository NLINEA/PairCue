from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from subflow.models import MediaItem, MediaType


class PlexError(RuntimeError):
    pass


class PlexClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        plex_path_prefix: str,
        media_root: Path,
    ) -> None:
        if not token:
            raise ValueError("Plex token is required")
        self.base_url = base_url.rstrip("/")
        self.plex_path_prefix = PurePosixPath(plex_path_prefix)
        self.media_root = media_root
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-Plex-Token": token,
                "X-Plex-Client-Identifier": "subflow",
                "X-Plex-Product": "SubFlow",
                "X-Plex-Version": "0.1.0b1",
                "X-Plex-Pms-Api-Version": "1.0.0",
                "Accept": "application/json",
            },
            timeout=30,
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str) -> dict[str, Any]:
        response = self._client.get(path)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise PlexError("Plex returned an unexpected response")
        return data

    def libraries(self) -> list[dict[str, str]]:
        data = self._get("/library/sections")
        directories = data.get("MediaContainer", {}).get("Directory", [])
        return [
            {"key": str(row["key"]), "title": str(row["title"]), "type": str(row["type"])}
            for row in directories
            if row.get("type") in {"movie", "show"} and row.get("key")
        ]

    def scan_items(self) -> list[MediaItem]:
        items: list[MediaItem] = []
        for library in self.libraries():
            media_type: MediaType = "movie" if library["type"] == "movie" else "episode"
            type_number = "1" if media_type == "movie" else "4"
            path = f"/library/sections/{library['key']}/all"
            for metadata in self._paginated_metadata(path, params={"type": type_number}):
                item = self._extract(metadata, media_type, library["key"])
                if item is None:
                    continue
                if media_type == "episode":
                    item = MediaItem(
                        rating_key=item.rating_key,
                        media_type=item.media_type,
                        path=item.path,
                        title=item.title,
                        year=item.year,
                        show_title=str(metadata.get("grandparentTitle") or ""),
                        season=item.season,
                        episode=item.episode,
                        library_key=item.library_key,
                    )
                items.append(item)
        return items

    def _paginated_metadata(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        page_size: int = 200,
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        offset = 0
        previous_page_ids: tuple[str, ...] | None = None
        while True:
            response = self._client.get(
                path,
                params=params,
                headers={
                    "X-Plex-Container-Start": str(offset),
                    "X-Plex-Container-Size": str(page_size),
                },
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise PlexError("Plex returned an unexpected response")
            container = data.get("MediaContainer", {})
            rows = container.get("Metadata", [])
            if not isinstance(rows, list):
                raise PlexError("Plex metadata page has an unexpected shape")
            page_ids = tuple(
                str(row.get("ratingKey") or "") for row in rows if isinstance(row, dict)
            )
            if rows and page_ids == previous_page_ids:
                raise PlexError("Plex ignored pagination and returned the same page twice")
            previous_page_ids = page_ids
            output.extend(row for row in rows if isinstance(row, dict))
            received = len(rows)
            total = container.get("totalSize")
            if received == 0 or (isinstance(total, int) and offset + received >= total):
                break
            if received < page_size and not isinstance(total, int):
                break
            offset += received
        return output

    def item_for_rating_key(self, rating_key: str) -> MediaItem | None:
        if not rating_key.isdigit():
            raise ValueError("rating key must contain digits only")
        data = self._get(f"/library/metadata/{rating_key}")
        rows = data.get("MediaContainer", {}).get("Metadata", [])
        if not rows:
            return None
        metadata = rows[0]
        media_type = metadata.get("type")
        if media_type not in {"movie", "episode"}:
            return None
        item = self._extract(metadata, media_type, "")
        if item is None or media_type == "movie":
            return item
        return MediaItem(
            rating_key=item.rating_key,
            media_type=item.media_type,
            path=item.path,
            title=item.title,
            year=item.year,
            show_title=str(metadata.get("grandparentTitle") or ""),
            season=item.season,
            episode=item.episode,
            library_key=item.library_key,
        )

    def _extract(
        self, metadata: dict[str, Any], media_type: MediaType, library_key: str
    ) -> MediaItem | None:
        server_path = ""
        for media in metadata.get("Media", []):
            for part in media.get("Part", []):
                if part.get("file"):
                    server_path = str(part["file"])
                    break
            if server_path:
                break
        if not server_path:
            return None
        return MediaItem(
            rating_key=str(metadata.get("ratingKey") or ""),
            media_type=media_type,
            path=self.remap_path(server_path),
            title=str(metadata.get("title") or "Unknown"),
            year=metadata.get("year") if isinstance(metadata.get("year"), int) else None,
            season=metadata.get("parentIndex")
            if isinstance(metadata.get("parentIndex"), int)
            else None,
            episode=metadata.get("index") if isinstance(metadata.get("index"), int) else None,
            library_key=library_key,
        )

    def remap_path(self, server_path: str) -> Path:
        path = PurePosixPath(server_path)
        try:
            relative = path.relative_to(self.plex_path_prefix)
        except ValueError as exc:
            raise PlexError("Plex returned a path outside PLEX_PATH_PREFIX") from exc
        return self.media_root.joinpath(*relative.parts)
