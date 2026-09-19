# Next test: S9 Ultra runtime config with VA48/PA48 geometry

## Why this test

The exact same four-image S9U/no-BTI bundle has reached different early stages
on separate boots (G9E1313 once, G9E1311 on replay), while the older 163750Z
control still boots Linux through initramfs and USB gadget setup.

This rules out a simple global "device can no longer boot mainline" failure and
makes the S9U-derived early MMU geometry a high-value variable to isolate.

The S9 Ultra reference uses:

```text
CONFIG_ARM64_4K_PAGES=y
CONFIG_ARM64_VA_BITS_52=y
CONFIG_ARM64_PA_BITS_52=y
CONFIG_ARM64_LPA2=y
CONFIG_PGTABLE_LEVELS=5
```

The `s9u-va48` control keeps the S9U runtime/PM/PSCI/RPMh/interconnect feature
set and the existing no-BTI control, but changes only the address-translation
geometry to:

```text
CONFIG_ARM64_4K_PAGES=y
CONFIG_ARM64_VA_BITS_48=y
# CONFIG_ARM64_VA_BITS_52 is not set
CONFIG_ARM64_PA_BITS_48=y
# CONFIG_ARM64_PA_BITS_52 is not set
# CONFIG_ARM64_LPA2 is not set
CONFIG_PGTABLE_LEVELS=4
```

`CONFIG_ARM64_LPA2` and `CONFIG_PGTABLE_LEVELS` are derived by Kconfig; the
build validator checks the resolved final `.config`.

The diagnostic patch series is intentionally left unchanged from the current
tree so this test does not add another head.S instrumentation variable.

## Build

Restore the previous test first:

```bash
python3 scripts/twrp-entry-marker-test.py restore
```

Then update and validate:

```bash
git pull --rebase origin main
python3 scripts/check-bringup.py
```

Build:

```bash
python3 scripts/twrp-entry-marker-test.py build \
  --config-profile s9u-va48
```

A `--clean-source` rebuild is not required for this commit because the kernel
patch series is unchanged. ccache can therefore accelerate the configuration
control build.

Confirm the resolved geometry:

```bash
cat artifacts/kernel/config-profile.txt

grep -E 'CONFIG_ARM64_(4K_PAGES|VA_BITS_48|VA_BITS_52|PA_BITS_48|PA_BITS_52|LPA2)|CONFIG_PGTABLE_LEVELS' \
  artifacts/kernel/config
```

Expected:

```text
s9u-va48
CONFIG_ARM64_4K_PAGES=y
CONFIG_ARM64_VA_BITS_48=y
# CONFIG_ARM64_VA_BITS_52 is not set
CONFIG_ARM64_PA_BITS_48=y
# CONFIG_ARM64_PA_BITS_52 is not set
# CONFIG_ARM64_LPA2 is not set
CONFIG_PGTABLE_LEVELS=4
```

Also verify the runtime options remain enabled:

```bash
grep -E 'CONFIG_ARM_PSCI_CPUIDLE_DOMAIN|CONFIG_DT_IDLE_GENPD|CONFIG_QCOM_RPMH|CONFIG_INTERCONNECT_QCOM_SM8550' \
  artifacts/kernel/config
```

Then verify the bundle:

```bash
python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
```

## Flash and collect

```bash
python3 scripts/twrp-entry-marker-test.py flash
```

After the normal observation window, return to TWRP if necessary:

```bash
python3 scripts/twrp-entry-marker-test.py collect
python3 scripts/twrp-entry-marker-test.py restore
```

## Interpretation

- Linux/setup_arch appears: simplifying VA/PA/LPA2 geometry materially changes
  the S9U-derived early boot path. Keep this profile and continue to the RPMh /
  supplier-chain runtime problem.
- Execution consistently moves deeper than the VA52/PA52 control but still
  stops early: narrow the remaining mapping/relocation variable from this
  geometry.
- It still stops at G9E1311/G9E1313 with similar run-to-run variation: the
  52-bit/LPA2 geometry is not sufficient to explain the early failure, and the
  next test should isolate another S9U config/layout variable rather than add
  more early markers.

Do not modify the DTS, USB, RPMh dependency graph, or marker patch series in
this round.
