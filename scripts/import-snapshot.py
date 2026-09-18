#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import a verified owner's SM-X710 snapshot, excluding private device data."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct

ROOT = Path(__file__).resolve().parent.parent
parse_fdt = runpy.run_path(str(ROOT / "scripts/analyze-device-snapshot.py"))["parse_fdt"]
def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--merged-dtb", type=Path, required=True,
                        help="vendor_boot/dtb-0.dtb merged with physical DTBO overlay 1")
    args = parser.parse_args()
    manifest = json.loads((args.snapshot / "manifest.json").read_text())
    if manifest["model"] != "SM-X710" or manifest.get("errors"):
        raise SystemExit("Expected a completed SM-X710 snapshot without extraction errors")
    needed = {f"partitions/{n}.img" for n in ("boot", "init_boot", "vendor_boot", "dtbo", "vbmeta")}
    items = {item["file"]: item for item in manifest["files"]}
    for name in needed:
        if sha(args.snapshot / name) != items[name]["sha256"]:
            raise SystemExit("Snapshot hash mismatch: " + name)
    analysis = json.loads((args.snapshot / "unpacked/analysis.json").read_text())
    profile = dict(model="SM-X710", codename="gts9wifi", board_id=[0x10008, 4],
                   supported_revision_range=[4, 0x20], source="Owner snapshot from TWRP, not certified factory firmware",
                   bootloader=manifest["bootloader"], header_version=4, page_size=4096,
                   partition_sizes={name.split('/')[1][:-4]: items[name]["size"] for name in sorted(needed)},
                   source_images={name: items[name]["sha256"] for name in sorted(needed)},
                   boot_images=analysis["boot_images"], dtbo_entries=analysis["dtbo_entries"],
                   vbmeta_flags=analysis["vbmeta_flags"])
    # No serial, EFS, persist, properties, command line or recovery logs are imported.
    (ROOT / "device/boot-profile.json").write_text(json.dumps(profile, indent=2) + "\n")
    nodes = parse_fdt(args.merged_dtb.read_bytes())
    selected = {}
    for path, properties in nodes.items():
        if path.startswith(("/__", "/chosen")):
            continue
        if not (path.startswith("/reserved-memory/") or path in ("/soc/clocks/xo_board", "/soc/clocks/sleep_clk") or
                any(part in path.lower() for part in ("touchscreen@49", "wacom@", "eusb2_repeater@4f", "gts9_ana38407_amsa10fa01", "sdhci@8804000"))):
            continue
        fields = {}
        for name, value in properties.items():
            if name in ("phandle", "linux,phandle"):
                continue
            if ("command" in name or "cmds" in name or "table" in name) and len(value) > 64:
                # Save panel command streams locally for subsequent driver work.
                directory = ROOT / "artifacts/panel"
                directory.mkdir(parents=True, exist_ok=True)
                basename = hashlib.sha256(path.encode()).hexdigest()[:12] + "-" + name.replace(',', '_') + ".bin"
                (directory / basename).write_bytes(value)
                fields[name] = {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest(), "local_file": "artifacts/panel/" + basename}
            elif name in ("compatible", "status", "label", "sec,firmware_name", "qcom,mdss-dsi-panel-name", "samsung,disp-model", "samsung,panel-vendor", "qcom,mdss-dsi-panel-type"):
                fields[name] = value.rstrip(b"\0").decode(errors="replace").split("\0")
            elif not value:
                fields[name] = True
            elif len(value) % 4 == 0:
                fields[name] = list(struct.unpack(">" + "I" * (len(value) // 4), value))
            else:
                fields[name] = {"hex_bytes": value.hex()}
        selected[path] = fields
    (ROOT / "device/stock-hardware.json").write_text(json.dumps({
        "source": "Current vendor_boot base DTB 0 + current physical DTBO entry 1; not recovery's embedded DTBO",
        "merged_dtb_sha256": sha(args.merged_dtb), "nodes": selected,
    }, indent=2) + "\n")
    print(f"Imported boot profile and {len(selected)} hardware nodes; private snapshot remains under artifacts/")
if __name__ == "__main__":
    main()
