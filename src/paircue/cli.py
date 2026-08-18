from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import uvicorn
from pydantic import ValidationError

from paircue.api import create_core_app
from paircue.config import DownloadStationSettings, PairCueSettings
from paircue.diagnostics import run_diagnostics
from paircue.downloads_api import create_downloads_app
from paircue.factory import build_pipeline, build_runtime
from paircue.models import MediaItem
from paircue.services.download_station import DownloadStationClient
from paircue.services.subtitle_files import merge_bilingual_subtitles, parse_srt, write_srt
from paircue.setup_server import SetupState, run_setup_wizard


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paircue", description="cross-platform bilingual subtitle automation"
    )
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("serve", help="run the subtitle service")
    subcommands.add_parser("downloads", help="run the isolated Download Station service")
    subcommands.add_parser("generate-token", help="generate a secure API token")
    setup = subcommands.add_parser("setup", help="open the private visual setup wizard")
    setup.add_argument("--no-open", action="store_true", help="print its local path instead")
    doctor = subcommands.add_parser("doctor", help="check configuration before starting PairCue")
    doctor.add_argument("--json", action="store_true", help="print machine-readable results")
    doctor.add_argument("--config", type=Path, help="read settings from this environment file")
    learn = subcommands.add_parser(
        "learn",
        help="create a bilingual learning track for one local video",
    )
    learn.add_argument(
        "media",
        type=Path,
        nargs="?",
        help="local movie or episode file; omit it to choose from a window",
    )
    learn.add_argument("--from", dest="source_language", help="spoken/source language tag")
    learn.add_argument("--to", dest="target_language", help="learning language tag")
    learn.add_argument(
        "--order",
        choices=("target-first", "source-first"),
        help="which language appears on the first line",
    )
    learn.add_argument("--title", help="title used for subtitle metadata fallback")
    learn.add_argument("--year", type=int, help="release year used for subtitle metadata fallback")
    learn.add_argument("--config", type=Path, help="read settings from this environment file")
    pair = subcommands.add_parser(
        "pair", help="merge two existing SRT files into one bilingual SRT"
    )
    pair.add_argument("source", type=Path, help="source-language SRT")
    pair.add_argument("target", type=Path, help="learning-language SRT")
    pair.add_argument("-o", "--output", type=Path, required=True, help="bilingual output SRT")
    pair.add_argument(
        "--order",
        choices=("target-first", "source-first"),
        default="target-first",
        help="which language appears on the first line",
    )
    pair.add_argument("--tolerance-ms", type=int, default=350)
    pair.add_argument("--min-match-ratio", type=float, default=0.7)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command is None:
        return _setup(no_open=False)
    if args.command == "generate-token":
        print(secrets.token_urlsafe(48))
        return 0
    if args.command == "pair":
        return _pair(args)
    if args.command == "setup":
        return _setup(no_open=args.no_open)
    if args.command == "doctor":
        return _doctor(as_json=args.json, config=args.config)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.command == "learn":
        return _learn(args)
    if args.command == "serve":
        settings = PairCueSettings()
        runtime = build_runtime(settings)
        app = create_core_app(settings, runtime)
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            access_log=False,
            proxy_headers=False,
        )
        return 0

    download_settings = DownloadStationSettings()
    client = DownloadStationClient(
        base_url=download_settings.url,
        username=download_settings.username,
        password=download_settings.password.get_secret_value(),
        destination=download_settings.destination,
    )
    app = create_downloads_app(download_settings, client)
    uvicorn.run(
        app,
        host=download_settings.host,
        port=download_settings.port,
        access_log=False,
        proxy_headers=False,
    )
    return 0


def _doctor(*, as_json: bool, config: Path | None = None) -> int:
    try:
        environment_file = _environment_file(config)
        settings = _load_settings(environment_file)
    except (OSError, ValidationError) as exc:
        if isinstance(exc, OSError):
            errors = [
                {
                    "location": "config",
                    "message": str(exc),
                    "type": "config_file_error",
                }
            ]
        else:
            errors = [
                {
                    "location": ".".join(str(part) for part in error["loc"]),
                    "message": str(error["msg"]),
                    "type": str(error["type"]),
                }
                for error in exc.errors(include_input=False, include_url=False)
            ]
        if as_json:
            print(json.dumps({"ready": False, "configuration_errors": errors}))
        else:
            print("PairCue is not ready:", file=sys.stderr)
            for error in errors:
                print(f"[error] {error['location']}: {error['message']}", file=sys.stderr)
        return 1
    checks = run_diagnostics(settings)
    ready = not any(check.status == "error" for check in checks)
    if as_json:
        print(
            json.dumps(
                {"ready": ready, "checks": [check.as_dict() for check in checks]},
                ensure_ascii=False,
            )
        )
    else:
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
        print("PairCue is ready." if ready else "PairCue needs attention before it can start.")
    return 0 if ready else 1


