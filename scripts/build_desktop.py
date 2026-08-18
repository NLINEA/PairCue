#!/usr/bin/env python3
"""Build and stage a self-contained PairCue desktop release for the current OS."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, default=Path("dist/desktop"))
    parser.add_argument("--work-dir", type=Path, default=Path("build/desktop"))
    parser.add_argument("--stage-dir", type=Path, default=Path("release/stage"))
    return parser.parse_args()


def _scoped(root: Path, candidate: Path) -> Path:
    resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(f"desktop build path must stay inside the repository: {resolved}")
    return resolved


def _labels() -> tuple[str, str]:
    system = {"Darwin": "macOS", "Windows": "windows", "Linux": "linux"}.get(
        platform.system()
    )
    if system is None:
        raise RuntimeError(f"unsupported desktop build system: {platform.system()}")
    machine = platform.machine().casefold()
    architecture = "arm64" if machine in {"arm64", "aarch64"} else "x64"
    return system, architecture


def _built_payload(dist_dir: Path) -> tuple[Path, Path]:
    if sys.platform == "darwin":
        payload = dist_dir / "PairCue.app"
        executable = payload / "Contents" / "MacOS" / "PairCue"
    elif sys.platform == "win32":
        payload = dist_dir / "PairCue.exe"
        executable = payload
    else:
        payload = dist_dir / "PairCue"
        executable = payload
    if not payload.exists() or not executable.is_file():
        raise RuntimeError(f"PyInstaller did not create the expected desktop payload: {payload}")
    return payload, executable


def _run(command: list[str], root: Path) -> None:
    subprocess.run(  # noqa: S603 - every build command is assembled from repository paths
        command,
        cwd=root,
        check=True,
        timeout=180,
    )


def main() -> int:
    arguments = _arguments()
    root = Path(__file__).resolve().parents[1]
    dist_dir = _scoped(root, arguments.dist_dir)
    work_dir = _scoped(root, arguments.work_dir)
    stage_parent = _scoped(root, arguments.stage_dir)
    system, architecture = _labels()
    stage = stage_parent / f"PairCue-{system}-{architecture}"

    try:
        import PyInstaller.__main__
    except ImportError as exc:
        raise RuntimeError("install PairCue's release dependencies before building") from exc

    for target in (dist_dir, work_dir, stage_parent):
        if target.exists():
            shutil.rmtree(target)
    dist_dir.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    stage.mkdir(parents=True)

    options = [
        str(root / "src" / "paircue" / "desktop.py"),
        "--name=PairCue",
        "--windowed",
        "--noupx",
        "--noconfirm",
        "--clean",
        f"--paths={root / 'src'}",
        "--collect-data=paircue",
        f"--distpath={dist_dir}",
        f"--workpath={work_dir}",
        f"--specpath={work_dir}",
    ]
    if sys.platform == "darwin":
        options.extend(("--onedir", "--osx-bundle-identifier=io.paircue.desktop"))
    else:
        options.append("--onefile")
    PyInstaller.__main__.run(options)

    payload, executable = _built_payload(dist_dir)
    _run([str(executable), "setup", "--no-open"], root)
    if executable.stat().st_size < 1_000_000:
        raise RuntimeError("desktop executable is unexpectedly small")

    destination = stage / payload.name
    if payload.is_dir():
        shutil.copytree(payload, destination, symlinks=True)
    else:
        shutil.copy2(payload, destination)
    for document in ("LICENSE", "THIRD_PARTY_NOTICES.md", "DESKTOP_README.md"):
        shutil.copy2(root / document, stage / document)

    _run(
        [
            sys.executable,
            "-m",
            "scripts.collect_runtime_licenses",
            str(stage / "THIRD_PARTY_LICENSES"),
        ],
        root,
    )
    _run(
        [
            sys.executable,
            "-m",
            "scripts.collect_runtime_licenses",
            str(stage / "BUILD_TOOL_LICENSES"),
            "--only",
            "pyinstaller",
            "pyinstaller-hooks-contrib",
        ],
        root,
    )
    _run(
        [
            sys.executable,
            "-m",
            "scripts.check_runtime_licenses",
            "--sbom",
            str(stage / "paircue-sbom.cdx.json"),
        ],
        root,
    )
    (stage / "BUILD-INFO.txt").write_text(
        f"PairCue {version('paircue')} desktop beta\nPlatform: {system} {architecture}\n"
        f"Python: {sys.version.split()[0]}\nFFmpeg bundled: no\n",
        encoding="utf-8",
    )
    print(stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
