from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


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


def media_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"
