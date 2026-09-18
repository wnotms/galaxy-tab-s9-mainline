#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Package a mainline bring-up kernel using the owner's Android v4 geometry.

Based on the S9 Ultra appended-DTB fallback. This bootloader route has NOT
been tested on SM-X710. This script only creates local files.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PAGE = 4096
CMDLINE = "rdinit=/init console=null loglevel=8 ignore_loglevel printk.devkmsg=on clk_ignore_unused pd_ignore_unused regulator_ignore_unused panic=0 bootconfig"
def padded(data, page=PAGE):
    return data + b"\0" * (-len(data) % page)
def boot_v4(kernel=b"", ramdisk=b"", os_version=0):
    header = b"ANDROID!" + struct.pack("<4I", len(kernel), len(ramdisk), os_version, 1584)
    header += b"\0" * 16 + struct.pack("<I", 4) + b"\0" * 1536 + struct.pack("<I", 0)
    assert len(header) == 1584
    return padded(header) + padded(kernel) + padded(ramdisk)
def vendor_v4(dtb, ramdisk, profile):
    original = profile["boot_images"]["vendor_boot"]
    config = original["bootconfig"].encode()
    cmdline = CMDLINE.encode()
    header = b"VNDRBOOT" + struct.pack("<5I", 4, PAGE, int(original["kernel_addr"],16), int(original["ramdisk_addr"],16), len(ramdisk))
    header += cmdline.ljust(2048, b"\0") + struct.pack("<I",int(original["tags_addr"],16)) + original["name"].encode().ljust(16,b"\0")
    header += struct.pack("<IIQ4I",2128,len(dtb),int(original["dtb_addr"],16),108,1,108,len(config))
    assert len(header) == 2128
    table = struct.pack("<3I",len(ramdisk),0,1) + b"\0" * 96
    return padded(header) + padded(ramdisk) + padded(dtb) + padded(table) + padded(config)
def empty_newc():
    name = b"TRAILER!!!\0"
    numbers = (0,0,0,0,1,0,0,0,0,0,0,len(name),0)
    data = b"070701" + "".join(f"{v:08x}" for v in numbers).encode() + name
    return data + b"\0" * (-len(data) % 512)
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=ROOT / "artifacts/kernel/Image")
    parser.add_argument("--dtb", type=Path, default=ROOT / "artifacts/kernel/sm8550-samsung-gts9wifi.dtb")
    parser.add_argument("--initramfs", type=Path, default=ROOT / "artifacts/initramfs/initramfs.cpio.gz")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/boot-bundle")
    args = parser.parse_args()
    profile = json.loads((ROOT / "device/boot-profile.json").read_text())
    if profile["model"] != "SM-X710" or profile["board_id"] != [0x10008,4]:
        sys.exit("This bundle builder supports only the captured SM-X710 board04 profile")
    subprocess.run([sys.executable, str(ROOT / "scripts/check-device-tree.py"), str(args.dtb)], check=True)
    kernel = args.kernel.read_bytes()
    if len(kernel) < 64 or kernel[56:60] != b"ARM\x64":
        sys.exit("Kernel is not a raw ARM64 Image")
    initrd = gzip.decompress(args.initramfs.read_bytes())
    if initrd[:6] != b"070701":
        sys.exit("Expected a gzip/newc initramfs")
    lz4 = ROOT / "work/lz4-1.10.0/programs/lz4"
    avb = ROOT / "work/downloads/avbtool.py"
    if not lz4.exists() or not avb.exists():
        sys.exit("Run python3 scripts/stage-host-tools.py first")
    def compress(data):
        return subprocess.run([str(lz4), "-l", "-12", "-c"], input=data, capture_output=True, check=True).stdout
    dtb = args.dtb.read_bytes()
    args.output.mkdir(parents=True, exist_ok=True)
    blobs = {
        "boot": boot_v4(gzip.compress(kernel,mtime=0) + dtb, os_version=profile["boot_images"]["boot"]["os_version"]),
        "init_boot": boot_v4(ramdisk=compress(initrd)),
        "vendor_boot": vendor_v4(dtb,compress(empty_newc()),profile),
        # Ultra's tested fallback deliberately avoids an Android DT table.
        # Do not accidentally combine mainline with the stock Samsung overlays.
        "dtbo": bytes(PAGE),
    }
    for name, blob in blobs.items():
        size = profile["partition_sizes"][name]
        if len(blob) > size - 69632:
            sys.exit(f"{name} exceeds its captured partition size including AVB metadata")
        path = args.output / (name + ".img")
        path.write_bytes(blob)
        subprocess.run([sys.executable,str(avb),"add_hash_footer","--image",str(path),
                        "--partition_name",name,"--partition_size",str(size),
                        "--salt",hashlib.sha256(blob).hexdigest()],check=True)
    report = dict(model="SM-X710", profile="board04", hardware_boot_tested=False,
                  bootloader_route="Experimental Ultra appended-DTB fallback; invalid DT-table payload",
                  vbmeta="Not generated or modified; owner's captured vbmeta has verification-disabled flag 2",
                  source_pin=json.loads((ROOT/"device/sources.json").read_text())["linux_commit"],
                  inputs={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.kernel,args.dtb,args.initramfs)},
                  files={name+'.img':dict(size=(args.output/(name+'.img')).stat().st_size,sha256=hashlib.sha256((args.output/(name+'.img')).read_bytes()).hexdigest()) for name in blobs})
    (args.output/"manifest.json").write_text(json.dumps(report,indent=2)+'\n')
    (args.output/"SHA256SUMS").write_text(''.join(f"{item['sha256']}  {name}\n" for name,item in report['files'].items()))
    print(args.output)
if __name__ == "__main__":
    main()
