#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Download hash-pinned packaging tools; build LZ4 locally without installation."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

root = Path(__file__).resolve().parent.parent
pins = json.loads((root / "device/host-tools.json").read_text())
downloads = root / "work/downloads"
downloads.mkdir(parents=True, exist_ok=True)
for name, filename in (("avbtool", "avbtool.py"), ("lz4", "lz4-v1.10.0.tar.gz")):
    path = downloads / filename
    if not path.exists():
        data = urllib.request.urlopen(pins[name]["url"], timeout=120).read()
        if name == "avbtool":
            data = base64.b64decode(data)
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != pins[name]["sha256"]:
        raise SystemExit("Tool hash mismatch: " + name)
source = root / "work/lz4-1.10.0"
if not source.exists():
    with tarfile.open(downloads / "lz4-v1.10.0.tar.gz") as archive:
        archive.extractall(root / "work", filter="data")
binary = source / "programs/lz4"
if not binary.exists():
    subprocess.run(["make", "-C", str(source), "-j4", "lz4"], check=True)
print("Packaging tools verified under work/")
