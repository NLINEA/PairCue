from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from subflow.languages import language_matches, observed_language_tag

log = logging.getLogger(__name__)


def _required_binary(name: str) -> str:
    binary = shutil.which(name)
    if binary is None:
        raise FileNotFoundError(f"required executable is unavailable: {name}")
    return binary


TEXT_SUBTITLE_CODECS = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text"}


def ensure_media_path(path: Path, media_root: Path) -> Path:
    resolved_root = media_root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not resolved.is_relative_to(resolved_root):
        raise ValueError("media path is not a file inside MEDIA_ROOT")
    return resolved


class EmbeddedSubtitleExtractor:
    def extract(
        self,
        media_path: Path,
        languages: set[str] | None = None,
    ) -> tuple[Path, ...]:
        probe = subprocess.run(  # noqa: S603 - fixed executable and argv; no shell
            [
                _required_binary("ffprobe"),
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_streams",
                "-select_streams",
                "s",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0:
            log.debug("ffprobe found no readable subtitle tracks for %s", media_path.name)
            return ()
        streams = json.loads(probe.stdout).get("streams", [])
        outputs: list[Path] = []
        for subtitle_index, stream in enumerate(streams):
            codec = str(stream.get("codec_name") or "").lower()
            if codec not in TEXT_SUBTITLE_CODECS:
                continue
            language = str(stream.get("tags", {}).get("language") or "").lower()
            mapped = observed_language_tag(language)
            if languages is not None:
                mapped = next(
                    (requested for requested in languages if language_matches(language, requested)),
                    None,
                )
            if mapped is None:
                continue
            target = media_path.parent / f"{media_path.stem}.{mapped}.srt"
            if target.exists():
                continue
            temporary = self._temporary_srt(target)
            try:
                result = subprocess.run(  # noqa: S603 - fixed executable and argv; no shell
                    [
                        _required_binary("ffmpeg"),
                        "-v",
                        "error",
                        "-y",
                        "-i",
                        str(media_path),
                        "-map",
                        f"0:s:{subtitle_index}",
                        "-c:s",
                        "srt",
                        str(temporary),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=90,
                    check=False,
                )
                if result.returncode == 0 and temporary.stat().st_size > 10:
                    os.replace(temporary, target)
                    outputs.append(target)
            finally:
                temporary.unlink(missing_ok=True)
        return tuple(outputs)

    @staticmethod
    def _temporary_srt(target: Path) -> Path:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".srt",
            delete=False,
        ) as handle:
            path = Path(handle.name)
        path.unlink(missing_ok=True)
        return path


class SubtitleSynchronizer:
    def sync(self, media_path: Path, subtitle_path: Path) -> bool:
        temporary = EmbeddedSubtitleExtractor._temporary_srt(subtitle_path)
        try:
            result = subprocess.run(  # noqa: S603 - fixed executable and argv; no shell
                [
                    _required_binary("ffsubsync"),
                    str(media_path),
                    "-i",
                    str(subtitle_path),
                    "-o",
                    str(temporary),
                    "--skip-sync-on-low-quality",
                ],
                capture_output=True,
                text=True,
                timeout=360,
                check=False,
            )
            if result.returncode != 0 or not temporary.exists() or temporary.stat().st_size <= 10:
                return False
            os.replace(temporary, subtitle_path)
            return True
        except FileNotFoundError:
            log.warning("ffsubsync is unavailable; keeping original timing")
            return False
        finally:
            temporary.unlink(missing_ok=True)
