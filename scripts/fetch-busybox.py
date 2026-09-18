#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch a pinned Debian ARM64 static BusyBox into the ignored work directory."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import urllib.request

root = Path(__file__).resolve().parent.parent
pin = json.loads((root / "device/busybox-source.json").read_text())
archive = root / "work/downloads/busybox-static-arm64.deb"
archive.parent.mkdir(parents=True, exist_ok=True)
if not archive.exists():
    urllib.request.urlretrieve(pin["url"], archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != pin["SHA256"]:
    raise SystemExit("BusyBox archive SHA256 mismatch")
out = root / "work/busybox-arm64"
out.mkdir(parents=True, exist_ok=True)
subprocess.run(["dpkg-deb", "-x", str(archive), str(out)], check=True)
binary = next(out.glob("**/busybox"))
data = binary.read_bytes()
if data[:4] != b"\x7fELF" or data[4:6] != b"\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
    raise SystemExit("Expected a little-endian ARM64 ELF BusyBox")
# Verify no PT_INTERP: dynamically linked init binaries cannot boot in this archive.
phoff = struct.unpack_from("<Q", data, 32)[0]
phsize, phnum = struct.unpack_from("<HH", data, 54)
if any(struct.unpack_from("<I", data, phoff + i * phsize)[0] == 3 for i in range(phnum)):
    raise SystemExit("BusyBox unexpectedly requires a dynamic loader")
print(binary)
