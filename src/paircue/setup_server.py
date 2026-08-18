from __future__ import annotations

import hmac
import json
import logging
import secrets
import shutil
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from paircue.config import PairCueSettings
from paircue.services.atomic import atomic_write_bytes

log = logging.getLogger(__name__)

MAX_CONFIG_BYTES = 64 * 1024
MAX_EXISTING_CONFIG_BYTES = 1024 * 1024
ASSETS: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/setup.css": ("setup.css", "text/css; charset=utf-8"),
    "/setup.js": ("setup.js", "text/javascript; charset=utf-8"),
}


@dataclass(slots=True)
class SetupState:
    saved: threading.Event
    output_path: Path | None = None
    backup_path: Path | None = None
    mode: str = ""
    phase: str = "setup"
    message: str = "Finish the setup in your browser."
    outputs: tuple[Path, ...] = ()
    delivered: threading.Event = field(default_factory=threading.Event)
    _progress_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update_progress(
        self,
        phase: str,
        message: str,
        outputs: tuple[Path, ...] = (),
    ) -> None:
        with self._progress_lock:
            self.phase = phase
            self.message = message
            self.outputs = outputs

    def progress_payload(self) -> dict[str, object]:
        with self._progress_lock:
            return {
                "phase": self.phase,
                "message": self.message,
                "outputs": [path.name for path in self.outputs],
                "terminal": self.phase in {"completed", "failed", "cancelled"},
            }


class SetupHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, assets_root: Path, output_path: Path) -> None:
        super().__init__(("127.0.0.1", 0), SetupRequestHandler)
        self.assets_root = assets_root
        self.output_path = output_path
        self.token = secrets.token_urlsafe(32)
        self.state = SetupState(threading.Event())
        self.save_lock = threading.Lock()

    @property
    def origin(self) -> str:
        host, port = cast(tuple[str, int], self.server_address)
        return f"http://{host}:{port}"