def _setup(*, no_open: bool) -> int:
    setup_page = Path(__file__).with_name("setup") / "index.html"
    if not setup_page.is_file():
        print("PairCue setup files are missing from this installation.", file=sys.stderr)
        return 1
    if no_open:
        print(setup_page)
        return 0
    exit_code = 0

    def continue_with_one_video(state: SetupState) -> None:
        nonlocal exit_code
        state.update_progress("choosing", "Choose one movie or episode in the file window.")
        print("Choose one video to create your first learning track.")
        selected = _choose_media_path()
        if selected is None:
            state.update_progress(
                "cancelled",
                "No video was selected. Your setup is saved, so you can try again anytime.",
            )
            print("No video selected. Your setup is saved; run `paircue learn` whenever ready.")
            return
        state.update_progress(
            "processing",
            f"Creating bilingual subtitles for {selected.name}…",
        )
        exit_code = _learn(
            argparse.Namespace(
                media=selected,
                config=state.output_path,
                source_language=None,
                target_language=None,
                order=None,
                title=None,
                year=None,
                reveal_output=True,
                setup_state=state,
            )
        )

    state = run_setup_wizard(
        setup_page.parent,
        _default_setup_output(),
        on_single_saved=continue_with_one_video,
    )
    if state.output_path is None:
        return 1
    print(f"Saved private configuration: {state.output_path}")
    if state.backup_path is not None:
        print(f"Previous configuration backed up to: {state.backup_path}")
    return exit_code


def _pair(args: argparse.Namespace) -> int:
    try:
        source = args.source.resolve(strict=True)
        target = args.target.resolve(strict=True)
        output = args.output.resolve(strict=False)
        if output in {source, target}:
            raise ValueError("output must not overwrite either input subtitle")
        if not 0 <= args.tolerance_ms <= 2_000:
            raise ValueError("tolerance must be between 0 and 2000 milliseconds")
        if not 0.5 <= args.min_match_ratio <= 1:
            raise ValueError("minimum match ratio must be between 0.5 and 1")
        merged = merge_bilingual_subtitles(
            parse_srt(source),
            parse_srt(target),
            order=args.order,
            tolerance_ms=args.tolerance_ms,
            min_match_ratio=args.min_match_ratio,
        )
        write_srt(output, merged.subtitles)
    except (OSError, ValueError) as exc:
        print(f"PairCue could not pair these subtitles: {exc}", file=sys.stderr)
        return 2
    print(
        f"Created {output} with {len(merged.subtitles)} bilingual cues "
        f"({merged.source_match_ratio:.0%}/{merged.target_match_ratio:.0%} matched)."
    )
    return 0


def _learn(args: argparse.Namespace) -> int:
    try:
        selected_media = args.media or _choose_media_path()
        if selected_media is None:
            raise ValueError("no video was selected")
        media = selected_media.expanduser().resolve(strict=True)
        if not media.is_file():
            raise ValueError("media path is not a file")
        if args.year is not None and not 1878 <= args.year <= 2100:
            raise ValueError("year must be between 1878 and 2100")
        title = (args.title or media.stem).strip()
        if not title:
            raise ValueError("title must not be empty")
    except (OSError, ValueError) as exc:
        message = f"PairCue could not open this video: {exc}"
        _update_guided_progress(args, "failed", message)
        print(message, file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="paircue-learn-") as temporary_state:
        try:
            environment_file = _environment_file(args.config)
            base_settings = _load_settings(
                environment_file,
                platform="filesystem",
                media_root=media.parent,
                state_dir=Path(temporary_state),
                api_host="127.0.0.1",
                webhook_enabled=False,
            )
            settings = _load_settings(
                environment_file,
                platform="filesystem",
                media_root=media.parent,
                state_dir=Path(temporary_state),
                api_host="127.0.0.1",
                webhook_enabled=False,
                source_language=args.source_language or base_settings.source_language,
                target_language=args.target_language or base_settings.target_language,
                bilingual_order=args.order or base_settings.bilingual_order,
            )
            pipeline = build_pipeline(settings)
        except (OSError, ValidationError, ValueError) as exc:
            message = f"PairCue configuration is not ready: {_safe_error(exc)}"
            _update_guided_progress(args, "failed", message)
            print(message, file=sys.stderr)
            return 2

        try:
            result = pipeline.process(
                MediaItem(
                    item_id="local",
                    media_type="movie",
                    path=media,
                    title=title,
                    year=args.year,
                )
            )
        finally:
            pipeline.close()

    destination = sys.stderr if result.status == "failed" else sys.stdout
    print(f"{result.status}: {result.message}", file=destination)
    for output in result.outputs:
        print(f"created: {output}")
    if (
        result.status != "failed"
        and result.outputs
        and bool(getattr(args, "reveal_output", False))
    ):
        _reveal_path(result.outputs[-1])
    guided = isinstance(getattr(args, "setup_state", None), SetupState)
    has_bilingual = any(path.name.casefold().endswith(".cc.srt") for path in result.outputs)
    if result.status == "failed":
        _update_guided_progress(args, "failed", result.message)
        return 1
    if guided and not has_bilingual:
        _update_guided_progress(
            args,
            "failed",
            "PairCue found only one language track. Add the other language or enable translation, "
            "then reopen PairCue.",
            result.outputs,
        )
        return 1
    _update_guided_progress(args, "completed", result.message, result.outputs)
    return 0


