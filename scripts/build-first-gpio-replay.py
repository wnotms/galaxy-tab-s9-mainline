#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Replay the archived first SM-X710 kernel, changing only the TLMM DT property.

Offline only: requires the private first-test archive and staged host tools.
Never uses the current kernel build or current initramfs as baseline inputs.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parent.parent
FIRST_BOOT_SHA = "c3b3fc4a4b8b26f131e69258d12de5587e442b8c0a6e477d2fc59a3c381d0993"
FIRST_IMAGE_SHA = "93cdf5c9fdbd0f5a74d9c7c54294a78fb4df0977beab543d5e7f8724874bfc7a"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def reserve_map(blob):
    pos = struct.unpack_from(">I", blob, 16)[0]
    pairs = []
    while pos + 16 <= len(blob):
        pair = struct.unpack_from(">QQ", blob, pos)
        pairs.append(pair)
        pos += 16
        if pair == (0, 0):
            return pairs
    raise ValueError("Unterminated FDT reserve-map")


def vendor_dtb(payload):
    size = struct.unpack_from("<I", payload, 2100)[0]
    ramdisk = struct.unpack_from("<I", payload, 24)[0]
    pos = 4096 + (ramdisk + 4095) // 4096 * 4096
    return pos, size, payload[pos:pos + size]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=ROOT / "artifacts/boot-tests/first-sm-x710/tested-bundle")
    parser.add_argument("--dtb", type=Path, default=ROOT / "artifacts/test11/sm8550-samsung-gts9wifi.dtb")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/first-gpio-replay")
    args = parser.parse_args()
    require(not args.output.exists(), "Output already exists; preserve earlier evidence")
    verify = runpy.run_path(str(ROOT / "scripts/verify-boot-bundle.py"))
    parse = runpy.run_path(str(ROOT / "scripts/analyze-device-snapshot.py"))["parse_fdt"]
    manifest = json.loads((args.baseline / "manifest.json").read_text())
    images = {}
    for name in ("boot", "init_boot", "vendor_boot", "dtbo"):
        data = (args.baseline / (name + ".img")).read_bytes()
        entry = manifest["files"][name + ".img"]
        require(len(data) == entry["size"] and sha(data) == entry["sha256"], "Baseline changed: " + name)
        images[name] = verify["original_image"](data)
    require(manifest["files"]["boot.img"]["sha256"] == FIRST_BOOT_SHA, "Not the actual first-test archive")
    kernel, _ = verify["inspect_boot"](images["boot"])
    stream = zlib.decompressobj(31)
    raw = stream.decompress(kernel)
    original_dtb = stream.unused_data
    require(stream.eof and sha(raw) == FIRST_IMAGE_SHA, "Not the original first-test Image")
    require(sha(original_dtb) == manifest["inputs"]["artifacts/kernel/sm8550-samsung-gts9wifi.dtb"], "First DTB mismatch")
    _, _, embedded_dtb = vendor_dtb(images["vendor_boot"])
    require(embedded_dtb == original_dtb, "First vendor DTB differs from appended DTB")
    cfg_start = raw.index(b"IKCFG_ST") + 8
    config = gzip.decompress(raw[cfg_start:raw.index(b"IKCFG_ED", cfg_start)])
    _, generic = verify["inspect_boot"](images["init_boot"])
    initrd = subprocess.run([str(ROOT / "work/lz4-1.10.0/programs/lz4"), "-dc"], input=generic, capture_output=True, check=True).stdout
    compressed_initrd = gzip.compress(initrd, mtime=0)
    require(sha(compressed_initrd) == manifest["inputs"]["artifacts/initramfs/initramfs.cpio.gz"], "Original initramfs hash mismatch")
    candidate = args.dtb.read_bytes()
    old, new = parse(original_dtb), parse(candidate)
    tlmm = "/soc@0/pinctrl@f100000"
    require(new[tlmm]["compatible"] == b"qcom,sm8550-tlmm\0", "Wrong TLMM node")
    require(new[tlmm].pop("gpio-reserved-ranges") == struct.pack(">II", 36, 4), "Wrong GPIO reservation")
    require(new == old and reserve_map(candidate) == reserve_map(original_dtb), "Unexpected additional DT change")
    args.output.mkdir(parents=True)
    for name, data in [("baseline-Image", raw), ("baseline.config", config), ("baseline.dtb", original_dtb), ("baseline-initramfs.cpio.gz", compressed_initrd), ("sm8550-samsung-gts9wifi.dtb", candidate)]:
        (args.output / name).write_bytes(data)
    subprocess.run([sys.executable, str(ROOT / "scripts/build-boot-bundle.py"), "--kernel", str(args.output / "baseline-Image"), "--dtb", str(args.output / "sm8550-samsung-gts9wifi.dtb"), "--initramfs", str(args.output / "baseline-initramfs.cpio.gz"), "--output", str(args.output)], check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/verify-boot-bundle.py"), str(args.output)], check=True)
    for name in ("init_boot.img", "dtbo.img"):
        require((args.output / name).read_bytes() == (args.baseline / name).read_bytes(), "Changed immutable image: " + name)
    new_boot = verify["original_image"]((args.output / "boot.img").read_bytes())
    new_kernel, _ = verify["inspect_boot"](new_boot)
    new_stream = zlib.decompressobj(31)
    require(new_stream.decompress(new_kernel) == raw and new_stream.unused_data == candidate, "Final boot payload changed")
    require(kernel[:-len(original_dtb)] == new_kernel[:-len(candidate)], "Compressed kernel bytes changed")
    # Only kernel_size may change in the boot header.
    require(images["boot"][:8] == new_boot[:8] and images["boot"][12:4096] == new_boot[12:4096], "Boot header changed beyond kernel_size")
    new_vendor = verify["original_image"]((args.output / "vendor_boot.img").read_bytes())
    old_pos, old_size, _ = vendor_dtb(images["vendor_boot"])
    pos, size, final_dtb = vendor_dtb(new_vendor)
    require(final_dtb == candidate and pos == old_pos, "Final vendor DTB mismatch")
    require(images["vendor_boot"][:2100] == new_vendor[:2100] and images["vendor_boot"][2104:pos] == new_vendor[2104:pos], "Vendor header, cmdline or ramdisk changed")
    align = lambda n: (n + 4095) // 4096 * 4096
    require(images["vendor_boot"][pos + align(old_size):] == new_vendor[pos + align(size):], "Vendor table or bootconfig changed")
    final_manifest = json.loads((args.output / "manifest.json").read_text())
    final_manifest["kernel_provenance"] = {"mode": "exact archived first-test raw Image", "archive_boot_sha256": FIRST_BOOT_SHA, "raw_image_sha256": FIRST_IMAGE_SHA, "kernel_patch_count": 4, "later_diagnostic_patches_present": False}
    final_manifest["replay_validation"] = {"baseline_image_set": "first-sm-x710", "functional_delta": "TLMM gpio-reserved-ranges=<36 4> only", "compressed_kernel_identical": True, "embedded_config_sha256": sha(config), "initramfs_identical": True, "init_boot_dtbo_byte_identical": True, "vendor_cmdline_addresses_ramdisk_bootconfig_identical": True, "all_other_dtb_nodes_properties_and_reserve_map_identical": True}
    (args.output / "manifest.json").write_text(json.dumps(final_manifest, indent=2) + "\n")
    (args.output / "vendor_boot-final.dtb").write_bytes(final_dtb)
    print("PASS: exact first kernel/config/initramfs/packing; only GPIO DT reservation differs")


if __name__ == "__main__":
    main()
