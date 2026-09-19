# Next test: primary virtual-switch probe

The no-BTI control produced the same result as the BTI-enabled S9U control:
`G9E1313` is present while `G9E1314` is absent. Therefore disabling
`CONFIG_ARM64_BTI_KERNEL` did not move the failure point.

This test keeps the `s9u-nobti` profile unchanged and adds three more precise
markers around the final branch from the identity-mapped early path into
`__primary_switched`.

```text
G9V0001  __primary_switched virtual target loaded into x8
G9V0002  a data load from [x8] succeeded
G9V0003  first inline marker after landing in __primary_switched
```

The `G9V0003` marker is deliberately inline and makes no helper call. This
distinguishes failure to land in the high virtual mapping from failure inside
the existing helper-based G9E1314 marker.

## Build

The patch series changed, so rebuild the generated kernel source:

```bash
python3 scripts/twrp-entry-marker-test.py restore

git pull --rebase origin main
python3 scripts/check-bringup.py

python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-nobti
```

Then verify:

```bash
cat artifacts/kernel/config-profile.txt
python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
```

Expected profile:

```text
s9u-nobti
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

- `G9V0001` absent: execution failed before/at loading the final virtual
  target after `G9E1313`.
- `G9V0001` present but `G9V0002` absent: the calculated high virtual
  target cannot be read through the completed kernel mapping. Focus on TTBR1,
  TCR and the mapping itself.
- `G9V0002` present but `G9V0003` absent: the target is readable as data,
  but the branch/instruction fetch does not successfully enter the high-VA
  target. Focus on executable permissions, translation state and exception
  state at the switch.
- `G9V0003` present but `G9E1314` absent: the virtual switch itself works;
  the existing helper call/write path is what fails at that point.
- `G9E1314` or later markers appear: continue interpreting the existing
  `finalise_el2` and `start_kernel` checkpoints.

Do not change LPA2/VA size, RPMh, USB or the DTS in this round.
