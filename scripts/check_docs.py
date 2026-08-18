#!/usr/bin/env python3
"""Validate local Markdown links and headings without fetching external pages."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

SKIPPED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "release",
}
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
HTML_TAG = re.compile(r"<[^>]+>")
PUNCTUATION = re.compile(r"[^\w\- ]", re.UNICODE)


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not any(part in SKIPPED_DIRECTORIES for part in path.relative_to(root).parts)
    )


def _anchors(path: Path) -> set[str]:
    counts: dict[str, int] = {}
    anchors: set[str] = set()
    for heading in HEADING.findall(path.read_text(encoding="utf-8")):
        plain = HTML_TAG.sub("", heading).replace("`", "").strip().casefold()
        slug = re.sub(r"-+", "-", PUNCTUATION.sub("", plain).replace(" ", "-"))
        duplicate = counts.get(slug, 0)
        counts[slug] = duplicate + 1
        anchors.add(f"{slug}-{duplicate}" if duplicate else slug)
    return anchors


def check_markdown_links(root: Path) -> list[str]:
    failures: list[str] = []
    for document in markdown_files(root):
        text = document.read_text(encoding="utf-8")
        for raw_destination in MARKDOWN_LINK.findall(text):
            destination = raw_destination.strip("<>")
            parsed = urlsplit(destination)
            if parsed.scheme or destination.startswith(("//", "mailto:")):
                continue
            relative_path = unquote(parsed.path)
            target = document if not relative_path else (document.parent / relative_path).resolve()
            try:
                target.relative_to(root.resolve())
            except ValueError:
                failures.append(
                    f"{document.relative_to(root)}: link leaves the repository: {destination}"
                )
                continue
            if not target.exists():
                failures.append(f"{document.relative_to(root)}: missing target: {destination}")
                continue
            if parsed.fragment and target.is_file() and target.suffix.casefold() == ".md":
                fragment = unquote(parsed.fragment).casefold()
                if fragment not in _anchors(target):
                    failures.append(
                        f"{document.relative_to(root)}: missing heading #{parsed.fragment} in "
                        f"{target.relative_to(root)}"
                    )
    return failures


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    root = _arguments().root.resolve()
    failures = check_markdown_links(root)
    if failures:
        print("Documentation link check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Documentation link check passed for {len(markdown_files(root))} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
