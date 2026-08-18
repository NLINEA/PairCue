from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any, TypeVar

import httpx


class DownloadStationError(RuntimeError):
    pass


Result = TypeVar("Result")


class DownloadStationClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        destination: str,
    ) -> None:
        self.base_url = base_url
        self.username = username
        self.password = password
        self.destination = destination

    def list_tasks(self) -> list[dict[str, str]]:
        def action(client: httpx.Client, sid: str) -> list[dict[str, str]]:
            data = self._post(
                client,
                "/webapi/DownloadStation/task.cgi",
                {
                    "api": "SYNO.DownloadStation.Task",
                    "version": "1",
                    "method": "list",
                    "_sid": sid,
                },
            )
            return [
                {"title": str(task.get("title") or "?"), "status": str(task.get("status") or "?")}
                for task in data.get("data", {}).get("tasks", [])[:100]
            ]

        return self._with_session(action)

    def add_magnet(self, uri: str) -> bool:
        def action(client: httpx.Client, sid: str) -> bool:
            data = self._post(
                client,
                "/webapi/DownloadStation/task.cgi",
                {
                    "api": "SYNO.DownloadStation.Task",
                    "version": "1",
                    "method": "create",
                    "uri": uri,
                    "destination": self.destination,
                    "_sid": sid,
                },
            )
            return bool(data.get("success"))

        return self._with_session(action)

    def _with_session(self, action: Callable[[httpx.Client, str], Result]) -> Result:
        with httpx.Client(base_url=self.base_url, timeout=20, follow_redirects=False) as client:
            login = self._post(
                client,
                "/webapi/auth.cgi",
                {
                    "api": "SYNO.API.Auth",
                    "version": "3",
                    "method": "login",
                    "account": self.username,
                    "passwd": self.password,
                    "session": "DownloadStation",
                    "format": "sid",
                },
            )
            try:
                sid = str(login["data"]["sid"])
            except (KeyError, TypeError) as exc:
                raise DownloadStationError("Download Station login failed") from exc
            try:
                return action(client, sid)
            finally:
                with suppress(DownloadStationError):
                    self._post(
                        client,
                        "/webapi/auth.cgi",
                        {
                            "api": "SYNO.API.Auth",
                            "version": "1",
                            "method": "logout",
                            "session": "DownloadStation",
                            "_sid": sid,
                        },
                    )

    @staticmethod
    def _post(client: httpx.Client, path: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            response = client.post(path, data=data)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DownloadStationError("Download Station request failed") from exc
        if not isinstance(payload, dict) or not payload.get("success"):
            raise DownloadStationError("Download Station rejected the request")
        return payload
