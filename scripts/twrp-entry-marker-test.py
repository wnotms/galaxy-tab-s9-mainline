#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build, flash, collect and restore the SM-X710 ARM64 entry-marker test.

The matching head.S patch writes G9E1301..G9E1305 directly into Samsung's
sec_log_buf before normal printk/setup_arch diagnostics are available.

Typical use:
  python3 scripts/twrp-entry-marker-test.py build --clean-source
  python3 scripts/twrp-entry-marker-test.py flash
  # Observe 60 s; if still stuck, enter TWRP once.
  python3 scripts/twrp-entry-marker-test.py collect
  python3 scripts/twrp-entry-marker-test.py restore
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PATCH = ROOT / "kernel/patches/record-arm64-entry-markers.patch"
SERIES = ROOT / "kernel/patches/series"
SNAPSHOT = ROOT / "artifacts/device-snapshot-sm-x710-20260918"
BUNDLE = ROOT / "artifacts/boot-bundle"
STATE_DIR = ROOT / "artifacts/entry-marker-test"
STATE_FILE = STATE_DIR / "active.json"
PARTITIONS = ("boot", "init_boot", "vendor_boot", "dtbo")
MARKERS = ("G9E1301", "G9E1302", "G9E1303", "G9E1304", "G9E1305")

PATTERNS = {
    "entry_01": re.compile(r"G9E1301"),
    "entry_02": re.compile(r"G9E1302"),
    "entry_03": re.compile(r"G9E1303"),
    "entry_04": re.compile(r"G9E1304"),
    "entry_05": re.compile(r"G9E1305"),
    "setup_after_fdt": re.compile(r"GTS9WIFI: setup_arch after_fdt"),
    "setup_after_memblock": re.compile(r"GTS9WIFI: setup_arch after_memblock"),
    "setup_after_paging": re.compile(r"GTS9WIFI: setup_arch after_paging"),
    "setup_after_unflatten": re.compile(r"GTS9WIFI: setup_arch after_unflatten"),
    "setup_after_bootmem": re.compile(r"GTS9WIFI: setup_arch after_bootmem"),
    "console_init": re.compile(r"GTS9WIFI: console_initcall reached"),
    "start_after_console": re.compile(r"GTS9WIFI: start_kernel after_console_init"),
    "mmu_state": re.compile(r"mmu_enabled_at_boot="),
    "start_before_rest": re.compile(r"GTS9WIFI: start_kernel before_rest_init"),
    "rest_enter": re.compile(r"GTS9WIFI: rest_init enter"),
    "rest_pid1": re.compile(r"GTS9WIFI: rest_init pid1_created"),
    "rest_kthreadd": re.compile(r"GTS9WIFI: rest_init kthreadd_created"),
    "rest_ready": re.compile(r"GTS9WIFI: rest_init kthreadd_ready"),
    "kernel_init_enter": re.compile(r"GTS9WIFI: kernel_init enter"),
    "kernel_init_ready": re.compile(r"GTS9WIFI: kernel_init kthreadd_ready"),
    "freeable_enter": re.compile(r"GTS9WIFI: kernel_init_freeable enter"),
    "pre_smp_before": re.compile(r"GTS9WIFI: kernel_init_freeable before_pre_smp_initcalls"),
    "pre_smp_after": re.compile(r"GTS9WIFI: kernel_init_freeable after_pre_smp_initcalls"),
    "smp_after": re.compile(r"GTS9WIFI: kernel_init_freeable after_smp_init"),
    "basic_before": re.compile(r"GTS9WIFI: kernel_init_freeable before_basic_setup"),
    "basic_after": re.compile(r"GTS9WIFI: kernel_init_freeable after_basic_setup"),
    "wait_initramfs_after": re.compile(r"GTS9WIFI: kernel_init_freeable after_wait_for_initramfs"),
    "console_rootfs_after": re.compile(r"GTS9WIFI: kernel_init_freeable after_console_on_rootfs"),
    "rdinit_access": re.compile(r"GTS9WIFI: kernel_init_freeable rdinit_access="),
    "freeable_done": re.compile(r"GTS9WIFI: kernel_init_freeable done"),
    "kernel_init_freeable_done": re.compile(r"GTS9WIFI: kernel_init kernel_init_freeable_done"),
    "rdinit_before_exec": re.compile(r"GTS9WIFI: kernel_init before_rdinit_exec"),
    "rdinit_exec_failed": re.compile(r"GTS9WIFI: kernel_init rdinit_exec_failed"),
    "initramfs_entered": re.compile(r"GTS9WIFI: initramfs init entered"),
    "initramfs_ready": re.compile(r"initramfs ready; USB NCM address"),
    "initcall_level": re.compile(r"GTS9WIFI: initcall level .* (?:begin|end)"),
    "initcall_debug": re.compile(r"(?:calling  .* @ |initcall .* returned )"),
    "linux": re.compile(r"Linux version .*gts9wifi-bringup"),
    "fatal_noc": re.compile(r"TZBSP_ERR_FATAL_NOC_ERROR"),
    "user_reset": re.compile(r"upload_cause = User press reset keys for 7 sec"),
    "bootmode_0": re.compile(r"\[ ABL \] BootMode = 0"),
    "requested_boot": re.compile(r"\[ ABL \] Requested Partition: boot"),
    "uefi_end": re.compile(r"UEFI End"),
}

