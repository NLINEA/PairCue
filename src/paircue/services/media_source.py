from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Protocol

from paircue.models import MediaItem


class MediaSourceError(RuntimeError):
    pass


class MediaSource(Protocol):
    platform: str

    def scan_items(self) -> list[MediaItem]: ...

    def item_for_id(self, item_id: str) -> MediaItem | None: ...

    def close(self) -> None: ...


def remap_server_path(
    server_path: str,
    *,
    server_path_prefix: str,
    media_root: Path,
    platform: str,
) -> Path:
    """Map a server path into the mounted media root by path components."""
    normalized_path = server_path.replace("\\", "/")
    normalized_prefix = server_path_prefix.replace("\\", "/")
    path = PurePosixPath(normalized_path)
    prefix = PurePosixPath(normalized_prefix)
    windows_path = re.match(r"^[A-Za-z]:/", normalized_path) is not None
    windows_prefix = re.match(r"^[A-Za-z]:/", normalized_prefix) is not None
    if windows_path and windows_prefix:
        path_parts = path.parts
        prefix_parts = prefix.parts
        prefix_matches = len(path_parts) >= len(prefix_parts) and all(
            actual.casefold() == expected.casefold()
            for actual, expected in zip(path_parts, prefix_parts, strict=False)
        )
        if not prefix_matches:
            raise MediaSourceError(
                f"{platform} returned a path outside PAIRCUE_SERVER_PATH_PREFIX"
            )
        relative_parts = path_parts[len(prefix_parts) :]
    else:
        try:
            relative_parts = path.relative_to(prefix).parts
        except ValueError as exc:
            raise MediaSourceError(
                f"{platform} returned a path outside PAIRCUE_SERVER_PATH_PREFIX"
            ) from exc
    if ".." in relative_parts:
        raise MediaSourceError(f"{platform} returned a path containing parent traversal")
    return media_root.joinpath(*relative_parts)
