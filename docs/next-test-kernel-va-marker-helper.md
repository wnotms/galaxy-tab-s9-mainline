# Next test: post-switch marker helper in the kernel mapping

## Observation

The `s9u-va48` run reached, in order:

```text
G9E1311
G9E1312
G9E1313
G9V0001
G9V0002
G9V0003
```

and stopped before `G9E1314`.

This is stronger than the earlier result: `G9V0003` is emitted inline at the
first instruction of `__primary_switched`, so the high-VA branch itself
works.  The next control-flow operation introduced by the diagnostics is the
call used to emit `G9E1314`.

The existing helper `gts9wifi_entry_marker_append_mmu_on` resides in
`.idmap.text`.  arm64's linker script places `.idmap.text` in
`.rodata.text`, explicitly described as code that is never executed via the
kernel mapping.  Therefore calling that helper after landing in the kernel
virtual mapping can make the instrumentation itself fault.

## Change

Keep the old helper for the pre-switch markers, but route the four
post-switch markers through a new helper in `.init.text`:

```text
G9E1314
G9E1315
G9E1316
G9E1317
```

No DTS, USB, RPMh, or config-profile setting changes in this round.  Continue
using `s9u-va48`.

## Build and test

Because the patch series changed, a clean patched source tree is required:

```bash
python3 scripts/twrp-entry-marker-test.py restore

git pull --rebase origin main
python3 scripts/check-bringup.py

python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-va48

python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
python3 scripts/twrp-entry-marker-test.py flash
```

After the observation window, return to TWRP if needed:

```bash
python3 scripts/twrp-entry-marker-test.py collect
python3 scripts/twrp-entry-marker-test.py restore
```

## Interpretation

- `G9E1314` appears: the old post-switch helper target was indeed invalid in
  the kernel virtual mapping; continue with the later markers.
- `G9E1315` appears: `init_cpu_task`, vector setup, stack setup,
  `set_cpu_boot_mode_flag`, and any configured KASAN early setup completed.
- `G9E1316` appears: `finalise_el2()` returned.
- `G9E1317` appears but no Linux banner: the failure is narrowed to the
  `start_kernel` call/very earliest C entry.
- Linux/setup_arch appears: the previous post-switch stop was caused by the
  diagnostic helper placement, not by the kernel's normal virtual-switch path.

Do not interpret absence of `G9E1314` as a normal kernel failure unless this
fixed-helper build reproduces it.
