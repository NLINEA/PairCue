from __future__ import annotations

import json
import re
from pathlib import Path

SLUG = re.compile(r"[^a-z0-9]+")


class GlossaryStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def load(self, context: str) -> dict[str, str]:
        slug = SLUG.sub("-", context.lower()).strip("-")[:80] or "default"
        path = self.directory / f"{slug}.json"
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"glossary must contain a JSON object: {path.name}")
        glossary: dict[str, str] = {}
        for source, target in raw.items():
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError(f"glossary entries must be strings: {path.name}")
            if source.strip() and target.strip():
                glossary[source.strip()] = target.strip()
        return glossary
