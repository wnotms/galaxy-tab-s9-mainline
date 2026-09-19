#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fast local preflight for SM-X710 bring-up scripts and patch files."""

from __future__ import annotations

from pathlib import Path
import hashlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

PYTHON_FILES = (
    "scripts/check-bringup.py",
    "scripts/twrp-entry-marker-test.py",
    "scripts/check-patch-series.py",
    "scripts/compare-boot-bundles.py",
    "scripts/build-initramfs.py",
    "scripts/build-boot-bundle.py",
    "scripts/verify-boot-bundle.py",
)

SHELL_FILES = (
    ("sh", "initramfs/init"),
    ("bash", "scripts/build-kernel.sh"),
    ("bash", "scripts/twrp-restore-original.sh"),
)

REQUIRED_INIT_MARKERS = (
    "GTS9WIFI: initramfs init entered",
    "configfs mountpoint present",
    "configfs primary mount failed",
    "configfs fallback mount failed",
    "GTS9WIFI: USB gadget setup failed",
    "GTS9WIFI: USB gadget skipped because configfs unavailable",
    "GTS9WIFI: UDC bind success",
    "GTS9WIFI: UDC bind timeout",
    "GTS9WIFI: USB NCM local ready",
    "GTS9WIFI: USB host configured",
    "GTS9WIFI: USB host configuration timeout",
    "platform_driver ",
    "platform_device name=",
    "waiting_for_supplier=",
    "platform_supplier consumer=",
    "device_link depth=",
    "link_status=",
    "manual_dwc3_bind",
)


def check_python(path: Path) -> None:
    source = path.read_text()
    compile(source, str(path), "exec")


