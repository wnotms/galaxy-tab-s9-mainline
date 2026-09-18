#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the actual payloads of two archived SM-X710 boot-test bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def original_image(blob: bytes) -> bytes:
    if len(blob) < 64:
        raise ValueError("truncated image")
    magic, major, _minor, original_size, vbmeta_offset, vbmeta_size = struct.unpack_from(
        ">4sIIQQQ", blob, len(blob) - 64
    )
    if magic != b"AVBf" or major != 1:
        raise ValueError("invalid AVB footer")
    if not (0 < original_size <= vbmeta_offset):
        raise ValueError("invalid AVB original image size")
    if vbmeta_offset + vbmeta_size > len(blob) - 64:
        raise ValueError("invalid AVB ranges")
    return blob[:original_size]


def align4k(value: int) -> int:
    return (value + 4095) // 4096 * 4096


def inspect_boot(blob: bytes) -> dict[str, object]:
    image = original_image(blob)
    if len(image) < 4096 or image[:8] != b"ANDROID!":
        raise ValueError("invalid Android boot header")
    kernel_size, ramdisk_size, os_version, header_size = struct.unpack_from("<4I", image, 8)
    header_version = struct.unpack_from("<I", image, 40)[0]
    if header_size != 1584 or header_version != 4:
        raise ValueError("expected Android boot header v4")
    kernel = image[4096:4096 + kernel_size]
    ramdisk_off = 4096 + align4k(kernel_size)
    ramdisk = image[ramdisk_off:ramdisk_off + ramdisk_size]

    stream = zlib.decompressobj(31)
    raw_kernel = stream.decompress(kernel)
    if not stream.eof:
        raise ValueError("kernel payload is not a complete gzip stream")
    dtb = stream.unused_data
    gzip_size = len(kernel) - len(dtb)

    if len(raw_kernel) < 64 or raw_kernel[56:60] != b"ARM\x64":
        raise ValueError("decompressed payload is not a raw ARM64 Image")

    text_offset = struct.unpack_from("<Q", raw_kernel, 8)[0]
    image_size = struct.unpack_from("<Q", raw_kernel, 16)[0]
    flags = struct.unpack_from("<Q", raw_kernel, 24)[0]

    return {
        "partition_sha256": sha256(blob),
        "avb_original_size": len(image),
        "boot_kernel_field_size": kernel_size,
        "boot_ramdisk_field_size": ramdisk_size,
        "boot_os_version": os_version,
        "gzip_kernel_size": gzip_size,
        "raw_kernel_size": len(raw_kernel),
        "raw_kernel_sha256": sha256(raw_kernel),
        "arm64_text_offset": text_offset,
        "arm64_image_size_field": image_size,
        "arm64_flags": flags,
        "appended_dtb_size": len(dtb),
        "appended_dtb_sha256": sha256(dtb),
        "boot_ramdisk_sha256": sha256(ramdisk),
    }


def inspect_init_boot(blob: bytes) -> dict[str, object]:
    image = original_image(blob)
    if len(image) < 4096 or image[:8] != b"ANDROID!":
        raise ValueError("invalid init_boot header")
    kernel_size, ramdisk_size, _os_version, header_size = struct.unpack_from("<4I", image, 8)
    header_version = struct.unpack_from("<I", image, 40)[0]
    if header_size != 1584 or header_version != 4 or kernel_size != 0:
        raise ValueError("unexpected init_boot geometry")
    ramdisk = image[4096:4096 + ramdisk_size]
    return {
        "partition_sha256": sha256(blob),
        "avb_original_size": len(image),
        "ramdisk_size": ramdisk_size,
        "ramdisk_sha256": sha256(ramdisk),
    }


def load_bundle(path: Path) -> dict[str, object]:
    path = path.resolve()
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    boot = (path / "boot.img").read_bytes()
    init_boot = (path / "init_boot.img").read_bytes()
    vendor_boot = (path / "vendor_boot.img").read_bytes()
    dtbo = (path / "dtbo.img").read_bytes()

    return {
        "path": str(path),
        "manifest_inputs": manifest.get("inputs", {}),
        "manifest_firmware_dtb_sha256": manifest.get("firmware_dtb_sha256"),
        "boot": inspect_boot(boot),
        "init_boot": inspect_init_boot(init_boot),
        "vendor_boot_sha256": sha256(vendor_boot),
        "dtbo_sha256": sha256(dtbo),
    }


def flatten(prefix: str, value: object, out: dict[str, object]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            flatten(f"{prefix}.{key}" if prefix else key, item, out)
    else:
        out[prefix] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_a", type=Path)
    parser.add_argument("bundle_b", type=Path)
    args = parser.parse_args()

    a = load_bundle(args.bundle_a)
    b = load_bundle(args.bundle_b)

    flat_a: dict[str, object] = {}
    flat_b: dict[str, object] = {}
    flatten("", a, flat_a)
    flatten("", b, flat_b)

    print("A:", a["path"])
    print("B:", b["path"])
    print()
    print("Changed fields:")
    changed = 0
    for key in sorted(set(flat_a) | set(flat_b)):
        if key == "path":
            continue
        va = flat_a.get(key, "<missing>")
        vb = flat_b.get(key, "<missing>")
        if va != vb:
            changed += 1
            print(f"- {key}")
            print(f"    A: {va}")
            print(f"    B: {vb}")

    if not changed:
        print("- none")

    print()
    same_dtb = a["boot"]["appended_dtb_sha256"] == b["boot"]["appended_dtb_sha256"]
    same_kernel = a["boot"]["raw_kernel_sha256"] == b["boot"]["raw_kernel_sha256"]
    print("Summary:")
    print("  raw kernel identical:", "yes" if same_kernel else "no")
    print("  appended DTB identical:", "yes" if same_dtb else "no")
    print(
        "  raw kernel size delta (B-A):",
        int(b["boot"]["raw_kernel_size"]) - int(a["boot"]["raw_kernel_size"]),
        "bytes",
    )
    print(
        "  compressed kernel size delta (B-A):",
        int(b["boot"]["gzip_kernel_size"]) - int(a["boot"]["gzip_kernel_size"]),
        "bytes",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
