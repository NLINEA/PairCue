"""Desktop entry point that is safe when an app has no attached terminal."""

from __future__ import annotations

import os
import sys
from typing import TextIO, cast


def _open_null(mode: str) -> TextIO:
    return cast(
        TextIO,
        open(os.devnull, mode, encoding="utf-8"),  # noqa: PTH123 - OS null device
    )


def ensure_standard_streams() -> None:
    """Provide harmless streams for Windows noconsole and macOS app launches."""

    if sys.stdin is None:
        sys.stdin = _open_null("r")
    if sys.stdout is None:
        sys.stdout = _open_null("w")
    if sys.stderr is None:
        sys.stderr = _open_null("w")


def main() -> int:
    ensure_standard_streams()
    from paircue.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
