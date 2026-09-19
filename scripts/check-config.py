#!/usr/bin/env python3
"""Fail early when Kconfig silently removes a required bring-up driver."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("config", type=Path)
parser.add_argument("--profile", choices=("bringup", "s9u-control", "s9u-nobti", "s9u-va48", "s9u-va48-norelr"), default="bringup")
args = parser.parse_args()

required = """ARM64 ARCH_QCOM KERNEL_MODE_NEON EFI EFI_STUB RELOCATABLE SMP BLK_DEV_INITRD RD_GZIP BINFMT_ELF
BINFMT_SCRIPT DEVTMPFS PROC_FS SYSFS TMPFS CONFIGFS_FS INET
ARM_PSCI_CPUIDLE ARM_PSCI_CPUIDLE_DOMAIN DT_IDLE_GENPD PM_GENERIC_DOMAINS_OF
SM_GCC_8550 SM_TCSRCC_8550 QCOM_SCM QCOM_TZMEM QCOM_RPMH QCOM_RPMHPD
QCOM_SMEM QCOM_PDC PINCTRL_SM8550 PINCTRL_QCOM_SPMI_PMIC SPMI_MSM_PMIC_ARB
REGULATOR_QCOM_RPMH INTERCONNECT_QCOM_SM8550 ARM_SMMU
I2C_QCOM_GENI QCOM_GPI_DMA PHY_SNPS_EUSB2 PHY_NXP_PTN3222
USB_DWC3 USB_DWC3_QCOM USB_GADGET USB_CONFIGFS USB_CONFIGFS_NCM
MMC_SDHCI_MSM EXT4_FS SAMSUNG_GTS9WIFI_SEC_LOG""".split()

if args.profile in ("s9u-control", "s9u-nobti", "s9u-va48", "s9u-va48-norelr"):
    # These are present in the S9 Ultra's working 7.2-rc3 base config and are
    # deliberately required here so this control is not just the minimal
    # allnoconfig image with a different label.
    required += """SUSPEND PM_SLEEP PM_GENERIC_DOMAINS_SLEEP CPU_PM
CPU_IDLE_MULTIPLE_DRIVERS DT_IDLE_STATES
INTERCONNECT_QCOM_BCM_VOTER INTERCONNECT_QCOM_RPMH""".split()

config = set(args.config.read_text().splitlines())

def enabled(name: str) -> bool:
    return f"CONFIG_{name}=y" in config

def require_lines(lines: set[str], description: str) -> None:
    missing = sorted(lines - config)
    if missing:
        raise SystemExit(description + ": " + ", ".join(missing))

if args.profile in ("s9u-nobti", "s9u-va48", "s9u-va48-norelr") and enabled("ARM64_BTI_KERNEL"):
    raise SystemExit(f"{args.profile} control must keep CONFIG_ARM64_BTI_KERNEL disabled")

if args.profile in ("s9u-va48", "s9u-va48-norelr"):
    # Kconfig may omit disabled invisible/choice symbols entirely instead of
    # emitting '# CONFIG_FOO is not set'. Validate the selected positive
    # geometry and reject forbidden y-values rather than requiring comments.
    require_lines(
        {
            "CONFIG_ARM64_4K_PAGES=y",
            "CONFIG_ARM64_VA_BITS_48=y",
            "CONFIG_ARM64_VA_BITS=48",
            "CONFIG_ARM64_PA_BITS_48=y",
            "CONFIG_ARM64_PA_BITS=48",
            "CONFIG_PGTABLE_LEVELS=4",
        },
        "s9u-va48 did not resolve the expected 4K/VA48/PA48/4-level geometry",
    )
    forbidden = [
        name
        for name in ("ARM64_VA_BITS_52", "ARM64_PA_BITS_52", "ARM64_LPA2")
        if enabled(name)
    ]
    if forbidden:
        raise SystemExit(
            f"{args.profile} unexpectedly enabled: "
            + ", ".join("CONFIG_" + name for name in forbidden)
        )

if args.profile == "s9u-va48" and not enabled("RELR"):
    raise SystemExit("s9u-va48 control must keep CONFIG_RELR enabled")
if args.profile == "s9u-va48-norelr" and enabled("RELR"):
    raise SystemExit("s9u-va48-norelr must keep CONFIG_RELR disabled")

if args.profile == "s9u-va48-norelr" and enabled("RELR"):
    raise SystemExit("s9u-va48-norelr must keep CONFIG_RELR disabled")

missing = [name for name in required if f"CONFIG_{name}=y" not in config]
if missing:
    raise SystemExit("Required built-in options missing: " + ", ".join(missing))
if "CONFIG_RANDOMIZE_BASE=y" in config:
    raise SystemExit("Diagnostic image must keep KASLR disabled")
print(f"Verified {len(required)} required built-in options for profile {args.profile}")
