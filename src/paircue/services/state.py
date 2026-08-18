from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RecentMediaState:
    media_name: str
    status: str
    message: str
    updated_at: str


class StateStore:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS media_state (
                    media_path TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def record(self, media_path: Path, fingerprint: str, status: str, message: str = "") -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO media_state(media_path, fingerprint, status, message, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(media_path) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    status = excluded.status,
                    message = excluded.message,
                    updated_at = excluded.updated_at
                """,
                (str(media_path), fingerprint, status, message[:1000], now),
            )

    def status_for(self, media_path: Path) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM media_state WHERE media_path = ?", (str(media_path),)
            ).fetchone()
        return str(row[0]) if row else None

    def summary(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) FROM media_state GROUP BY status ORDER BY status"
            ).fetchall()
        return {str(status): int(count) for status, count in rows}

    def recent(self, limit: int = 20) -> tuple[RecentMediaState, ...]:
        bounded_limit = max(1, min(limit, 100))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT media_path, status, message, updated_at
                FROM media_state
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        recent: list[RecentMediaState] = []
        for media_path, status, message, updated_at in rows:
            path = Path(str(media_path))
            safe_message = str(message).replace(str(path), path.name)
            for separator in ("/", "\\"):
                safe_message = safe_message.replace(f"{path.parent}{separator}", "")
            recent.append(
                RecentMediaState(
                    media_name=path.name,
                    status=str(status),
                    message=safe_message,
                    updated_at=str(updated_at),
                )
            )
        return tuple(recent)


def media_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"
