#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate every patch listed in kernel/patches/series.

This is a fast syntax/structure check. It catches malformed unified-diff hunks
before the kernel source tree is cleaned or a build is started. The real build
still performs git apply --check in series order against the pinned Linux tree.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
PATCH_DIR = ROOT / "kernel/patches"
SERIES = PATCH_DIR / "series"
HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$"
)


class PatchError(RuntimeError):
    pass


def series_entries() -> list[str]:
    if not SERIES.is_file():
        raise PatchError(f"missing patch series: {SERIES}")
    result: list[str] = []
    for lineno, raw in enumerate(SERIES.read_text().splitlines(), 1):
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        if name in result:
            raise PatchError(f"{SERIES}:{lineno}: duplicate patch: {name}")
        result.append(name)
    if not result:
        raise PatchError("patch series is empty")
    return result


def validate_patch(path: Path) -> tuple[int, int]:
    if not path.is_file():
        raise PatchError(f"missing patch: {path}")

    lines = path.read_text().splitlines()
    if not any(line.startswith("diff --git ") for line in lines):
        raise PatchError(f"{path}: missing 'diff --git' header")

    hunks = 0
    files = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            files += 1
            i += 1
            continue
        if not line.startswith("@@ "):
            i += 1
            continue

        match = HUNK_RE.match(line)
        if not match:
            raise PatchError(f"{path}:{i + 1}: malformed hunk header: {line}")

        old_expected = int(match.group(2) or "1")
        new_expected = int(match.group(4) or "1")
        old_seen = 0
        new_seen = 0
        hunk_line = i + 1
        hunks += 1
        i += 1

        while i < len(lines):
            body = lines[i]

            if body.startswith("@@ ") or body.startswith("diff --git "):
                break
            if body.startswith("\\ No newline at end of file"):
                i += 1
                continue

            if body == "":
                # A source blank line inside a unified diff must be prefixed
                # with one context/add/remove character. A bare empty line
                # before the declared counts are satisfied makes git apply
                # report a corrupt patch.
                if old_seen < old_expected or new_seen < new_expected:
                    raise PatchError(
                        f"{path}:{i + 1}: bare empty line inside hunk "
                        f"started at line {hunk_line}"
                    )
                break

            prefix = body[0]
            if prefix == " ":
                old_seen += 1
                new_seen += 1
            elif prefix == "-":
                # File headers are outside hunks, so '-' here is removal.
                old_seen += 1
            elif prefix == "+":
                new_seen += 1
            else:
                if old_seen < old_expected or new_seen < new_expected:
                    raise PatchError(
                        f"{path}:{i + 1}: invalid hunk body prefix "
                        f"{body[:1]!r} in hunk started at line {hunk_line}"
                    )
                break

            if old_seen > old_expected or new_seen > new_expected:
                raise PatchError(
                    f"{path}:{i + 1}: hunk count exceeds header "
                    f"(old {old_seen}/{old_expected}, "
                    f"new {new_seen}/{new_expected})"
                )
            i += 1
            if old_seen == old_expected and new_seen == new_expected:
                # Hunk length is authoritative. Stop here so a standard
                # git-format-patch footer ("-- " and version) is not
                # mistaken for hunk body.
                break

        if old_seen != old_expected or new_seen != new_expected:
            raise PatchError(
                f"{path}:{hunk_line}: hunk count mismatch: "
                f"header old={old_expected} new={new_expected}, "
                f"body old={old_seen} new={new_seen}"
            )

    if hunks == 0:
        raise PatchError(f"{path}: contains no hunks")
    return files, hunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only errors",
    )
    args = parser.parse_args()

    try:
        names = series_entries()
        total_files = 0
        total_hunks = 0
        for name in names:
            files, hunks = validate_patch(PATCH_DIR / name)
            total_files += files
            total_hunks += hunks
            if not args.quiet:
                print(f"PASS: {name}: {files} file diff(s), {hunks} hunk(s)")
        if not args.quiet:
            print(
                f"PASS: patch series syntax: {len(names)} patches, "
                f"{total_files} file diff(s), {total_hunks} hunk(s)"
            )
        return 0
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
