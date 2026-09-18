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
USB_DIAG_RE = re.compile(
    r"(?:dwc3|\budc\b|gadget|usb0|\bncm\b|eusb|ptn3222|type-?c|configfs|"
    r"GTS9WIFI: mount |GTS9WIFI: filesystem |GTS9WIFI: initramfs pseudo|"
    r"GTS9WIFI: mount table)",
    re.IGNORECASE,
)

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
    "rdinit_after_exec": re.compile(r"GTS9WIFI: kernel_init after_rdinit_exec ret="),
    "rdinit_exec_success": re.compile(r"GTS9WIFI: kernel_init rdinit_exec_success"),
    "rdinit_exec_failed": re.compile(r"GTS9WIFI: kernel_init rdinit_exec_failed"),
    "initramfs_entered": re.compile(r"GTS9WIFI: initramfs init entered"),
    "initramfs_busybox": re.compile(r"GTS9WIFI: initramfs busybox links ready"),
    "initramfs_devtmpfs": re.compile(r"GTS9WIFI: (?:initramfs devtmpfs mounted|mount devtmpfs success)"),
    "mount_devtmpfs_failed": re.compile(r"GTS9WIFI: mount devtmpfs failed"),
    "mount_proc_success": re.compile(r"GTS9WIFI: mount proc success"),
    "mount_proc_failed": re.compile(r"GTS9WIFI: mount proc failed"),
    "mount_sysfs_success": re.compile(r"GTS9WIFI: mount sysfs success"),
    "mount_sysfs_failed": re.compile(r"GTS9WIFI: mount sysfs failed"),
    "mount_devpts_success": re.compile(r"GTS9WIFI: mount devpts success"),
    "mount_devpts_failed": re.compile(r"GTS9WIFI: mount devpts failed"),
    "mount_run_failed": re.compile(r"GTS9WIFI: mount run_tmpfs failed"),
    "mount_tmp_failed": re.compile(r"GTS9WIFI: mount tmp_tmpfs failed"),
    "initramfs_pseudo": re.compile(r"GTS9WIFI: initramfs pseudo filesystems ready"),
    "initramfs_pseudo_incomplete": re.compile(r"GTS9WIFI: initramfs pseudo filesystems incomplete"),
    "filesystem_configfs": re.compile(r"GTS9WIFI: filesystem (?:available|missing) name=configfs"),
    "configfs_mountpoint": re.compile(r"GTS9WIFI: configfs mountpoint "),
    "configfs_primary_failed": re.compile(r"GTS9WIFI: configfs primary mount failed"),
    "configfs_mounted": re.compile(r"GTS9WIFI: configfs (?:already mounted|mounted|fallback mounted)"),
    "configfs_failed": re.compile(r"GTS9WIFI: configfs (?:mount failed|fallback mount failed)"),
    "gadget_configured": re.compile(r"GTS9WIFI: USB gadget configured"),
    "gadget_setup_failed": re.compile(r"GTS9WIFI: USB gadget setup failed"),
    "gadget_skipped": re.compile(r"GTS9WIFI: USB gadget skipped because configfs unavailable"),
    "udc_test_skipped": re.compile(r"GTS9WIFI: USB UDC test skipped because gadget setup failed"),
    "udc_no_controller": re.compile(r"GTS9WIFI: UDC no controller yet"),
    "udc_candidate": re.compile(r"GTS9WIFI: UDC candidate controller="),
    "udc_bind_success": re.compile(r"GTS9WIFI: UDC bind success controller="),
    "udc_bind_failed": re.compile(r"GTS9WIFI: UDC bind (?:failed|verification failed)"),
    "udc_bind_timeout": re.compile(r"GTS9WIFI: UDC bind timeout"),
    "udc_class": re.compile(r"GTS9WIFI: UDC class (?:entries=|missing)"),
    "deferred_probe": re.compile(r"GTS9WIFI: deferred_probe "),
    "platform_driver": re.compile(r"GTS9WIFI: platform_driver "),
    "platform_device": re.compile(r"GTS9WIFI: platform_device "),
    "platform_waiting_supplier": re.compile(r"GTS9WIFI: platform_device .*waiting_for_supplier=1"),
    "platform_supplier": re.compile(r"GTS9WIFI: platform_supplier "),
    "manual_dwc3_bind": re.compile(r"GTS9WIFI: manual_dwc3_bind "),
    "manual_dwc3_defer": re.compile(r"GTS9WIFI: manual_dwc3_bind .*Resource temporarily unavailable"),
    "usb0_present": re.compile(r"GTS9WIFI: usb0 present"),
    "usb0_missing": re.compile(r"GTS9WIFI: usb0 missing after UDC bind"),
    "usb0_configured": re.compile(r"GTS9WIFI: usb0 configured address="),
    "usb0_config_failed": re.compile(r"GTS9WIFI: usb0 configuration failed"),
    "telnet_started": re.compile(r"GTS9WIFI: telnetd started port="),
    "telnet_failed": re.compile(r"GTS9WIFI: telnetd start failed"),
    "usb_local_ready": re.compile(r"GTS9WIFI: USB NCM local ready controller="),
    "udc_state": re.compile(r"GTS9WIFI: UDC state controller=.* state="),
    "usb_host_configured": re.compile(r"GTS9WIFI: USB host configured controller="),
    "usb_host_timeout": re.compile(r"GTS9WIFI: USB host configuration timeout"),
    "initramfs_ready": re.compile(r"initramfs ready; USB NCM host configured;"),
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
    ("usb_host_configured", "USB_HOST_CONFIGURED"),
    ("initramfs_ready", "INITRAMFS_USB_HOST_READY"),
    ("usb_local_ready", "USB_NCM_LOCAL_READY"),
    ("usb0_configured", "USB0_CONFIGURED"),
    ("udc_bind_success", "UDC_BOUND"),
    ("gadget_configured", "USB_GADGET_CONFIGURED"),
    ("configfs_mounted", "CONFIGFS_MOUNTED"),
    ("initramfs_pseudo", "INITRAMFS_PSEUDO_FS_READY"),
    ("initramfs_devtmpfs", "INITRAMFS_DEVTMPFS_MOUNTED"),
    ("initramfs_busybox", "INITRAMFS_BUSYBOX_LINKS_READY"),
    ("initramfs_entered", "INITRAMFS_INIT_ENTERED"),
    ("rdinit_exec_success", "KERNEL_RDINIT_EXEC_SUCCESS"),
    ("rdinit_after_exec", "KERNEL_RDINIT_EXEC_RETURNED"),
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
    exec_patch = ROOT / "kernel/patches/record-rdinit-exec-result.patch"
    if not late_patch.is_file():
        raise RuntimeError("late-boot checkpoint patch is missing")
    if not exec_patch.is_file():
        raise RuntimeError("rdinit exec-result patch is missing")
    series = SERIES.read_text().splitlines()
    for required in (PATCH.name, late_patch.name, exec_patch.name):
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
    exec_text = exec_patch.read_text()
    if "kernel_init after_rdinit_exec ret=" not in exec_text:
        raise RuntimeError("missing rdinit exec-result marker")
    init_text = (ROOT / "initramfs/init").read_text()
    if "GTS9WIFI: initramfs init entered" not in init_text:
        raise RuntimeError("missing earliest initramfs userspace marker")
    for marker in (
        "GTS9WIFI: UDC bind success",
        "GTS9WIFI: USB NCM local ready",
        "GTS9WIFI: USB host configured",
        "GTS9WIFI: USB host configuration timeout",
    ):
        if marker not in init_text:
            raise RuntimeError("missing USB diagnostic marker: " + marker)
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
    if m.get("platform_waiting_supplier"):
        result += "+WAITING_FOR_SUPPLIER"
    elif m.get("manual_dwc3_defer"):
        result += "+DWC3_BIND_DEFERRED"
    if m.get("mount_sysfs_failed"):
        result += "+SYSFS_MOUNT_FAILED"
    elif m.get("mount_proc_failed"):
        result += "+PROC_MOUNT_FAILED"
    elif m.get("mount_devtmpfs_failed"):
        result += "+DEVTMPFS_MOUNT_FAILED"
    elif m.get("initramfs_pseudo_incomplete"):
        result += "+PSEUDO_FS_INCOMPLETE"
    elif m.get("configfs_failed"):
        result += "+CONFIGFS_MOUNT_FAILED"
    elif m.get("gadget_setup_failed"):
        result += "+GADGET_SETUP_FAILED"
    elif m.get("udc_bind_timeout"):
        result += "+UDC_BIND_TIMEOUT"
    elif m.get("usb_host_timeout"):
        result += "+USB_HOST_ENUM_TIMEOUT"
    elif m.get("usb0_config_failed"):
        result += "+USB0_CONFIG_FAILED"
    if m["fatal_noc"]:
        result += "+FATAL_NOC"
    elif m["user_reset"]:
        result += "+USER_RESET"
    return result

