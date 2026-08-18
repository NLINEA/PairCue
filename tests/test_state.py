from pathlib import Path

from paircue.services.state import StateStore


def test_state_summary_and_recent_hide_parent_paths(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state" / "paircue.sqlite3")
    first = tmp_path / "private" / "Movie.mkv"
    second = tmp_path / "private" / "Episode.mkv"
    store.record(first, "1:1", "completed", f"translated {first}")
    sidecar = second.with_suffix(".en.srt")
    store.record(second, "2:2", "failed", f"could not read {sidecar}")

    assert store.summary() == {"completed": 1, "failed": 1}
    recent = store.recent()
    assert {row.media_name for row in recent} == {"Movie.mkv", "Episode.mkv"}
    assert all(str(tmp_path) not in row.media_name for row in recent)
    assert all(str(tmp_path) not in row.message for row in recent)
    assert any("Episode.en.srt" in row.message for row in recent)
