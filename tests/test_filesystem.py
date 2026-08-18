from pathlib import Path

from paircue.services.filesystem import FilesystemSource


def test_filesystem_scans_video_files_and_infers_episode_context(tmp_path: Path) -> None:
    movie = tmp_path / "Movies" / "Film (2024).mkv"
    episode = tmp_path / "Shows" / "Language Club" / "Season 02" / "Lesson.S02E03.mp4"
    subtitle = episode.with_suffix(".srt")
    movie.parent.mkdir(parents=True)
    episode.parent.mkdir(parents=True)
    movie.write_bytes(b"movie")
    episode.write_bytes(b"episode")
    subtitle.write_text("subtitle", encoding="utf-8")

    source = FilesystemSource(media_root=tmp_path, extensions=(".mkv", ".mp4"))
    items = source.scan_items()

    assert len(items) == 2
    by_path = {item.path: item for item in items}
    assert by_path[movie].media_type == "movie"
    assert by_path[movie].year == 2024
    assert by_path[episode].context_label == "Language Club S02E03"
    assert source.item_for_id(by_path[episode].item_id) == by_path[episode]


def test_filesystem_skips_symlinks_outside_media_root(tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    outside = tmp_path / "outside.mkv"
    media_root.mkdir()
    outside.write_bytes(b"outside")
    (media_root / "escape.mkv").symlink_to(outside)

    source = FilesystemSource(media_root=media_root, extensions=(".mkv",))

    assert source.scan_items() == []
