#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a deterministic gzip/newc diagnostic initramfs without root privileges."""
import gzip
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
result = subprocess.run([sys.executable, str(root / "scripts/fetch-busybox.py")], check=True, text=True, capture_output=True)
busybox = Path(result.stdout.strip())
archive = bytearray()
def entry(name, data=b"", mode=0o40755, inode=1, rdevmajor=0, rdevminor=0):
    encoded = name.encode() + b"\0"
    numbers = (inode, mode, 0, 0, 1, 0, len(data), 0, 0, rdevmajor, rdevminor, len(encoded), 0)
    archive.extend(b"070701" + "".join(f"{v:08x}" for v in numbers).encode() + encoded)
    archive.extend(b"\0" * (-len(archive) % 4))
    archive.extend(data)
    archive.extend(b"\0" * (-len(archive) % 4))
for i, directory in enumerate(("bin", "sbin", "dev", "proc", "sys", "run", "tmp"), 1):
    entry(directory, inode=i)
entry("bin/busybox", busybox.read_bytes(), 0o100755, 8)
entry("bin/sh", b"busybox", 0o120777, 9)
entry("init", (root / "initramfs/init").read_bytes(), 0o100755, 10)
entry("dev/console", mode=0o20600, inode=11, rdevmajor=5, rdevminor=1)
entry("dev/null", mode=0o20666, inode=12, rdevmajor=1, rdevminor=3)
entry("dev/kmsg", mode=0o20600, inode=13, rdevmajor=1, rdevminor=11)
entry("TRAILER!!!", mode=0, inode=0)
archive.extend(b"\0" * (-len(archive) % 512))
out = root / "artifacts/initramfs/initramfs.cpio.gz"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(gzip.compress(bytes(archive), mtime=0))
print(out)
