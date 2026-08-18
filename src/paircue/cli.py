from __future__ import annotations

import argparse
import json
import logging
import secrets
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from paircue.api import create_core_app
from paircue.config import DownloadStationSettings, PairCueSettings
from paircue.diagnostics import run_diagnostics
from paircue.downloads_api import create_downloads_app
from paircue.factory import build_runtime
from paircue.services.download_station import DownloadStationClient
from paircue.services.subtitle_files import merge_bilingual_subtitles, parse_srt, write_srt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paircue", description="cross-platform bilingual subtitle automation"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("serve", help="run the subtitle service")
    subcommands.add_parser("downloads", help="run the isolated Download Station service")
    subcommands.add_parser("generate-token", help="generate a secure API token")
    doctor = subcommands.add_parser("doctor", help="check configuration before starting PairCue")
    doctor.add_argument("--json", action="store_true", help="print machine-readable results")
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
    if args.command == "generate-token":
        print(secrets.token_urlsafe(48))
        return 0
    if args.command == "pair":
        return _pair(args)
    if args.command == "doctor":
        return _doctor(as_json=args.json)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
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


def _doctor(*, as_json: bool) -> int:
    try:
        settings = PairCueSettings()
    except ValidationError as exc:
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
