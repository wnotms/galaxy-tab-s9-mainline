#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fast local preflight for SM-X710 bring-up scripts and patch files."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

PYTHON_FILES = (
    "scripts/check-bringup.py",
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
    "configfs mountpoint present",
    "configfs primary mount failed",
    "configfs fallback mount failed",
    "GTS9WIFI: USB gadget setup failed",
    "GTS9WIFI: USB gadget skipped because configfs unavailable",
    "GTS9WIFI: UDC bind success",
    "GTS9WIFI: UDC bind timeout",
    "GTS9WIFI: USB NCM local ready",
    "GTS9WIFI: USB host configured",
    "GTS9WIFI: USB host configuration timeout",
    "platform_driver ",
    "platform_device name=",
    "manual_dwc3_bind",
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

    sysfs_mount = init_text.find("mount_checked sysfs sysfs sysfs /sys")
    configfs_probe = init_text.find("configfs mountpoint present")
    configfs_primary = init_text.find(
        "/bin/busybox mount -t configfs none /sys/kernel/config"
    )
    configfs_fallback = init_text.find(
        "/bin/busybox mount -t configfs none /config"
    )
    if min(sysfs_mount, configfs_probe, configfs_primary, configfs_fallback) < 0:
        raise RuntimeError("missing sysfs/configfs diagnostic sequence")
    if not (sysfs_mount < configfs_probe < configfs_primary < configfs_fallback):
        raise RuntimeError(
            "configfs diagnostics must follow sysfs and primary mount must precede fallback"
        )

    for required in (
        "mount_checked devtmpfs devtmpfs devtmpfs /dev",
        "mkdir -p /dev/pts",
        "mount_checked proc proc proc /proc",
        "mount_checked sysfs sysfs sysfs /sys",
        "filesystem available name=",
        "mount table target=",
        "CONFIGFS_ROOT='/config'",
    ):
        if required not in init_text:
            raise RuntimeError("missing pseudo-filesystem diagnostic: " + required)

    if "rc=$?" not in init_text or "/bin/busybox mount -t" not in init_text:
        raise RuntimeError("mount_checked must preserve the real mount return code")
    if "record_usb_platform_state" not in init_text:
        raise RuntimeError("missing platform-device USB diagnostics")
    if "try_manual_dwc3_bind" not in init_text:
        raise RuntimeError("missing manual dwc3-qcom bind diagnostic")

    if "/bin/busybox sleep 1" not in init_text:
        raise RuntimeError("UDC/host wait loops must use explicit BusyBox sleep")
    if "USB UDC test skipped because gadget setup failed" not in init_text:
        raise RuntimeError("gadget failure must gate UDC testing")
    if "\n sleep 1\n" in init_text or "\n  sleep 1\n" in init_text:
        raise RuntimeError("bare sleep 1 found; use /bin/busybox sleep 1")

    print("PASS: initramfs diagnostic markers and control flow")

    print("PASS: bring-up script preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