def relative_path(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)

def last_match(summary, key):
    found = summary.get("matches", {}).get(key, [])
    return found[-1]["text"] if found else None

def record_interpretation(summary):
    m = summary.get("matches", {})
    if m.get("mount_sysfs_failed"):
        return "initramfs 用户态已进入，但 sysfs 挂载失败；configfs 与 UDC 结果在该前提下不具备诊断意义，应先定位 sysfs mount 失败的返回码与错误信息。"
    if m.get("mount_proc_failed"):
        return "initramfs 用户态已进入，但 procfs 挂载失败；应先修复基础伪文件系统挂载，再继续 USB/configfs 诊断。"
    if m.get("configfs_failed"):
        return "基础挂载已进入 configfs 阶段，但 configfs 在主路径和 fallback 路径上均未成功挂载；应结合 mount rc、stderr 与 /proc/filesystems 判断失败原因。"
    if m.get("gadget_setup_failed"):
        return "configfs 已可用，但 USB gadget configfs 配置步骤失败；应根据 gadget setup error 继续定位。"
    if m.get("usb_host_configured"):
        return "USB gadget 已绑定 UDC，usb0 已在设备端配置，并且 UDC state 达到 configured；主机已经完成 USB 枚举。"
    if m.get("usb_host_timeout"):
        return "USB gadget 已进入设备端本地就绪阶段，但主机在观察窗口内没有把 UDC state 推进到 configured；应继续分析主机枚举或物理 USB 链路。"
    if m.get("udc_bind_timeout"):
        if m.get("platform_waiting_supplier"):
            return "configfs 与 USB gadget 已正常建立，但 a600000.usb 明确处于 waiting_for_supplier=1；dwc3-qcom deferred probe 发生在 supplier 依赖未就绪阶段，应依据 platform_supplier 记录定位未绑定 supplier。"
        if m.get("manual_dwc3_defer"):
            return "configfs 与 USB gadget 已正常建立，a600000.usb 手动绑定 dwc3-qcom 返回 EAGAIN/EPROBE_DEFER；应结合 waiting_for_supplier 与 platform_supplier 的实际 driver 状态，区分 driver-core supplier gating 和 dwc3_qcom_probe/DWC3 core 内部 defer。"
        if m.get("manual_dwc3_bind"):
            return "configfs 与 USB gadget 已正常建立，但等待窗口内没有 UDC；已记录 a600000 platform device、dwc3-qcom 手动 bind 结果和实际 driver binding，应依据这些结果定位 DWC3 probe。"
        return "initramfs 已运行到 USB gadget 配置，但没有在等待窗口内成功绑定任何 UDC；应检查 DWC3/UDC 驱动 probe 与设备树。"
    if m.get("usb_local_ready"):
        return "USB gadget 已成功绑定 UDC，且设备端 usb0/NCM 本地栈已配置；仍需结合 UDC state 判断主机枚举是否完成。"
    if m.get("udc_bind_success"):
        return "USB gadget 已成功绑定 UDC；后续应检查 usb0 配置与主机枚举状态。"
    if m.get("initramfs_ready"):
        return "已进入 initramfs 用户态并完成 USB NCM 主机枚举。"
    if m.get("initramfs_pseudo"):
        return "已进入 initramfs 用户态并完成基础伪文件系统挂载，后续应继续定位 USB gadget/UDC 初始化。"
    if m.get("initramfs_devtmpfs"):
        return "已进入 initramfs 用户态并完成 devtmpfs 挂载，后续卡点位于更晚的 initramfs 初始化。"
    if m.get("initramfs_busybox"):
        return "已进入 initramfs 用户态且 BusyBox 链接建立完成，后续卡点在 devtmpfs 或更晚阶段。"
    if m.get("initramfs_entered"):
        return "已成功进入 /init 用户态脚本；后续应继续按 initramfs 阶段 marker 定位。"
    if m.get("rdinit_exec_success"):
        return "kernel_execve(/init) 已返回成功，但尚未观察到 initramfs 第一条用户态 marker。"
    if m.get("rdinit_after_exec"):
        return "kernel_execve(/init) 已返回；应结合返回值判断 exec 成功或失败。"
    if m.get("rdinit_before_exec"):
        return "内核已完成全部 initcall，确认 /init 可访问，并到达 kernel_execve(/init) 调用前。"
    if m.get("basic_after"):
        return "所有普通 initcall 已完成；问题位于后续 initramfs/用户态交接路径。"
    if m.get("console_init"):
        return "Linux 已进入 start_kernel 并建立 persistent console。"
    if m.get("linux"):
        return "已观察到主线 Linux printk，但更晚阶段尚未确认。"
    return "当前日志不足以确认更深执行阶段。"