STAGES = (
    ("initramfs_ready", "INITRAMFS_USB_READY"),
    ("initramfs_entered", "INITRAMFS_INIT_ENTERED"),
    ("rdinit_before_exec", "KERNEL_BEFORE_RDINIT_EXEC"),
    ("kernel_init_freeable_done", "KERNEL_INIT_FREEABLE_RETURNED"),
    ("freeable_done", "KERNEL_INIT_FREEABLE_DONE"),
    ("rdinit_access", "KERNEL_RDINIT_ACCESS_CHECKED"),
    ("console_rootfs_after", "KERNEL_CONSOLE_ON_ROOTFS_DONE"),
    ("wait_initramfs_after", "KERNEL_WAIT_FOR_INITRAMFS_DONE"),
    ("basic_after", "KERNEL_BASIC_SETUP_DONE"),
    ("basic_before", "KERNEL_BEFORE_BASIC_SETUP"),
    ("smp_after", "KERNEL_SMP_INIT_DONE"),
    ("pre_smp_after", "KERNEL_PRE_SMP_INITCALLS_DONE"),
    ("pre_smp_before", "KERNEL_BEFORE_PRE_SMP_INITCALLS"),
    ("freeable_enter", "KERNEL_INIT_FREEABLE_ENTER"),
    ("kernel_init_ready", "KERNEL_INIT_KTHREADD_READY"),
    ("kernel_init_enter", "KERNEL_INIT_ENTER"),
    ("rest_ready", "REST_INIT_KTHREADD_READY"),
    ("rest_kthreadd", "REST_INIT_KTHREADD_CREATED"),
    ("rest_pid1", "REST_INIT_PID1_CREATED"),
    ("rest_enter", "REST_INIT_ENTER"),
    ("start_before_rest", "START_KERNEL_BEFORE_REST_INIT"),
    ("start_after_console", "START_KERNEL_AFTER_CONSOLE_INIT"),
    ("console_init", "CONSOLE_INITCALL_REACHED"),
    ("setup_after_bootmem", "SETUP_ARCH_AFTER_BOOTMEM"),
    ("setup_after_unflatten", "SETUP_ARCH_AFTER_UNFLATTEN"),
    ("setup_after_paging", "SETUP_ARCH_AFTER_PAGING"),
    ("setup_after_memblock", "SETUP_ARCH_AFTER_MEMBLOCK"),
    ("setup_after_fdt", "SETUP_ARCH_AFTER_FDT"),
    ("entry_05", "HEAD_AFTER_CPU_SETUP"),
    ("entry_04", "HEAD_AFTER_INIT_KERNEL_EL"),
    ("entry_03", "HEAD_AFTER_IDMAP_CREATE"),
    ("entry_02", "HEAD_AFTER_PRESERVE_BOOT_ARGS"),
    ("entry_01", "HEAD_PRIMARY_ENTRY"),
)

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def run_id():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def load(path):
    return json.loads(Path(path).read_text())

def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def adb_default():
    if os.environ.get("ADB"):
        return Path(os.environ["ADB"])
    candidate = Path("/mnt/d/android/platform-tools/adb.exe")
    return candidate if candidate.exists() else Path("adb")