class SetupRequestHandler(BaseHTTPRequestHandler):
    server: SetupHTTPServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._trusted_host():
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        path = urlparse(self.path).path
        if path == "/progress":
            supplied = parse_qs(urlparse(self.path).query).get("token", [""])[0]
            if not hmac.compare_digest(supplied, self.server.token):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            payload = self.server.state.progress_payload()
            self._json_response(HTTPStatus.OK, payload)
            if bool(payload["terminal"]):
                self.server.state.delivered.set()
            return
        if path == "/readiness":
            ffmpeg = shutil.which("ffmpeg") is not None
            ffprobe = shutil.which("ffprobe") is not None
            self._json_response(
                HTTPStatus.OK,
                {
                    "ready": ffmpeg and ffprobe,
                    "ffmpeg": ffmpeg,
                    "ffprobe": ffprobe,
                },
            )
            return
        asset = ASSETS.get(path)
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename, content_type = asset
        try:
            content = (self.server.assets_root / filename).read_bytes()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_response(HTTPStatus.OK)
        self._security_headers(content_type, len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urlparse(self.path)
        supplied = parse_qs(parsed.query).get("token", [""])[0]
        if (
            parsed.path != "/config"
            or not self._trusted_host()
            or not hmac.compare_digest(supplied, self.server.token)
            or self.headers.get("Origin") != self.server.origin
        ):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_CONFIG_BYTES:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            payload: Any = json.loads(self.rfile.read(length))
            config = payload.get("config") if isinstance(payload, dict) else None
            mode = payload.get("mode") if isinstance(payload, dict) else None
            if not isinstance(config, str) or not config or "\0" in config:
                raise ValueError("invalid configuration")
            if mode not in {"single", "library"}:
                raise ValueError("invalid setup mode")
            encoded = config.encode("utf-8")
            if len(encoded) > MAX_CONFIG_BYTES:
                raise ValueError("configuration is too large")
            _validate_config(config, mode=mode)
            with self.server.save_lock:
                if self.server.state.saved.is_set():
                    self._json_response(
                        HTTPStatus.CONFLICT,
                        {"saved": False, "message": "PairCue Setup was already saved."},
                    )
                    return
                output, backup = self._save_config(config)
                self.server.state.output_path = output
                self.server.state.backup_path = backup
                self.server.state.mode = mode
                self.server.state.update_progress(
                    "saved",
                    "Your private setup is saved on this device.",
                )
                self._json_response(
                    HTTPStatus.OK,
                    {
                        "saved": True,
                        "filename": output.name,
                        "location": str(output.parent),
                        "backup": backup.name if backup is not None else "",
                    },
                )
                self.server.state.saved.set()
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            log.warning("visual setup could not save configuration (%s)", type(exc).__name__)
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"saved": False, "message": "PairCue could not save this configuration."},
            )
            return

    def _save_config(self, config: str) -> tuple[Path, Path | None]:
        output = self.server.output_path
        output.parent.mkdir(parents=True, exist_ok=True)
        backup: Path | None = None
        if output.exists():
            if (
                output.is_symlink()
                or not output.is_file()
                or output.stat().st_size > MAX_EXISTING_CONFIG_BYTES
            ):
                raise OSError("existing configuration cannot be backed up safely")
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            backup = output.with_name(f"{output.name}.backup-{timestamp}")
            shutil.copy2(output, backup)
            backup.chmod(0o600)
        atomic_write_bytes(output, config.encode("utf-8"), mode=0o600)
        return output, backup

    def _trusted_host(self) -> bool:
        hostname = self.headers.get("Host", "").partition(":")[0]
        return hostname in {"127.0.0.1", "localhost"}

    def _json_response(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._security_headers("application/json; charset=utf-8", len(content))
        self.end_headers()
        self.wfile.write(content)

    def _security_headers(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def log_message(self, format: str, *args: object) -> None:
        return


def run_setup_wizard(
    assets_root: Path,
    output_path: Path,
    *,
    on_single_saved: Callable[[SetupState], None] | None = None,
) -> SetupState:
    server = SetupHTTPServer(assets_root, output_path)
    thread = threading.Thread(target=server.serve_forever, name="paircue-setup", daemon=True)
    thread.start()
    url = f"{server.origin}/?token={server.token}"
    if webbrowser.open(url):
        print("PairCue Setup opened. Finish the three short steps in your browser.")
    else:
        print(f"Open this private local address in a browser: {url}")
    print("Waiting for you to save the setup. Press Ctrl+C to cancel.")
    try:
        while not server.state.saved.wait(0.25):
            continue
        if (
            server.state.output_path is not None
            and server.state.mode == "single"
            and on_single_saved is not None
        ):
            try:
                on_single_saved(server.state)
            except Exception as exc:
                log.error("guided first run failed (%s)", type(exc).__name__)
                server.state.update_progress(
                    "failed",
                    "PairCue could not finish this run. Reopen PairCue to try again.",
                )
            if server.state.phase not in {"completed", "failed", "cancelled"}:
                server.state.update_progress(
                    "failed",
                    "PairCue stopped before finishing. Reopen PairCue to try again.",
                )
            server.state.delivered.wait(timeout=30)
    except KeyboardInterrupt:
        print("\nPairCue Setup cancelled.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return server.state


def _validate_config(config: str, *, mode: str) -> None:
    values: dict[str, str] = {}
    for line in config.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, raw = stripped.partition("=")
        if not separator or not name.startswith("PAIRCUE_"):
            continue
        decoded = json.loads(raw) if raw.startswith('"') else raw
        if not isinstance(decoded, str):
            raise ValueError("configuration values must be strings")
        values[name.removeprefix("PAIRCUE_").casefold()] = decoded
    if mode == "single":
        # One-video learning deliberately bypasses the selected media server, while retaining the
        # user's platform choice in the saved file for the next setup visit.
        values["platform"] = "filesystem"
    PairCueSettings.model_validate(values)
