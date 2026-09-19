# Next test: S9 Ultra control without in-kernel BTI

The 2026-09-19 MMU-on trace reached `G9E1313`: `map_kernel()` completed and
`__pi_early_map_kernel()` returned, but `G9E1314` at the beginning of
`__primary_switched` was not recovered.

That narrows the failure to the virtual-address transition immediately after:

```asm
ldr x8, =__primary_switched
adrp x0, KERNEL_START
br x8
```

The S9 Ultra base enables `CONFIG_ARM64_BTI_KERNEL=y`; the minimal X710
allnoconfig baseline does not intentionally enable that option. With BTI
enabled, `map_kernel()` can mark executable kernel mappings guarded on CPUs
with BTI support. This control changes **only that Kconfig choice** while
retaining the S9U PM/PSCI/genpd/RPMh/interconnect environment.

This is a diagnostic control, not a proposed final security configuration.

## Build

Restore the preceding test first, then:

```bash
git pull --rebase origin main
python3 scripts/check-bringup.py

python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-nobti
```

Confirm:

```bash
cat artifacts/kernel/config-profile.txt

grep -E 'CONFIG_ARM64_BTI_KERNEL|CONFIG_ARM_PSCI_CPUIDLE_DOMAIN|CONFIG_DT_IDLE_GENPD|CONFIG_INTERCONNECT_QCOM_SM8550' \
  artifacts/kernel/config

python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
```

Expected:

```text
s9u-nobti
# CONFIG_ARM64_BTI_KERNEL is not set
CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y
CONFIG_DT_IDLE_GENPD=y
CONFIG_INTERCONNECT_QCOM_SM8550=y
```

## Test

```bash
python3 scripts/twrp-entry-marker-test.py flash
```

After the observation window, return to TWRP:

```bash
python3 scripts/twrp-entry-marker-test.py collect
python3 scripts/twrp-entry-marker-test.py restore
```

## Interpretation

- If `G9E1314` and later markers appear, disabling in-kernel BTI changed the
  failing virtual switch. Continue with the same profile and determine whether
  the kernel reaches `start_kernel()`/Linux.
- If Linux/setup markers appear, the BTI-enabled S9U control has a
  device/firmware-sensitive early transition on X710 and the exact BTI/TCR/PTE
  interaction should be isolated before restoring BTI.
- If the result is still exactly `G9E1313`, BTI is not sufficient to explain
  the failure. The next experiment should record the calculated
  `__primary_switched` target/translation state or isolate LPA2/VA handling.