def patch_id():
    h = hashlib.sha256()
    base = ROOT / "kernel/patches"
    for name in SERIES.read_text().splitlines():
        name = name.strip()
        if not name or name.startswith("#"):
            continue
        h.update(name.encode())
        h.update((base / name).read_bytes())
    return h.hexdigest()

def verify_repo():
    if not PATCH.is_file():
        raise RuntimeError("entry-marker patch is missing")
    late_patch = ROOT / "kernel/patches/record-late-boot-checkpoints.patch"
    if not late_patch.is_file():
        raise RuntimeError("late-boot checkpoint patch is missing")
    series = SERIES.read_text().splitlines()
    for required in (PATCH.name, late_patch.name):
        if required not in series:
            raise RuntimeError(required + " is not enabled in series")
    text = PATCH.read_text()
    for marker in MARKERS:
        if marker not in text:
            raise RuntimeError("missing marker in patch: " + marker)
    late_text = late_patch.read_text()
    for marker in (
        "start_kernel after_console_init",
        "rest_init enter",
        "kernel_init_freeable enter",
        "kernel_init before_rdinit_exec",
    ):
        if marker not in late_text:
            raise RuntimeError("missing late-boot marker in patch: " + marker)
    config = (ROOT / "kernel/config/gts9wifi-bringup.config").read_text()
    if "CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG=y" not in config:
        raise RuntimeError("persistent sec-log config is required")

def clean_stale_source(enabled):
    src = ROOT / "work/kernel-src"
    out = ROOT / "work/kernel-build"
    if not src.exists():
        return
    marker = src / ".gts9-source"
    if not marker.is_file():
        if not enabled:
            raise RuntimeError(
                "work/kernel-src is an incomplete/unmarked generated tree; "
                "rerun build with --clean-source"
            )
        # build-kernel.sh creates exactly this directory before patching and
        # writes .gts9-source only after the entire patch series succeeds.
        # A failed git apply therefore legitimately leaves an unmarked tree.
        shutil.rmtree(src)
        if out.exists():
            shutil.rmtree(out)
        print("Removed incomplete generated kernel source/build trees")
        return
    pin = load(ROOT / "device/sources.json")["linux_commit"]
    expected = f"{pin} {patch_id()}"
    actual = marker.read_text().strip()
    if actual == expected:
        return
    if not enabled:
        raise RuntimeError(
            "kernel patch set changed; rerun build with --clean-source\n"
            f"have: {actual}\nneed: {expected}"
        )
    shutil.rmtree(src)
    if out.exists():
        shutil.rmtree(out)
    print("Removed stale generated kernel source/build trees")

def verify_bundle(path):
    manifest = load(path / "manifest.json")
    if manifest.get("model") != "SM-X710":
        raise RuntimeError("bundle is not SM-X710")
    for part in PARTITIONS:
        fn = part + ".img"
        actual = sha256(path / fn)
        expected = manifest["files"][fn]["sha256"]
        if actual != expected:
            raise RuntimeError(f"bundle hash mismatch: {fn}")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify-boot-bundle.py"), str(path)],
        cwd=ROOT, check=True,
    )
    return manifest

def snapshot_serial(snapshot):
    manifest = load(snapshot / "manifest.json")
    if manifest.get("model") != "SM-X710" or not manifest.get("serial"):
        raise RuntimeError("invalid SM-X710 snapshot")
    return manifest["serial"]

class ADB:
    def __init__(self, executable, serial):
        self.base = [str(executable), "-s", serial]

    def run(self, args, binary=False, check=True):
        p = subprocess.run(self.base + list(args), capture_output=True, timeout=180)
        if check and p.returncode:
            raise RuntimeError(
                p.stderr.decode(errors="replace") + p.stdout.decode(errors="replace")
            )
        if binary:
            return p.returncode, p.stdout, p.stderr
        return (
            p.returncode,
            p.stdout.decode(errors="replace"),
            p.stderr.decode(errors="replace"),
        )

    def shell(self, command, check=True):
        return self.run(["shell", command], check=check)[1].strip()

    def capture(self, remote, local):
        rc, out, err = self.run(["exec-out", "cat", remote], binary=True, check=False)
        if rc:
            Path(str(local) + ".error.txt").write_bytes(err + out)
            return False
        Path(local).write_bytes(out)
        return True

