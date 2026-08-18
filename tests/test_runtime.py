from pathlib import Path

import pytest

from paircue.runtime import CoreRuntime


class DummyState:
    def summary(self) -> dict[str, int]:
        return {}

    def recent(self, limit: int) -> tuple[()]:
        return ()


class DummyPipeline:
    def __init__(self) -> None:
        self.state = DummyState()

    def close(self) -> None:
        return None


class DummyCoordinator:
    def __init__(self) -> None:
        self.pipeline = DummyPipeline()
        self.submitted: list[object] = []

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def counts(self) -> tuple[int, int]:
        return 0, 0

    def submit(self, item: object) -> bool:
        self.submitted.append(item)
        return True


class DummySource:
    platform = "filesystem"

    def __init__(self, items: list[Path] | None = None, *, failure: bool = False) -> None:
        self.items = items or []
        self.failure = failure

    def scan_items(self) -> list[Path]:
        if self.failure:
            raise OSError("private path must not reach the dashboard")
        return self.items

    def close(self) -> None:
        return None


def test_runtime_reports_a_successful_scan_without_paths(tmp_path: Path) -> None:
    coordinator = DummyCoordinator()
    runtime = CoreRuntime(DummySource([tmp_path / "Movie.mkv"]), coordinator, 1800)  # type: ignore[arg-type]

    assert runtime.scan_now() == 1

    snapshot = runtime.status_snapshot()
    assert snapshot.scan_status == "ready"
    assert snapshot.scan_message == "Latest scan queued 1 item."


def test_runtime_turns_scan_exceptions_into_safe_dashboard_guidance() -> None:
    runtime = CoreRuntime(DummySource(failure=True), DummyCoordinator(), 1800)  # type: ignore[arg-type]

    with pytest.raises(OSError):
        runtime.scan_now()

    snapshot = runtime.status_snapshot()
    assert snapshot.scan_status == "error"
    assert "Check the platform connection" in snapshot.scan_message
    assert "private path" not in snapshot.scan_message
