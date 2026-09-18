#!/usr/bin/env python3
"""Fail early when Kconfig silently removes a required bring-up driver."""
import sys
from pathlib import Path

required = """ARM64 ARCH_QCOM SMP BLK_DEV_INITRD RD_GZIP BINFMT_ELF
BINFMT_SCRIPT DEVTMPFS PROC_FS SYSFS TMPFS CONFIGFS_FS INET
SM_GCC_8550 SM_TCSRCC_8550 QCOM_SCM QCOM_TZMEM QCOM_RPMH QCOM_RPMHPD
QCOM_SMEM QCOM_PDC PINCTRL_SM8550 PINCTRL_QCOM_SPMI_PMIC SPMI_MSM_PMIC_ARB
REGULATOR_QCOM_RPMH INTERCONNECT_QCOM_SM8550 ARM_SMMU
I2C_QCOM_GENI QCOM_GPI_DMA PHY_SNPS_EUSB2 PHY_NXP_PTN3222
USB_DWC3 USB_DWC3_QCOM USB_GADGET USB_CONFIGFS USB_CONFIGFS_NCM
MMC_SDHCI_MSM EXT4_FS SAMSUNG_GTS9WIFI_SEC_LOG""".split()
config = set(Path(sys.argv[1]).read_text().splitlines())
missing = [name for name in required if f"CONFIG_{name}=y" not in config]
if missing:
    sys.exit("Required built-in options missing: " + ", ".join(missing))
print(f"Verified {len(required)} required built-in options")
