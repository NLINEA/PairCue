from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class KeyedLockPool:
    """Serialize work per media path while allowing unrelated items to run independently."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def acquire(self, key: str) -> Iterator[None]:
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            yield
