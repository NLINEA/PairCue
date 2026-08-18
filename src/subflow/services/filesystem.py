from __future__ import annotations

import hashlib
import re
from pathlib import Path

from subflow.models import MediaItem, MediaType

EPISODE_PATTERN = re.compile(
    r"(?i)(?:^|[ ._-])(?:s(?P<season>\d{1,3})e|(?P<season_alt>\d{1,3})x)"
    r"(?P<episode>\d{1,3})(?:[ ._-]|$)"
)
YEAR_PATTERN = re.compile(r"(?:^|[ ._(\[])(?P<year>(?:19|20)\d{2})(?:[ ._)\]]|$)")


class FilesystemSource:
    platform = "filesystem"

    def __init__(self, *, media_root: Path, extensions: tuple[str, ...]) -> None:
        self.media_root = media_root
        self.extensions = frozenset(extension.casefold() for extension in extensions)

    def close(self) -> None:
        return None

    def scan_items(self) -> list[MediaItem]:
        root = self.media_root.resolve(strict=True)
        items: list[MediaItem] = []
        seen: set[Path] = set()
        for candidate in sorted(root.rglob("*")):
            if candidate.suffix.casefold() not in self.extensions:
                continue
            try:
                path = candidate.resolve(strict=True)
                relative = path.relative_to(root)
            except (OSError, ValueError):
                continue
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            items.append(self._item(path, relative))
        return items

    def item_for_id(self, item_id: str) -> MediaItem | None:
        return next((item for item in self.scan_items() if item.item_id == item_id), None)

    @staticmethod
    def _item(path: Path, relative: Path) -> MediaItem:
        match = EPISODE_PATTERN.search(path.stem)
        media_type: MediaType = "episode" if match is not None else "movie"
        season = None
        episode = None
        show_title = ""
        if match is not None:
            season = int(match.group("season") or match.group("season_alt"))
            episode = int(match.group("episode"))
            show_title = (
                path.parent.parent.name
                if path.parent.name.casefold().startswith("season")
                else path.parent.name
            )
        year_match = YEAR_PATTERN.search(path.stem)
        title = re.sub(r"[._]+", " ", path.stem).strip()
        item_id = hashlib.sha256(relative.as_posix().encode()).hexdigest()[:32]
        return MediaItem(
            item_id=item_id,
            media_type=media_type,
            path=path,
            title=title,
            year=int(year_match.group("year")) if year_match else None,
            show_title=show_title,
            season=season,
            episode=episode,
        )