def _update_guided_progress(
    args: argparse.Namespace,
    phase: str,
    message: str,
    outputs: tuple[Path, ...] = (),
) -> None:
    state = getattr(args, "setup_state", None)
    if isinstance(state, SetupState):
        state.update_progress(phase, message, outputs)


def _safe_error(error: Exception) -> str:
    if isinstance(error, ValidationError):
        messages = [
            str(item["msg"])
            for item in error.errors(include_input=False, include_url=False)
        ]
        return "; ".join(messages)
    return str(error)


def _environment_file(config: Path | None) -> Path:
    if config is None:
        return Path(".env")
    resolved = config.resolve(strict=True)
    if not resolved.is_file():
        raise OSError(f"configuration path is not a file: {resolved}")
    return resolved


def _default_setup_output() -> Path:
    """Use the working folder for CLI installs and the user config folder for desktop builds."""

    if not bool(getattr(sys, "frozen", False)):
        return Path.cwd() / "paircue.env"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PairCue" / "paircue.env"
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        root = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
        return root / "PairCue" / "paircue.env"
    config_home = os.environ.get("XDG_CONFIG_HOME")
    root = Path(config_home) if config_home else Path.home() / ".config"
    return root / "paircue" / "paircue.env"


def _load_settings(environment_file: Path, **overrides: object) -> PairCueSettings:
    """Cross the dynamic BaseSettings source boundary while retaining validated output."""

    settings_factory: Any = PairCueSettings
    return cast(PairCueSettings, settings_factory(_env_file=environment_file, **overrides))


def _choose_media_path() -> Path | None:
    """Open a native file chooser, with a drag-and-drop terminal fallback."""

    commands: list[list[str]] = []
    if sys.platform == "darwin" and Path("/usr/bin/osascript").is_file():
        commands.append(
            [
                "/usr/bin/osascript",
                "-e",
                'POSIX path of (choose file with prompt "Choose one movie or episode for PairCue")',
            ]
        )
    elif os.name == "nt":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        if powershell:
            commands.append(
                [
                    powershell,
                    "-NoProfile",
                    "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$d=New-Object System.Windows.Forms.OpenFileDialog; "
                    "$d.Title='Choose one movie or episode for PairCue'; "
                    "$d.Filter='Video files|*.mkv;*.mp4;*.m4v;*.avi;*.mov;*.webm|All files|*.*'; "
                    "if($d.ShowDialog() -eq 'OK'){Write-Output $d.FileName}",
                ]
            )
    else:
        zenity = shutil.which("zenity")
        if zenity:
            commands.append(
                [
                    zenity,
                    "--file-selection",
                    "--title=Choose one movie or episode for PairCue",
                    "--file-filter=Video files | *.mkv *.mp4 *.m4v *.avi *.mov *.webm",
                    "--file-filter=All files | *",
                ]
            )
        kdialog = shutil.which("kdialog")
        if not zenity and kdialog:
            commands.append(
                [
                    kdialog,
                    "--getopenfilename",
                    "",
                    "Video files (*.mkv *.mp4 *.m4v *.avi *.mov *.webm)",
                    "--title",
                    "Choose one movie or episode for PairCue",
                ]
            )

    for command in commands:
        try:
            result = subprocess.run(  # noqa: S603 - fixed platform chooser and argument array
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        selected = result.stdout.strip()
        if result.returncode == 0 and selected:
            return Path(selected)
        return None

    if sys.stdin.isatty():
        selected = input("Drag one video file here, then press Return: ").strip()
        if selected:
            return Path(selected.strip("'\""))
    return None


def _reveal_path(path: Path) -> None:
    """Reveal a completed subtitle in the native file manager when available."""

    command: list[str] | None = None
    if sys.platform == "darwin" and Path("/usr/bin/open").is_file():
        command = ["/usr/bin/open", "-R", str(path)]
    elif os.name == "nt":
        explorer = shutil.which("explorer")
        if explorer:
            command = [explorer, "/select,", str(path)]
    else:
        opener = shutil.which("xdg-open")
        if opener:
            command = [opener, str(path.parent)]
    if command is None:
        return
    try:
        subprocess.run(  # noqa: S603 - fixed platform file-manager command and argument array
            command,
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
