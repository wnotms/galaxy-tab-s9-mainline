#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fast local preflight for SM-X710 bring-up scripts and patch files."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

PYTHON_FILES = (
    "scripts/twrp-entry-marker-test.py",
    "scripts/check-patch-series.py",
    "scripts/build-initramfs.py",
    "scripts/build-boot-bundle.py",
    "scripts/verify-boot-bundle.py",
)

SHELL_FILES = (
    ("sh", "initramfs/init"),
    ("bash", "scripts/build-kernel.sh"),
    ("bash", "scripts/twrp-restore-original.sh"),
)

REQUIRED_INIT_MARKERS = (
    "GTS9WIFI: initramfs init entered",
    "GTS9WIFI: UDC bind success",
    "GTS9WIFI: USB NCM local ready",
    "GTS9WIFI: USB host configured",
    "GTS9WIFI: USB host configuration timeout",
)


def check_python(path: Path) -> None:
    source = path.read_text()
    compile(source, str(path), "exec")


def check_shell(shell: str, path: Path) -> None:
    subprocess.run(
        [shell, "-n", str(path)],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-patch-series.py"), "--quiet"],
        cwd=ROOT,
        check=True,
    )

    for rel in PYTHON_FILES:
        path = ROOT / rel
        check_python(path)
        print("PASS: Python syntax:", rel)

    for shell, rel in SHELL_FILES:
        path = ROOT / rel
        check_shell(shell, path)
        print(f"PASS: {shell} syntax: {rel}")

    init_text = (ROOT / "initramfs/init").read_text()
    for marker in REQUIRED_INIT_MARKERS:
        if marker not in init_text:
            raise RuntimeError("missing required initramfs diagnostic marker: " + marker)
    print("PASS: initramfs diagnostic markers")

    print("PASS: bring-up script preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
