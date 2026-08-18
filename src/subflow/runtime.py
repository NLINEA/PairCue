from __future__ import annotations

import logging
import queue
import threading

from subflow.models import MediaItem
from subflow.services.pipeline import SubtitlePipeline
from subflow.services.plex import PlexClient

log = logging.getLogger(__name__)


class JobCoordinator:
    def __init__(self, pipeline: SubtitlePipeline, max_size: int = 1000) -> None:
        self.pipeline = pipeline
        self._queue: queue.Queue[MediaItem | None] = queue.Queue(maxsize=max_size)
        self._pending: set[str] = set()
        self._guard = threading.Lock()
        self._worker: threading.Thread | None = None

    def start(self) -> None:
        if self._worker is not None:
            return
        self._worker = threading.Thread(target=self._run, name="subflow-worker", daemon=True)
        self._worker.start()

    def submit(self, item: MediaItem) -> bool:
        with self._guard:
            if item.queue_key in self._pending:
                return False
            self._pending.add(item.queue_key)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            with self._guard:
                self._pending.discard(item.queue_key)
            raise RuntimeError("subtitle job queue is full") from None
        return True

    def stop(self) -> None:
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=10)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            try:
                result = self.pipeline.process(item)
                log.info("%s: %s", item.context_label, result.message)
            except Exception:
                log.exception("worker failed before processing %s", item.context_label)
            finally:
                with self._guard:
                    self._pending.discard(item.queue_key)
                self._queue.task_done()


class CoreRuntime:
    def __init__(
        self,
        plex: PlexClient,
        coordinator: JobCoordinator,
        scan_interval_seconds: int,
    ) -> None:
        self.plex = plex
        self.coordinator = coordinator
        self.scan_interval_seconds = scan_interval_seconds
        self._stop = threading.Event()
        self._poller: threading.Thread | None = None

    def start(self) -> None:
        self.coordinator.start()
        self._poller = threading.Thread(target=self._poll, name="subflow-poller", daemon=True)
        self._poller.start()

    def stop(self) -> None:
        self._stop.set()
        if self._poller is not None:
            self._poller.join(timeout=10)
        self.coordinator.stop()
        self.plex.close()

    def scan_now(self) -> int:
        submitted = 0
        for item in self.plex.scan_items():
            submitted += int(self.coordinator.submit(item))
        return submitted

    def submit_rating_key(self, rating_key: str) -> bool:
        item = self.plex.item_for_rating_key(rating_key)
        return self.coordinator.submit(item) if item is not None else False

    def _poll(self) -> None:
        while not self._stop.is_set():
            try:
                count = self.scan_now()
                log.info("Plex scan queued %s item(s)", count)
            except Exception:
                log.exception("Plex scan failed")
            self._stop.wait(self.scan_interval_seconds)