def require_twrp(adb):
    if not adb.shell("pidof recovery", check=False):
        raise RuntimeError("device is not in TWRP")
    if "uid=0(" not in adb.shell("id"):
        raise RuntimeError("TWRP root shell required")
    model = adb.shell("getprop ro.boot.em.model")
    if model != "SM-X710":
        raise RuntimeError("connected device is not SM-X710")

def twrp_test(adb, snapshot, bundle, report, action=None, reboot=False):
    cmd = [
        sys.executable, str(ROOT / "scripts/twrp-boot-test.py"),
        "--adb", str(adb),
        "--snapshot", str(snapshot),
        "--bundle", str(bundle),
        "--report", str(report),
    ]
    if action:
        cmd.append(action)
    if reboot:
        cmd.append("--reboot")
    subprocess.run(cmd, cwd=ROOT, check=True)

def active(required=True):
    if not STATE_FILE.is_file():
        if required:
            raise RuntimeError("no active entry-marker test")
        return None
    return load(STATE_FILE)

def run_dir(args):
    return args.run_dir.resolve() if args.run_dir else Path(active()["run_dir"])

def archive_bundle(source, destination):
    destination.mkdir(parents=True)
    for name in ("boot.img", "init_boot.img", "vendor_boot.img", "dtbo.img",
                 "manifest.json", "SHA256SUMS"):
        src = source / name
        if src.exists():
            shutil.copy2(src, destination / name)
    verify_bundle(destination)

def partition_hashes(adb):
    result = {}
    for part in PARTITIONS + ("vbmeta", "recovery"):
        dev = f"/dev/block/by-name/{part}"
        result[part] = {
            "size": int(adb.shell("blockdev --getsize64 " + shlex.quote(dev))),
            "sha256": adb.shell("sha256sum " + shlex.quote(dev)).split()[0],
        }
    return result

def matches(text):
    result = {key: [] for key in PATTERNS}
    for lineno, line in enumerate(text.splitlines(), 1):
        for key, pattern in PATTERNS.items():
            if pattern.search(line):
                result[key].append({"line": lineno, "text": line})
    return result

def deepest(m):
    for key, label in STAGES:
        if m[key]:
            return label
    if m["linux"]:
        return "MAINLINE_PRINTK_VISIBLE"
    if m["requested_boot"] and m["uefi_end"]:
        return "ABL_UEFI_END_NO_KERNEL_MARKER"
    if m["requested_boot"]:
        return "ABL_REQUESTED_BOOT"
    return "NO_NORMAL_BOOT_SIGNATURE"

def classify(m):
    result = deepest(m)
    if m["fatal_noc"]:
        result += "+FATAL_NOC"
    elif m["user_reset"]:
        result += "+USER_RESET"
    return result

def cmd_build(args):
    verify_repo()
    clean_stale_source(args.clean_source)
    subprocess.run(["make", "bundle"], cwd=ROOT, check=True)
    manifest = verify_bundle(args.bundle)
    info = {
        "built_utc": now(),
        "linux_commit": load(ROOT / "device/sources.json")["linux_commit"],
        "patch_id": patch_id(),
        "markers": MARKERS,
        "files": {
            p + ".img": manifest["files"][p + ".img"]["sha256"] for p in PARTITIONS
        },
    }
    save(STATE_DIR / "last-build.json", info)
    print("PASS: entry-marker bundle built and verified")
    for fn, digest in info["files"].items():
        print(digest, fn)

def cmd_flash(args):
    verify_repo()
    verify_bundle(args.bundle)
    old = active(False)
    if old and old.get("phase") not in ("restored", "finished") and not args.force_new_run:
        raise RuntimeError(
            "previous test is unfinished: " + old.get("run_dir", "unknown")
        )
    rd = (args.run_dir or ROOT / "artifacts/boot-tests" / ("entry-marker-" + run_id())).resolve()
    if rd.exists():
        raise RuntimeError("run directory already exists: " + str(rd))
    rd.mkdir(parents=True)
    tested = rd / "tested-bundle"
    archive_bundle(args.bundle, tested)
    state = {
        "created_utc": now(),
        "phase": "prepared",
        "run_dir": str(rd),
        "tested_bundle": str(tested),
        "snapshot": str(args.snapshot),
        "observation_seconds": args.observation_seconds,
    }
    save(STATE_FILE, state)
    save(rd / "run.json", state)
    twrp_test(args.adb, args.snapshot, tested, rd / "preflight")
    state["phase"] = "preflight_passed"
    save(STATE_FILE, state)
    save(rd / "run.json", state)
    try:
        twrp_test(args.adb, args.snapshot, tested, rd / "flash", "--flash", True)
        state["phase"] = "reboot_requested"
    finally:
        state["updated_utc"] = now()
        save(STATE_FILE, state)
        save(rd / "run.json", state)
    print("Run directory:", rd)
    print(f"Observe for {args.observation_seconds} seconds.")
    print("Then enter TWRP once if needed and run:")
    print("  python3 scripts/twrp-entry-marker-test.py collect")

