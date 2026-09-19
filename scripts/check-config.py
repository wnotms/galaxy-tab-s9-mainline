#!/usr/bin/env python3
"""Fail early when Kconfig silently removes a required bring-up driver."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("config", type=Path)
parser.add_argument("--profile", choices=("bringup", "s9u-control"), default="bringup")
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

if args.profile == "s9u-control":
    # These are present in the S9 Ultra's working 7.2-rc3 base config and are
    # deliberately required here so this control is not just the minimal
    # allnoconfig image with a different label.
    required += """SUSPEND PM_SLEEP PM_GENERIC_DOMAINS_SLEEP CPU_PM
CPU_IDLE_MULTIPLE_DRIVERS DT_IDLE_STATES
INTERCONNECT_QCOM_BCM_VOTER INTERCONNECT_QCOM_RPMH""".split()

config = set(args.config.read_text().splitlines())
missing = [name for name in required if f"CONFIG_{name}=y" not in config]
if missing:
    raise SystemExit("Required built-in options missing: " + ", ".join(missing))
if "CONFIG_RANDOMIZE_BASE=y" in config:
    raise SystemExit("Diagnostic image must keep KASLR disabled")
print(f"Verified {len(required)} required built-in options for profile {args.profile}")