def write_test_record(rd, state, summary):
    rd = Path(rd).resolve()
    tested = Path(state["tested_bundle"]).resolve()
    manifest = load(tested / "manifest.json")
    hashes = {
        part: manifest["files"][part + ".img"]["sha256"]
        for part in PARTITIONS
    }
    matches_map = summary.get("matches", {})
    initcall_tail = [
        item["text"] for item in matches_map.get("initcall_debug", [])[-10:]
    ]
    key_names = (
        "linux", "mmu_state", "setup_after_bootmem", "start_after_console",
        "start_before_rest", "rest_enter", "kernel_init_enter",
        "basic_after", "rdinit_access", "rdinit_before_exec",
        "rdinit_after_exec", "rdinit_exec_success", "rdinit_exec_failed",
        "initramfs_entered", "initramfs_busybox", "initramfs_devtmpfs",
        "mount_devtmpfs_failed", "mount_proc_success", "mount_proc_failed",
        "mount_sysfs_success", "mount_sysfs_failed",
        "mount_devpts_success", "mount_devpts_failed",
        "mount_run_failed", "mount_tmp_failed", "initramfs_pseudo",
        "initramfs_pseudo_incomplete", "filesystem_configfs",
        "configfs_mountpoint", "configfs_primary_failed",
        "configfs_mounted", "configfs_failed",
        "gadget_configured", "gadget_setup_failed", "gadget_skipped",
        "udc_test_skipped", "udc_no_controller", "udc_candidate",
        "udc_bind_success", "udc_bind_failed", "udc_bind_timeout",
        "udc_class", "deferred_probe", "platform_driver",
        "platform_device", "platform_waiting_supplier", "platform_supplier",
        "manual_dwc3_bind", "manual_dwc3_defer",
        "usb0_present", "usb0_missing", "usb0_configured",
        "usb0_config_failed", "telnet_started", "telnet_failed",
        "usb_local_ready", "udc_state", "usb_host_configured",
        "usb_host_timeout", "initramfs_ready", "fatal_noc", "user_reset",
        "uefi_end",
    )
    record = {
        "schema": 1,
        "run_id": rd.name,
        "generated_utc": now(),
        "phase": state.get("phase"),
        "created_utc": state.get("created_utc"),
        "collected_utc": summary.get("collected_utc"),
        "restored_utc": state.get("restored_utc"),
        "observation_seconds": state.get("observation_seconds"),
        "deepest_stage": summary.get("deepest_stage"),
        "classification": summary.get("classification"),
        "interpretation": record_interpretation(summary),
        "pstore_files": summary.get("pstore_files", []),
        "tested_bundle": relative_path(tested),
        "snapshot": relative_path(Path(state["snapshot"])),
        "image_sha256": hashes,
        "key_markers": {
            key: last_match(summary, key)
            for key in key_names
            if matches_map.get(key)
        },
        "last_initcall_activity": initcall_tail,
        "artifacts": {
            "last_kmsg": relative_path(rd / "recovery-after/last_kmsg.txt"),
            "summary_json": relative_path(rd / "recovery-after/summary.json"),
            "summary_txt": relative_path(rd / "recovery-after/summary.txt"),
            "usb_diagnostics": relative_path(rd / "recovery-after/usb-diagnostics.txt"),
            "pstore": relative_path(rd / "recovery-after/pstore"),
            "device": relative_path(rd / "recovery-after/device.json"),
        },
    }
    save(rd / "test-record.json", record)

    md = [
        "# SM-X710 Boot Test - " + rd.name,
        "",
        "## 基本信息",
        "",
        "- 创建时间（UTC）：" + str(record["created_utc"] or "-"),
        "- 日志采集时间（UTC）：" + str(record["collected_utc"] or "-"),
        "- 恢复时间（UTC）：" + str(record["restored_utc"] or "-"),
        "- 当前状态：" + str(record["phase"] or "-"),
        "- 观察窗口：" + str(record["observation_seconds"] or "-") + " 秒",
        "- 最深阶段：" + str(record["deepest_stage"] or "-"),
        "- 分类：" + str(record["classification"] or "-"),
        "- pstore 文件数：" + str(len(record["pstore_files"])),
        "",
        "## 实际刷入镜像",
        "",
        "| 分区 | SHA256 |",
        "| --- | --- |",
    ]
    for name in PARTITIONS:
        md.append("| " + name + " | " + hashes[name] + " |")
    md.extend([
        "",
        "- Tested bundle：" + record["tested_bundle"],
        "- 原始快照：" + record["snapshot"],
        "",
        "## 关键执行证据",
        "",
    ])
    if record["key_markers"]:
        for key, value in record["key_markers"].items():
            md.append("- " + key + "：" + value)
    else:
        md.append("- 未提取到关键 marker。")

    md.extend(["", "## 最后 initcall 活动", ""])
    if initcall_tail:
        for line in initcall_tail:
            md.append("    " + line)
    else:
        md.append("未记录 initcall_debug 输出。")

    md.extend([
        "",
        "## 结论",
        "",
        record["interpretation"],
        "",
        "## 日志位置",
        "",
    ])
    for key, value in record["artifacts"].items():
        md.append("- " + key + "：" + value)
    md.append("")

    markdown = "\n".join(md)
    local_path = rd / "TEST-RECORD.md"
    local_path.write_text(markdown)
    return local_path

