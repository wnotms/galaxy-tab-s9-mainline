#!/usr/bin/env python3
"""Read a connected SM-X710 through TWRP ADB; write only host-side files."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time


PHYSICAL = (
    "boot", "init_boot", "vendor_boot", "dtbo", "vbmeta", "vbmeta_system",
    "recovery", "abl", "xbl", "xbl_b", "xbl_config", "xbl_config_b",
    "aop", "aop_config", "tz", "hyp", "devcfg", "qupfw", "cpucp", "shrm",
    "apnhlos", "dsp", "modem", "core_nhlos_a", "persist", "efs", "sec_efs",
)
LOGICAL = ("vendor", "vendor_dlkm", "odm", "system_dlkm", "system_ext", "product")
METADATA = {
    "properties.txt": "getprop",
    "identity.txt": "getprop ro.boot.em.model; getprop ro.bootloader; getprop ro.product.device; getprop ro.boot.verifiedbootstate; getprop ro.boot.vbmeta.device_state; getprop ro.boot.slot_suffix",
    "cmdline.txt": "cat /proc/cmdline",
    "bootconfig.txt": "cat /proc/bootconfig",
    "partitions.txt": "cat /proc/partitions",
    "partition-links.txt": "ls -l /dev/block/by-name",
    "logical-links.txt": "ls -l /dev/block/mapper",
    "mounts.txt": "cat /proc/mounts",
    "meminfo.txt": "cat /proc/meminfo",
    "iomem.txt": "cat /proc/iomem",
    "kernel-version.txt": "cat /proc/version",
    "dmesg.txt": "dmesg",
    "recovery.log": "cat /tmp/recovery.log",
    "recovery.fstab": "cat /etc/recovery.fstab",
    "pstore-list.txt": "ls -la /sys/fs/pstore",
    "block-layout.txt": "for d in /sys/class/block/sd*; do printf '%s ' \"${d##*/}\"; for n in size start ro queue/logical_block_size; do if [ -f \"$d/$n\" ]; then printf '%s=' \"$n\"; cat \"$d/$n\"; fi; done; done",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--layout-only", action="store_true", help="Finish layout reads in an existing verified snapshot")
    args = parser.parse_args()
    os.umask(0o077)
    adb = [args.adb, "-s", args.serial]

    def shell(command):
        return subprocess.run(adb + ["shell", command], capture_output=True, timeout=180)

    def text(command):
        result = shell(command)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace") + result.stdout.decode(errors="replace"))
        return result.stdout.decode(errors="replace").strip()

    model = text("getprop ro.boot.em.model")
    if model != "SM-X710":
        raise SystemExit(f"Expected SM-X710, got {model!r}")
    if "recovery" not in text("getprop ro.bootmode"):
        # Some recovery builds leave bootmode empty; a running TWRP process
        # provides a separate check without changing device state.
        text("pidof recovery")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=args.layout_only, mode=0o700)
    for sub in ("metadata", "partitions", "logical", "layout"):
        (output / sub).mkdir(mode=0o700, exist_ok=args.layout_only)
    manifest = {
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model": model, "bootloader": text("getprop ro.bootloader"),
        "serial": args.serial, "source": "Current device in TWRP; not certified factory images",
        "recovery_note": "recovery.img is the currently installed recovery, expected TWRP",
        "files": [], "errors": [], "partition_inventory": [],
    }
    if args.layout_only:
        manifest = json.loads((output / "manifest.json").read_text())
        if manifest["serial"] != args.serial or manifest["bootloader"] != text("getprop ro.bootloader"):
            raise RuntimeError("Existing snapshot belongs to a different device/firmware")

    def save():
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        (output / "SHA256SUMS").write_text("".join(
            f"{f['sha256']}  {f['file']}\n" for f in manifest["files"]
        ))

    def record(path, source, **extra):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        item = dict(file=str(path.relative_to(output)), source=source,
                    size=path.stat().st_size, sha256=digest.hexdigest(), **extra)
        manifest["files"].append(item)
        save()
        return item

    def stream(arguments, destination, expected=None, source_hash=None, source=None):
        temporary = destination.with_suffix(destination.suffix + ".partial")
        if destination.exists():
            raise RuntimeError(f"Refusing to replace an existing snapshot file: {destination}")
        # exec-out merges the device command's stderr into its binary stream.
        # Toybox dd supports status=none; avoid progress bytes in the payload.
        if arguments[0] == "dd":
            arguments = arguments + ["status=none"]
        if temporary.exists():
            temporary.unlink()
        started = time.monotonic()
        with temporary.open("xb") as target, destination.with_suffix(destination.suffix + ".stderr").open("wb") as errors:
            process = subprocess.run(adb + ["exec-out"] + arguments, stdout=target, stderr=errors, timeout=900)
        if process.returncode:
            raise RuntimeError(f"ADB read failed for {source}: exit {process.returncode}")
        if expected is not None and temporary.stat().st_size != expected:
            raise RuntimeError(f"Length mismatch for {source}: {temporary.stat().st_size} != {expected}")
        digest = hashlib.sha256()
        with temporary.open("rb") as content:
            for chunk in iter(lambda: content.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        host_hash = digest.hexdigest()
        if source_hash is not None and host_hash != source_hash:
            raise RuntimeError(f"SHA-256 mismatch for {source}")
        temporary.rename(destination)
        err = destination.with_suffix(destination.suffix + ".stderr")
        if not err.stat().st_size:
            err.unlink()
        record(destination, source, device_sha256=source_hash,
               verified=source_hash is not None, duration_seconds=round(time.monotonic() - started, 2))

    for name, command in ([] if args.layout_only else METADATA.items()):
        result = shell(command)
        path = output / "metadata" / name
        path.write_bytes(result.stdout.replace(b"\r\n", b"\n"))
        record(path, command, exit_code=result.returncode)
        if result.returncode:
            manifest["errors"].append(dict(stage="metadata", file=name, message=result.stderr.decode(errors="replace")))
    print("Finishing layout metadata" if args.layout_only else "Saved device identity, partition layout and recovery logs", flush=True)

    inventory_command = "for p in /dev/block/by-name/*; do [ -b \"$p\" ] || continue; printf '%s\\t%s\\t%s\\n' \"${p##*/}\" \"$(readlink -f \"$p\")\" \"$(blockdev --getsize64 \"$p\")\"; done"
    manifest["partition_inventory"] = []
    for line in text(inventory_command).splitlines():
        name, device, size = line.split()
        manifest["partition_inventory"].append(dict(name=name, device=device, size=int(size)))
    save()

    special = {
        "recovery-live.dtb": "/sys/firmware/fdt",
        "recovery-config.gz": "/proc/config.gz",
        "last_kmsg.txt": "/proc/last_kmsg",
    }
    for name, source in ([] if args.layout_only else special.items()):
        if shell("test -r " + shlex.quote(source)).returncode:
            manifest["errors"].append(dict(stage="optional", source=source, message="not readable"))
            continue
        stream(["cat", source], output / "metadata" / name, source=source)
    # Recovery live DT is retained as recovery evidence, never labelled as
    # a running stock Android DT.

    total = sum(p["size"] for p in manifest["partition_inventory"] if p["name"] in PHYSICAL)
    for name in LOGICAL:
        total += int(text("blockdev --getsize64 /dev/block/mapper/" + name))
    if shutil.disk_usage(output).free < total + 1024 * 1024 * 1024:
        raise RuntimeError(f"Insufficient free host space for {total} bytes")
    print(f"Selected partition images: {total / 1024**3:.2f} GiB", flush=True)

    selections = (("partitions", PHYSICAL, "/dev/block/by-name/"),
                  ("logical", LOGICAL, "/dev/block/mapper/"))
    for kind, names, base in ([] if args.layout_only else selections):
        for name in names:
            source = base + name
            try:
                size = int(text("blockdev --getsize64 " + source))
                resolved = text("readlink -f " + source)
                print(f"Reading {kind}/{name}.img ({size / 1024**2:.1f} MiB)", flush=True)
                device_hash = text("sha256sum " + source).split()[0]
                if len(device_hash) != 64:
                    raise RuntimeError("Invalid device SHA-256 output")
                stream(["cat", source], output / kind / (name + ".img"),
                       expected=size, source_hash=device_hash, source=source)
                manifest["files"][-1]["device"] = resolved
                save()
                print(f"Verified {name}.img", flush=True)
            except Exception as exc:
                manifest["errors"].append(dict(stage=kind, name=name, message=str(exc)))
                save()
                print(f"ERROR {name}: {exc}", flush=True)

    for lun in ("sda", "sdb", "sdc", "sdd", "sde", "sdf"):
        source = "/dev/block/" + lun
        sector = int(text("blockdev --getss " + source))
        size = int(text("blockdev --getsize64 " + source))
        for position, skip, count in (("primary", 0, 34), ("backup", size // sector - 33, 33)):
            stream(["dd", "if=" + source, "bs=" + str(sector), "skip=" + str(skip), "count=" + str(count)],
                   output / "layout" / f"{lun}-gpt-{position}.bin",
                   expected=sector * count, source=source + f" byte range {skip * sector}:{(skip + count) * sector}")
        manifest.setdefault("lun_geometry", []).append(dict(name=lun, size=size, logical_sector_size=sector))
    stream(["dd", "if=/dev/block/by-name/super", "bs=1048576", "count=4"],
           output / "layout" / "super-prefix-4MiB.bin", expected=4 * 1024 * 1024,
           source="First 4 MiB of super (metadata analysis only, not full super backup)")
    manifest["completed_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
    print(f"COMPLETE {output}; files={len(manifest['files'])}, errors={len(manifest['errors'])}", flush=True)


if __name__ == "__main__":
    main()