def check_shell(shell: str, path: Path) -> None:
    subprocess.run(
        [shell, "-n", str(path)],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-patch-series.py"), "--quiet"],
        cwd=ROOT,
        check=True,
    )

    for rel in PYTHON_FILES:
        path = ROOT / rel
        check_python(path)
        print("PASS: Python syntax:", rel)

    for shell, rel in SHELL_FILES:
        path = ROOT / rel
        check_shell(shell, path)
        print(f"PASS: {shell} syntax: {rel}")

    config_text = (ROOT / "kernel/config/gts9wifi-bringup.config").read_text()
    for required_config in (
        "CONFIG_ARM_PSCI_CPUIDLE=y",
        "CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y",
        "CONFIG_PM_GENERIC_DOMAINS=y",
        "CONFIG_PM_GENERIC_DOMAINS_OF=y",
        "CONFIG_QCOM_RPMH=y",
        "CONFIG_QCOM_CLK_RPMH=y",
        "CONFIG_SM_TCSRCC_8550=y",
        "CONFIG_PHY_SNPS_EUSB2=y",
        "CONFIG_USB_DWC3_QCOM=y",
    ):
        if required_config not in config_text:
            raise RuntimeError(
                "missing required bring-up config fragment entry: " + required_config
            )
    print("PASS: PSCI/RPMh/TCSR/eUSB2/DWC3 config chain")

    reference = ROOT / "kernel/config/s9u-mainline-aarch64.reference.config"
    reference_sha = hashlib.sha256(reference.read_bytes()).hexdigest()
    expected_reference_sha = "754de673160f57c867ee8107ad2987db6bba09942b8df6aca4b6be85d22c4658"
    if reference_sha != expected_reference_sha:
        raise RuntimeError(
            "S9 Ultra reference config hash mismatch: "
            + reference_sha + " != " + expected_reference_sha
        )
    reference_text = reference.read_text()
    for required_reference in (
        "CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y",
        "CONFIG_DT_IDLE_GENPD=y",
        "CONFIG_SUSPEND=y",
        "CONFIG_PM_SLEEP=y",
        "CONFIG_PM_GENERIC_DOMAINS_SLEEP=y",
        "CONFIG_INTERCONNECT_QCOM_SM8550=y",
        "CONFIG_SM_TCSRCC_8550=y",
    ):
        if required_reference not in reference_text:
            raise RuntimeError(
                "S9 Ultra reference config missing: " + required_reference
            )

    build_kernel_text = (ROOT / "scripts/build-kernel.sh").read_text()
    for token in (
        'GTS9_CONFIG_PROFILE',
        's9u-control',
        's9u-nobti',
        's9u-va48',
        's9u-va48-norelr',
        'merge_config.sh',
        's9u-mainline-aarch64.reference.config',
        'GTS9_CCACHE',
        'CCACHE_DIR',
        'CCACHE_MAXSIZE',
        'CCACHE_COMPILERCHECK',
        'MAKE_TOOLCHAIN',
        'CC="ccache clang"',
        'HOSTCC="ccache clang"',
        'ccache --show-stats',
    ):
        if token not in build_kernel_text:
            raise RuntimeError("missing S9U control build support: " + token)

    check_config_text = (ROOT / "scripts/check-config.py").read_text()
    for token in (
        'CONFIG_ARM64_VA_BITS=48',
        'CONFIG_ARM64_PA_BITS=48',
        'for name in ("ARM64_VA_BITS_52", "ARM64_PA_BITS_52", "ARM64_LPA2")',
        'if enabled(name)',
    ):
        if token not in check_config_text:
            raise RuntimeError("missing robust s9u-va48 config validation: " + token)
    print("PASS: optional ccache kernel build support")
    print("PASS: s9u-va48 positive/forbidden config validation")

    entry_test_text = (ROOT / "scripts/twrp-entry-marker-test.py").read_text()
    if (
        "--config-profile" not in entry_test_text
        or "s9u-control" not in entry_test_text
        or "s9u-nobti" not in entry_test_text
        or "s9u-va48" not in entry_test_text
        or "s9u-va48-norelr" not in entry_test_text
        or "s9u-va48-norelr" not in entry_test_text
    ):
        raise RuntimeError("entry-marker harness lacks s9u-control profile support")
    nobti = (ROOT / "kernel/config/s9u-nobti.fragment").read_text()
    if "# CONFIG_ARM64_BTI_KERNEL is not set" not in nobti:
        raise RuntimeError("S9U no-BTI override is missing ARM64_BTI_KERNEL=n")
    va48 = (ROOT / "kernel/config/s9u-va48.fragment").read_text()
    for token in (
        "CONFIG_ARM64_VA_BITS_48=y",
        "# CONFIG_ARM64_VA_BITS_52 is not set",
        "CONFIG_ARM64_PA_BITS_48=y",
        "# CONFIG_ARM64_PA_BITS_52 is not set",
    ):
        if token not in va48:
            raise RuntimeError("S9U VA48 override is missing: " + token)
    norelr = (ROOT / "kernel/config/s9u-va48-norelr.fragment").read_text()
    if "# CONFIG_RELR is not set" not in norelr:
        raise RuntimeError("S9U VA48 no-RELR override is missing CONFIG_RELR=n")
    if "s9u-va48 control must keep CONFIG_RELR enabled" not in check_config_text:
        raise RuntimeError("check-config lacks RELR-on control validation")
    if "s9u-va48-norelr must keep CONFIG_RELR disabled" not in check_config_text:
        raise RuntimeError("check-config lacks no-RELR control validation")
    norelr = (ROOT / "kernel/config/s9u-norelr.fragment").read_text()
    if "# CONFIG_RELR is not set" not in norelr:
        raise RuntimeError("S9U no-RELR override is missing CONFIG_RELR=n")
    if "s9u-va48-norelr" not in check_config_text:
        raise RuntimeError("check-config lacks s9u-va48-norelr validation")
    print("PASS: pinned S9 Ultra config control profiles")
    print("PASS: s9u-va48 RELR/no-RELR A/B control")

    bundle_builder_text = (ROOT / "scripts/build-boot-bundle.py").read_text()
    for token in (
        "--kernel-gzip-target-size",
        "FEXTRA",
        "kernel_gzip_target_size",
    ):
        if token not in bundle_builder_text:
            raise RuntimeError("missing fixed-geometry gzip control support: " + token)
    print("PASS: fixed-geometry gzip control support")

    boot_marker_patch = ROOT / "kernel/patches/record-arm64-boot-markers.patch"
    boot_marker_text = boot_marker_patch.read_text()
    for token in (
        "G9E1301",
        "G9E1306",
        "G9E1317",
        "G9V0001",
        "G9V0002",
        "G9V0003",
        "gts9wifi_map_sec_log",
        "gts9wifi_entry_marker_append_mmu_on",
        "gts9wifi_entry_marker_append_kernel_va",
        "ldr\tw9, [x8]",
    ):
        if token not in boot_marker_text:
            raise RuntimeError("missing consolidated ARM64 boot-marker support: " + token)
    active_series = (
        ROOT / "kernel/patches/series"
    ).read_text().splitlines()
    if "record-arm64-boot-markers.patch" not in active_series:
        raise RuntimeError("consolidated ARM64 boot-marker patch is not enabled")
    for obsolete in (
        "record-arm64-entry-markers.patch",
        "record-arm64-mmu-on-markers.patch",
        "record-arm64-virtual-switch-probe.patch",
    ):
        if obsolete in active_series:
            raise RuntimeError("obsolete overlapping ARM64 marker patch still enabled: " + obsolete)
    if boot_marker_text.count("bl\tgts9wifi_entry_marker_append_kernel_va") != 4:
        raise RuntimeError("post-switch G9E1314..G9E1317 must all use the kernel-VA helper")
    print("PASS: consolidated ARM64 early/MMU/virtual-switch markers")
    print("PASS: post-switch marker helper stays in kernel mapping")

    dyndbg_patch = ROOT / "kernel/patches/record-dynamic-debug-init-checkpoints.patch"
    dyndbg_text = dyndbg_patch.read_text()
    for token in (
        "dynamic_debug_init enter",
        "dynamic_debug_init walk_begin",
        "dynamic_debug_init walk_done",
        "dynamic_debug_init cmp_before",
        "dynamic_debug_init cmp_after",
        "dynamic_debug_init add_begin i=",
        "dynamic_debug_init add_done i=",
        "dynamic_debug_init final_add_done",
        "dynamic_debug_init before_parse_args",
        "dynamic_debug_init after_parse_args",
    ):
        if token not in dyndbg_text:
            raise RuntimeError("missing dynamic-debug init checkpoint: " + token)
    if dyndbg_patch.name not in active_series:
        raise RuntimeError("dynamic-debug init checkpoint patch is not enabled")
    print("PASS: dynamic-debug early-initcall checkpoints")

    init_text = (ROOT / "initramfs/init").read_text()
    for marker in REQUIRED_INIT_MARKERS:
        if marker not in init_text:
            raise RuntimeError("missing required initramfs diagnostic marker: " + marker)

    sysfs_mount = init_text.find("mount_checked sysfs sysfs sysfs /sys")
    configfs_probe = init_text.find("configfs mountpoint present")
    configfs_primary = init_text.find(
        "/bin/busybox mount -t configfs none /sys/kernel/config"
    )
    configfs_fallback = init_text.find(
        "/bin/busybox mount -t configfs none /config"
    )
    if min(sysfs_mount, configfs_probe, configfs_primary, configfs_fallback) < 0:
        raise RuntimeError("missing sysfs/configfs diagnostic sequence")
    if not (sysfs_mount < configfs_probe < configfs_primary < configfs_fallback):
        raise RuntimeError(
            "configfs diagnostics must follow sysfs and primary mount must precede fallback"
        )

    for required in (
        "mount_checked devtmpfs devtmpfs devtmpfs /dev",
        "mkdir -p /dev/pts",
        "mount_checked proc proc proc /proc",
        "mount_checked sysfs sysfs sysfs /sys",
        "filesystem available name=",
        "mount table target=",
        "CONFIGFS_ROOT='/config'",
    ):
        if required not in init_text:
            raise RuntimeError("missing pseudo-filesystem diagnostic: " + required)

    if "rc=$?" not in init_text or "/bin/busybox mount -t" not in init_text:
        raise RuntimeError("mount_checked must preserve the real mount return code")
    if "record_usb_platform_state" not in init_text:
        raise RuntimeError("missing platform-device USB diagnostics")
    if "waiting_for_supplier" not in init_text:
        raise RuntimeError("missing fw_devlink waiting-for-supplier diagnostics")
    if "platform_supplier consumer=" not in init_text:
        raise RuntimeError("missing supplier driver-state diagnostics")
    if "record_supplier_tree" not in init_text or "link_status=" not in init_text:
        raise RuntimeError("missing recursive devlink status diagnostics")
    if "try_manual_dwc3_bind" not in init_text:
        raise RuntimeError("missing manual dwc3-qcom bind diagnostic")

    if "/bin/busybox sleep 1" not in init_text:
        raise RuntimeError("UDC/host wait loops must use explicit BusyBox sleep")
    if "USB UDC test skipped because gadget setup failed" not in init_text:
        raise RuntimeError("gadget failure must gate UDC testing")
    if "\n sleep 1\n" in init_text or "\n  sleep 1\n" in init_text:
        raise RuntimeError("bare sleep 1 found; use /bin/busybox sleep 1")

    print("PASS: initramfs diagnostic markers and control flow")

    print("PASS: bring-up script preflight")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
