#!/usr/bin/env python3
"""Extract boot payloads and device trees from a completed/local snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct


def align(size, page):
    return (size + page - 1) // page * page


def cstring(data):
    return data.split(b"\0", 1)[0].decode(errors="replace")


def parse_fdt(blob):
    header = struct.unpack_from(">10I", blob)
    assert header[0] == 0xD00DFEED and header[1] <= len(blob)
    strings = blob[header[3]:header[3] + header[8]]
    position = header[2]
    stack = []
    nodes = {}
    while True:
        token = struct.unpack_from(">I", blob, position)[0]
        position += 4
        if token == 1:
            end = blob.index(0, position)
            stack.append(blob[position:end].decode())
            position = align(end + 1, 4)
            nodes.setdefault("/" + "/".join(stack[1:]), {})
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, offset = struct.unpack_from(">II", blob, position)
            position += 8
            name = strings[offset:strings.index(0, offset)].decode()
            nodes["/" + "/".join(stack[1:])][name] = blob[position:position + size]
            position = align(position + size, 4)
        elif token == 9:
            break
        elif token != 4:
            raise ValueError(f"Unexpected FDT token {token}")
    return nodes


def property_value(value):
    if not value:
        return True
    if value[-1] == 0 and all(v == 0 or 32 <= v < 127 or v in (9, 10, 13) for v in value):
        return value.rstrip(b"\0").decode().split("\0")
    if len(value) % 4 == 0:
        return [f"0x{v:x}" for v in struct.unpack(">" + str(len(value) // 4) + "I", value)]
    return {"hex_bytes": value.hex()}


def summarize_fdt(blob):
    nodes = parse_fdt(blob)
    interesting = {}
    for path, properties in nodes.items():
        if path.startswith(("/__fixups__", "/__local_fixups__")):
            continue
        if path in ("/", "/chosen") or re.search(r"memory@|reserved-memory|touchscreen@|wacom@|GTS9_ANA38407_AMSA10FA01", path):
            interesting[path] = {k: property_value(v) for k, v in properties.items() if len(v) < 512}
    return {"node_count": len(nodes), "nodes": interesting}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    root = args.snapshot.resolve()
    out = root / "unpacked"
    out.mkdir(exist_ok=True)
    report = {"boot_images": {}, "dtbo_entries": [], "device_trees": {}, "files": []}

    def write(name, payload):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        report["files"].append({"file": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})

    for name in ("boot", "init_boot"):
        blob = (root / "partitions" / (name + ".img")).read_bytes()
        assert blob[:8] == b"ANDROID!"
        kernel, ramdisk, os_version, header_size = struct.unpack_from("<4I", blob, 8)
        version = struct.unpack_from("<I", blob, 40)[0]
        assert version == 4 and header_size == 1584
        report["boot_images"][name] = dict(header_version=version, header_size=header_size,
                                         kernel_size=kernel, ramdisk_size=ramdisk, os_version=os_version,
                                         cmdline=cstring(blob[44:1580]), page_size=4096)
        position = 4096
        if kernel:
            write(name + "/kernel.bin", blob[position:position + kernel])
        position += align(kernel, 4096)
        if ramdisk:
            payload = blob[position:position + ramdisk]
            write(name + "/ramdisk.bin", payload)
            report["boot_images"][name]["ramdisk_magic"] = payload[:4].hex()

    blob = (root / "partitions/vendor_boot.img").read_bytes()
    assert blob[:8] == b"VNDRBOOT"
    version, page, kernel_addr, ramdisk_addr, ramdisk = struct.unpack_from("<5I", blob, 8)
    header_size, dtb_size, dtb_addr, table_size, entry_count, entry_size, config_size = struct.unpack_from("<IIQ4I", blob, 2096)
    assert version == 4 and header_size == 2128 and page == 4096
    position = align(header_size, page)
    payload = blob[position:position + ramdisk]
    write("vendor_boot/vendor-ramdisk.bin", payload)
    position += align(ramdisk, page)
    dtbs = blob[position:position + dtb_size]
    write("vendor_boot/dtb.img", dtbs)
    position += align(dtb_size, page)
    table = blob[position:position + table_size]
    write("vendor_boot/ramdisk-table.bin", table)
    position += align(table_size, page)
    bootconfig = blob[position:position + config_size]
    write("vendor_boot/bootconfig.txt", bootconfig)
    write("vendor_boot/cmdline.txt", blob[28:2076].split(b"\0", 1)[0] + b"\n")
    entries = []
    for i in range(entry_count):
        entry = table[i * entry_size:(i + 1) * entry_size]
        size, offset, kind = struct.unpack_from("<3I", entry)
        entries.append(dict(size=size, offset=offset, type=kind, name=cstring(entry[12:44]),
                            board_id=list(struct.unpack_from("<16I", entry, 44))))
    report["boot_images"]["vendor_boot"] = dict(header_version=version, page_size=page,
        tags_addr=hex(struct.unpack_from("<I", blob, 2076)[0]), name=cstring(blob[2080:2096]),
        kernel_addr=hex(kernel_addr), ramdisk_addr=hex(ramdisk_addr), dtb_addr=hex(dtb_addr),
        vendor_ramdisk_size=ramdisk, ramdisk_magic=payload[:4].hex(), dtb_size=dtb_size,
        cmdline=cstring(blob[28:2076]), bootconfig=cstring(bootconfig), ramdisk_entries=entries)
    offset = 0
    index = 0
    while offset < len(dtbs):
        assert dtbs[offset:offset + 4] == b"\xd0\x0d\xfe\xed"
        size = struct.unpack_from(">I", dtbs, offset + 4)[0]
        fdt = dtbs[offset:offset + size]
        assert len(fdt) == size
        name = f"vendor_boot/dtb-{index}.dtb"
        write(name, fdt)
        report["device_trees"][name] = summarize_fdt(fdt)
        offset += size
        index += 1

    blob = (root / "partitions/dtbo.img").read_bytes()
    magic, total, header_size, entry_size, count, entries_offset, page, version = struct.unpack_from(">8I", blob)
    assert magic == 0xD7B7AB1E and total <= len(blob)
    for i in range(count):
        size, offset, device_id, revision, *custom = struct.unpack_from(">8I", blob, entries_offset + i * entry_size)
        payload = blob[offset:offset + size]
        assert len(payload) == size
        name = f"dtbo/overlay-{i}.dtbo"
        write(name, payload)
        summary = summarize_fdt(payload)
        report["dtbo_entries"].append(dict(index=i, size=size, id=device_id, revision=revision,
                                            custom=custom, root=summary["nodes"]["/"]))
        report["device_trees"][name] = summary
    live = root / "metadata/recovery-live.dtb"
    if live.exists():
        report["device_trees"]["recovery-live.dtb"] = summarize_fdt(live.read_bytes())

    vbmeta = (root / "partitions/vbmeta.img").read_bytes()
    assert vbmeta[:4] == b"AVB0"
    report["vbmeta_flags"] = struct.unpack_from(">I", vbmeta, 120)[0]
    report["recovery_note"] = "Live DT/cmdline and recovery image are from TWRP; Android live DT is not collected."
    (out / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (out / "SHA256SUMS").write_text("".join(f"{f['sha256']}  {f['file']}\n" for f in report["files"]))
    print(json.dumps({"boot_images": report["boot_images"], "dtbo_entries": report["dtbo_entries"],
                      "vbmeta_flags": report["vbmeta_flags"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
