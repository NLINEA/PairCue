import sys
from typing import TextIO, cast

from paircue.desktop import ensure_standard_streams


def test_desktop_entry_provides_streams_without_a_terminal() -> None:
    original_streams = sys.stdin, sys.stdout, sys.stderr
    replacements: tuple[TextIO, TextIO, TextIO] | None = None
    try:
        sys.stdin = None  # type: ignore[assignment]
        sys.stdout = None  # type: ignore[assignment]
        sys.stderr = None  # type: ignore[assignment]

        ensure_standard_streams()

        replacements = (
            cast(TextIO, sys.stdin),
            cast(TextIO, sys.stdout),
            cast(TextIO, sys.stderr),
        )
        assert all(stream is not None for stream in replacements)
    finally:
        sys.stdin, sys.stdout, sys.stderr = original_streams
        if replacements is not None:
            for stream in replacements:
                stream.close()
