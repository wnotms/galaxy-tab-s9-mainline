# Next test: VA48 without RELR relocation packing

The current s9u-va48 run entered dynamic_debug_init() but the first built-in
descriptor reported:

```text
base_modname=0000000000178000
current_modname=0000000000178000
```

That is not a canonical kernel virtual address.  The next operation is
strcmp(modname, iter->modname), so this run is consistent with an immediate
fault on an unrelocated/corrupted descriptor pointer.

The S9 Ultra reference enables CONFIG_RELOCATABLE and CONFIG_RELR.  arm64
relocate_kernel() applies RELA entries from explicit addends and applies RELR
entries by adding the runtime displacement to in-place values.  This control
keeps the same VA48/PA48/no-BTI setup but disables CONFIG_RELR, forcing the
relative relocation table away from the RELR path.

Build:

```bash
python3 scripts/twrp-entry-marker-test.py restore
git pull --rebase origin main
JOBS=10 python3 scripts/twrp-entry-marker-test.py build \
  --config-profile s9u-va48-norelr
```

No --clean-source is required because the active patch series is unchanged.

Verify:

```bash
grep -E 'CONFIG_(RELR|RELOCATABLE|RANDOMIZE_BASE|ARM64_VA_BITS=|ARM64_PA_BITS=|PGTABLE_LEVELS)' \
  artifacts/kernel/config
cat artifacts/kernel/config-profile.txt
```

Expected:

```text
CONFIG_RELOCATABLE=y
# CONFIG_RELR is not set
# CONFIG_RANDOMIZE_BASE is not set
CONFIG_ARM64_VA_BITS=48
CONFIG_ARM64_PA_BITS=48
CONFIG_PGTABLE_LEVELS=4
s9u-va48-norelr
```

Then flash/collect normally.

Interpretation:

- If dynamic_debug_init now reports a canonical ffff... modname and progresses,
  RELR/in-place relocation handling becomes a strong suspect.
- If the first modname is still a small value such as 0x178000, RELR packing is
  not sufficient to explain it; inspect the static vmlinux relocation entry and
  runtime relocation offset next.
- If the image again stops before map_kernel returns, exact-replay the same
  bundle before drawing a relocation-format conclusion.