def cmd_collect(args):
    rd = run_dir(args)
    out = rd / "recovery-after"
    out.mkdir(parents=True, exist_ok=True)
    adb = ADB(args.adb, snapshot_serial(args.snapshot))
    require_twrp(adb)
    save(out / "device.json", {
        "collected_utc": now(),
        "partition_hashes": partition_hashes(adb),
    })
    adb.capture("/proc/last_kmsg", out / "last_kmsg.txt")
    rc, data, err = adb.run(["shell", "dmesg"], binary=True, check=False)
    (out / "twrp-dmesg.txt").write_bytes(data)
    if rc:
        (out / "twrp-dmesg.error.txt").write_bytes(err)
    adb.capture("/tmp/recovery.log", out / "recovery.log")

    listing = adb.shell("ls -1 /sys/fs/pstore 2>/dev/null", check=False)
    pstore = [x.strip() for x in listing.splitlines() if x.strip()]
    (out / "pstore-list.txt").write_text("\n".join(pstore) + ("\n" if pstore else ""))
    (out / "pstore").mkdir(exist_ok=True)
    for name in pstore:
        if "/" not in name and name not in (".", ".."):
            adb.capture("/sys/fs/pstore/" + name, out / "pstore" / name)

    text = (out / "last_kmsg.txt").read_text(errors="replace")
    m = matches(text)
    summary = {
        "collected_utc": now(),
        "deepest_stage": deepest(m),
        "classification": classify(m),
        "pstore_files": pstore,
        "matches": m,
        "note": "G9E13 markers are emitted only on the expected MMU-off ABL path.",
    }
    save(out / "summary.json", summary)
    lines = [
        "deepest_stage: " + summary["deepest_stage"],
        "classification: " + summary["classification"],
        "pstore files: " + str(len(pstore)),
        "",
    ]
    for key in PATTERNS:
        found = m[key]
        lines.append(f"[{key}] count={len(found)}")
        for item in found[-5:]:
            lines.append(f"  L{item['line']}: {item['text']}")
    (out / "summary.txt").write_text("\n".join(lines) + "\n")

    state = active(False) or {}
    state.update({
        "phase": "logs_collected",
        "run_dir": str(rd),
        "updated_utc": now(),
        "classification": summary["classification"],
    })
    save(STATE_FILE, state)
    save(rd / "run.json", state)
    print((out / "summary.txt").read_text(), end="")
    print("Logs:", out)
    print("Now restore with:")
    print("  python3 scripts/twrp-entry-marker-test.py restore")

def cmd_restore(args):
    rd = run_dir(args)
    state = active()
    tested = Path(state["tested_bundle"])
    verify_bundle(tested)
    twrp_test(args.adb, args.snapshot, tested, rd / "restore", "--restore")
    state["phase"] = "restored"
    state["updated_utc"] = now()
    save(STATE_FILE, state)
    save(rd / "run.json", state)
    print("PASS: original four boot partitions restored; device left in TWRP")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("build", "flash", "collect", "restore"))
    p.add_argument("--adb", type=Path, default=adb_default())
    p.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    p.add_argument("--bundle", type=Path, default=BUNDLE)
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--clean-source", action="store_true")
    p.add_argument("--force-new-run", action="store_true")
    p.add_argument("--observation-seconds", type=int, default=60)
    args = p.parse_args()
    if args.observation_seconds < 10:
        p.error("--observation-seconds must be >= 10")
    args.snapshot = args.snapshot.resolve()
    args.bundle = args.bundle.resolve()
    if args.run_dir:
        args.run_dir = args.run_dir.resolve()
    {
        "build": cmd_build,
        "flash": cmd_flash,
        "collect": cmd_collect,
        "restore": cmd_restore,
    }[args.command](args)

if __name__ == "__main__":
    main()
