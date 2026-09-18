#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify final Android headers, appended DTB, AVB hashes and partition sizes."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parent.parent
def require(condition, message):
    if not condition:
        raise ValueError(message)
def original_image(blob):
    require(len(blob) >= 64, "Truncated image")
    magic, major, minor, length, offset, size = struct.unpack_from(">4sIIQQQ", blob, len(blob)-64)
    require(magic == b"AVBf" and major == 1, "Invalid AVB footer")
    require(0 < length <= offset and offset + size <= len(blob)-64, "Invalid AVB ranges")
    return blob[:length]
def inspect_boot(blob):
    require(len(blob) >= 4096 and blob[:8] == b"ANDROID!", "Invalid Android boot header")
    kernel, ramdisk, os_version, size = struct.unpack_from("<4I",blob,8)
    require(size == 1584 and struct.unpack_from("<I",blob,40)[0] == 4, "Expected boot header v4")
    align = lambda n: (n + 4095)//4096*4096
    require(len(blob) == 4096 + align(kernel) + align(ramdisk), "Boot payload length mismatch")
    return blob[4096:4096+kernel], blob[4096+align(kernel):4096+align(kernel)+ramdisk]
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle",type=Path)
    args = parser.parse_args()
    profile = json.loads((ROOT/"device/boot-profile.json").read_text())
    manifest = json.loads((args.bundle/"manifest.json").read_text())
    require(manifest["model"] == "SM-X710", "Wrong model")
    images = {}
    avb = ROOT/"work/downloads/avbtool.py"
    for name in ("boot","init_boot","vendor_boot","dtbo"):
        file = args.bundle/(name+'.img'); data = file.read_bytes()
        require(len(data) == profile["partition_sizes"][name], name+" partition size mismatch")
        require(hashlib.sha256(data).hexdigest() == manifest["files"][file.name]["sha256"], name+" hash mismatch")
        images[name] = original_image(data)
        subprocess.run([sys.executable,str(avb),"verify_image","--image",str(file)],check=True,capture_output=True)
    kernel, ramdisk = inspect_boot(images['boot'])
    require(not ramdisk,"boot unexpectedly contains a ramdisk")
    stream = zlib.decompressobj(31); raw = stream.decompress(kernel)
    require(stream.eof and raw[56:60] == b"ARM\x64", "Invalid compressed ARM64 kernel")
    dtb = stream.unused_data
    require(len(dtb)>40 and struct.unpack_from('>I',dtb)[0] == 0xd00dfeed and struct.unpack_from('>I',dtb,4)[0] == len(dtb), "Invalid appended DTB")
    # Validate the DTB actually inside the bundle, even if the build tree changed.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        extracted=Path(directory)/'appended.dtb'; extracted.write_bytes(dtb)
        subprocess.run([sys.executable,str(ROOT/'scripts/check-device-tree.py'),str(extracted)],check=True)
    generic_kernel, generic = inspect_boot(images['init_boot'])
    require(not generic_kernel and generic[:4] == bytes.fromhex('02214c18'), "Expected legacy LZ4 generic ramdisk")
    vendor = images['vendor_boot']
    require(vendor[:8] == b'VNDRBOOT',"Invalid vendor_boot magic")
    version,page,ka,ra,ramdisk_size = struct.unpack_from('<5I',vendor,8)
    hs,dtbs,da,ts,count,entry_size,cs = struct.unpack_from('<IIQ4I',vendor,2096)
    expected=profile['boot_images']['vendor_boot']
    require((version,page,hs,count,entry_size,ts)==(4,4096,2128,1,108,108),"Invalid vendor_boot layout")
    require((ka,ra,da)==tuple(int(expected[k],16) for k in ('kernel_addr','ramdisk_addr','dtb_addr')),"Vendor addresses differ from S9 snapshot")
    require(struct.unpack_from('<I',vendor,2076)[0]==int(expected['tags_addr'],16),"Vendor tags address mismatch")
    require(vendor[2080:2096].split(b'\0',1)[0].decode()==expected['name'],"Vendor header name mismatch")
    align=lambda n:(n+4095)//4096*4096
    require(len(vendor)==4096+align(ramdisk_size)+align(dtbs)+align(ts)+align(cs),"Vendor payload length mismatch")
    pos=4096+align(ramdisk_size)
    require(vendor[4096:4100]==bytes.fromhex('02214c18'),"Vendor ramdisk is not legacy LZ4")
    require(vendor[pos:pos+dtbs]==dtb,"Vendor and appended DTB differ")
    pos+=align(dtbs)
    require(struct.unpack_from('<3I',vendor,pos)==(ramdisk_size,0,1),"Unexpected platform ramdisk table")
    pos+=align(ts)
    require(vendor[pos:pos+cs].decode()==expected['bootconfig'],"Vendor bootconfig mismatch")
    require(images['dtbo']==bytes(4096),"Expected the experimental appended-DTB fallback payload")
    lz4=ROOT/'work/lz4-1.10.0/programs/lz4'
    for payload in (generic,vendor[4096:4096+ramdisk_size]):
        unpacked=subprocess.run([str(lz4),'-dc'],input=payload,check=True,capture_output=True).stdout
        require(unpacked.startswith(b'070701') and b'TRAILER!!!' in unpacked,"Invalid ramdisk archive")
    print('PASS: four partition-sized images, AVB hashes, Android v4 geometry, identical S9 DTBs and both legacy-LZ4 ramdisks')
if __name__=='__main__':
    try:
        main()
    except (ValueError,subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
