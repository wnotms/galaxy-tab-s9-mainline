# Next test: MMU-on primary-entry checkpoints

## Goal

Continue the exact S9 Ultra config-control path that reached all five MMU-off
entry markers but no \`setup_arch\` marker.

The previous run reached:

\`\`\`text
G9E1301
G9E1302
G9E1303
G9E1304
G9E1305
\`\`\`

Therefore ABL loaded/decompressed the kernel and Linux completed
\`__cpu_setup()\`.  This test narrows the remaining path through MMU enable,
\`early_map_kernel()\`, the primary virtual switch, \`finalise_el2()\`, and the
handoff to \`start_kernel()\`.

## New markers

\`\`\`text
G9E1306  immediately before __enable_mmu
G9E1307  early_map_kernel entered; sec-log identity mapping established
G9E1308  map_fdt completed
G9E1309  early BSS/page-table clear completed
G9E1310  init_feature_override completed
G9E1311  immediately before map_kernel
G9E1312  map_kernel completed
G9E1313  returned from __pi_early_map_kernel
G9E1314  entered __primary_switched
G9E1315  immediately before finalise_el2
G9E1316  finalise_el2 returned
G9E1317  immediately before start_kernel
\`\`\`

The sec-log reservation is identity-mapped only for this diagnostic path while
TTBR0 still uses the initial idmap. MMU-on marker writes clean their data/header
cache lines to PoC so recovery can read them after reset.

## Build

The patch series changed, so the generated kernel source must be rebuilt:

\`\`\`bash
git pull --rebase origin main

python3 scripts/check-bringup.py

python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-control
\`\`\`

Confirm:

\`\`\`bash
cat artifacts/kernel/config-profile.txt
python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
\`\`\`

Expected profile:

\`\`\`text
s9u-control
\`\`\`

## Test

If a previous test is still active, restore it first:

\`\`\`bash
python3 scripts/twrp-entry-marker-test.py restore
\`\`\`

Then:

\`\`\`bash
python3 scripts/twrp-entry-marker-test.py flash
\`\`\`

After the observation window, return to TWRP and collect:

\`\`\`bash
python3 scripts/twrp-entry-marker-test.py collect
\`\`\`

Finally restore:

\`\`\`bash
python3 scripts/twrp-entry-marker-test.py restore
\`\`\`

## Interpretation

- Deepest \`G9E1306\`: failure is at MMU enable or before the diagnostic sec-log
  mapping can be established in \`early_map_kernel()\`.
- \`G9E1307\` through \`G9E1310\`: the MMU is on and early C code is running;
  the last marker localizes FDT/clear/feature-override progress.
- Deepest \`G9E1311\`: investigate \`map_kernel()\` and the large S9U-control
  kernel mapping.
- Deepest \`G9E1312\` or \`G9E1313\`: \`map_kernel()\` returned; focus on the
  virtual switch into \`__primary_switched\`.
- \`G9E1314\` or \`G9E1315\`: the primary virtual mapping is live; focus on the
  setup immediately before/inside \`finalise_el2()\`.
- \`G9E1316\`: \`finalise_el2()\` returned.
- \`G9E1317\` with no Linux banner/setup marker: focus on the
  \`start_kernel()\` entry and its earliest operations.
- Any normal Linux/setup marker supersedes these early checkpoints and means
  the test passed the very-early failure window.

Do not change USB, RPMh, or the X710 DTS in this round.
