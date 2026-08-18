#!/usr/bin/env python3
"""Verify that every commit after the merge base is signed off by its author."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

SIGN_OFF = re.compile(r"^Signed-off-by: .+ <([^<>]+)>$", re.IGNORECASE | re.MULTILINE)
GIT = shutil.which("git")


def _git(*arguments: str) -> str:
    if GIT is None:
        raise RuntimeError("git is unavailable")
    result = subprocess.run(  # noqa: S603 - fixed git executable and argument array
        [GIT, *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: check_dco.py BASE HEAD", file=sys.stderr)
        return 2
    base, head = sys.argv[1:]
    merge_base = _git("merge-base", base, head)
    commits = _git("rev-list", f"{merge_base}..{head}").splitlines()
    failures: list[str] = []
    for commit in commits:
        author_email = _git("show", "-s", "--format=%ae", commit).casefold()
        message = _git("show", "-s", "--format=%B", commit)
        signers = {match.casefold() for match in SIGN_OFF.findall(message)}
        if author_email not in signers:
            failures.append(commit)
    if failures:
        print("The following commits need an author-matching Signed-off-by line:", file=sys.stderr)
        for commit in failures:
            print(f"- {commit}", file=sys.stderr)
        return 1
    print(f"DCO sign-off verified for {len(commits)} commit(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