def cmd_build(args):
    verify_repo()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-bringup.py")],
        cwd=ROOT, check=True,
    )
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

    usb_diag = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if USB_DIAG_RE.search(line):
            usb_diag.append({"line": lineno, "text": line})
    usb_diag_lines = [
        f"L{item['line']}: {item['text']}" for item in usb_diag
    ]
    (out / "usb-diagnostics.txt").write_text(
        "\n".join(usb_diag_lines) + ("\n" if usb_diag_lines else "")
    )

    summary = {
        "collected_utc": now(),
        "deepest_stage": deepest(m),
        "classification": classify(m),
        "pstore_files": pstore,
        "matches": m,
        "usb_diagnostics_count": len(usb_diag),
        "usb_diagnostics_tail": usb_diag[-50:],
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
    lines.append(f"[usb_diagnostics] count={len(usb_diag)}")
    for item in usb_diag[-20:]:
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
    local_record = write_test_record(rd, state, summary)
    print((out / "summary.txt").read_text(), end="")
    print("Logs:", out)
    print("Test record:", local_record)
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
    state["restored_utc"] = state["updated_utc"]
    save(STATE_FILE, state)
    save(rd / "run.json", state)
    summary_path = rd / "recovery-after/summary.json"
    if summary_path.is_file():
        local_record = write_test_record(rd, state, load(summary_path))
        print("Updated test record:", local_record)
    print("PASS: original four boot partitions restored; device left in TWRP")

def cmd_record(args):
    rd = run_dir(args)
    run_state = load(rd / "run.json") if (rd / "run.json").is_file() else active()
    summary_path = rd / "recovery-after/summary.json"
    if not summary_path.is_file():
        raise RuntimeError("no collected summary for run: " + str(rd))
    local_record = write_test_record(rd, run_state, load(summary_path))
    print("Test record:", local_record)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("build", "flash", "collect", "restore", "record"))
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
        "record": cmd_record,
    }[args.command](args)

if __name__ == "__main__":
    main()
