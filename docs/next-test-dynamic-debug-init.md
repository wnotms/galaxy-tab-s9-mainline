# Next test: dynamic_debug early initcall

The s9u-va48 build has now passed the ARM64 virtual switch and entered normal
Linux initialization.  The latest persistent log reaches:

```text
GTS9WIFI: kernel_init_freeable before_pre_smp_initcalls
...
calling dynamic_debug_init+0x0/0x268 @ 1
```

with no matching `initcall ... returned` record.

This round keeps the same s9u-va48 config and adds only normal printk
checkpoints inside `dynamic_debug_init()`.  The markers report descriptor
counts and bounded progress through the __dyndbg table without dereferencing
module-name strings in the marker itself.

Build with a clean patched source tree because the patch series changed:

```bash
python3 scripts/twrp-entry-marker-test.py restore
git pull --rebase origin main
JOBS=10 python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-va48
python3 scripts/twrp-entry-marker-test.py flash
```

After observation, collect and restore:

```bash
python3 scripts/twrp-entry-marker-test.py collect
python3 scripts/twrp-entry-marker-test.py restore
```

Interpretation:

- only `dynamic_debug_init enter`: failure occurs before the descriptor walk;
- `walk i=0` but no later progress: suspect the first descriptor/module-name
  comparison;
- progress stops at a particular `walk i=N`: suspect a malformed descriptor
  near N;
- `add_begin` without `add_done`: suspect ddebug table allocation/list
  insertion;
- `walk_done` but no `final_add_done`: suspect final built-in module table
  insertion;
- `before_parse_args` but no `after_parse_args`: suspect command-line
  reparse;
- `after_parse_args` and then the initcall return appears: dynamic-debug is
  not the actual blocker and the next early initcall must be inspected.
