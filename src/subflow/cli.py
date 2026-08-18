from __future__ import annotations

import argparse
import logging
import secrets

import uvicorn

from subflow.api import create_core_app
from subflow.config import DownloadStationSettings, SubFlowSettings
from subflow.downloads_api import create_downloads_app
from subflow.factory import build_runtime
from subflow.services.download_station import DownloadStationClient


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subflow", description="cross-platform bilingual subtitle automation"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("serve", help="run the subtitle service")
    subcommands.add_parser("downloads", help="run the isolated Download Station service")
    subcommands.add_parser("generate-token", help="generate a secure API token")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "generate-token":
        print(secrets.token_urlsafe(48))
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.command == "serve":
        settings = SubFlowSettings()
        runtime = build_runtime(settings)
        app = create_core_app(settings, runtime)
        uvicorn.run(
            app,
            host=settings.api_host,
            port=settings.api_port,
            access_log=False,
            proxy_headers=False,
        )
        return

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
