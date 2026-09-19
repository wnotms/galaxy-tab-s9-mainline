# Next test: s9u-va48 without RELR packing

## Why this control exists

The latest Linux-reaching run reports:

```text
dynamic_debug_init enter descs=17160 ...
dynamic_debug_init walk i=0 ...
base_modname=0000000000178000
current_modname=0000000000178000
```

A built-in `struct _ddebug.modname` is a normal kernel pointer.  A value such
as `0x178000` is not a valid kernel virtual pointer for this image and
explains why the first `strcmp(modname, iter->modname)` cannot complete.

The pinned arm64 kernel is relocatable.  The S9 Ultra reference config enables
`CONFIG_RELR=y`, while the bring-up fragment disables KASLR but leaves
`CONFIG_RELOCATABLE=y`.  This profile changes only the relocation packing
format:

```text
s9u-va48:         CONFIG_RELR=y
s9u-va48-norelr: CONFIG_RELR=n
```

Both remain relocatable, VA48/PA48, four-level, no-LPA2 and no-BTI.

## Preserve the current vmlinux evidence first

Before using `--clean-source`, inspect the current RELR build:

```bash
grep -E 'CONFIG_(RELOCATABLE|RELR|RANDOMIZE_BASE)=' artifacts/kernel/config

DYNDBG=$(llvm-nm -n work/kernel-build/vmlinux |
  awk '$3=="__start___dyndbg" {print $1; exit}')
echo "__start___dyndbg=$DYNDBG"

llvm-readelf -rW work/kernel-build/vmlinux |
  grep -i "$DYNDBG" || true

llvm-objdump -s -j __dyndbg work/kernel-build/vmlinux |
  head -n 12
```

Keep that output with the run record.

## Build no-RELR control

```bash
python3 scripts/twrp-entry-marker-test.py restore
git pull --rebase origin main

JOBS=10 python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-va48-norelr

grep -E 'CONFIG_(RELOCATABLE|RELR|RANDOMIZE_BASE)=' artifacts/kernel/config
```

Expected:

```text
CONFIG_RELOCATABLE=y
# CONFIG_RELR is not set
# CONFIG_RANDOMIZE_BASE is not set
```

Then flash, collect and restore normally.

## Interpretation

If the no-RELR image reaches `dynamic_debug_init()`, the first
`base_modname/current_modname` should be a canonical kernel VA, not a small
value such as `0x178000`.  If repeated no-RELR replays also stop showing the
map_kernel/run-to-run failures, RELR relocation handling becomes the primary
suspect.

A single successful no-RELR boot is not enough to prove that conclusion:
repeat the exact same bundle because this device has already shown
state-dependent boot depth.
