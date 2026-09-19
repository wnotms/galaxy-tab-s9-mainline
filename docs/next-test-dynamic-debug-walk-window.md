# Next test: narrow dynamic_debug descriptor walk

The replayed s9u-va48 bundle entered Linux and reached dynamic_debug_init().
The descriptor section reported 17,160 entries and the walk reached i=7168,
but did not reach i=8192 or walk_done.

The section bounds are internally consistent: the reported address span is
960,960 bytes, exactly 17,160 * 56 bytes, and the logged iter addresses match
start + i * 56 through i=7168. This makes a broken __dyndbg section length less
likely than a failure on a particular descriptor/module transition.

This test keeps the same s9u-va48 profile and adds only:
- cmp_before/cmp_after every 64 descriptors from i=7168 through i=8192;
- add_begin/add_done for every module transition in that same window;
- collector patterns for those markers.

Build:
```bash
python3 scripts/twrp-entry-marker-test.py restore
git pull --rebase origin main
JOBS=10 python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-va48
python3 scripts/twrp-entry-marker-test.py flash
```

After observation:
```bash
python3 scripts/twrp-entry-marker-test.py collect
python3 scripts/twrp-entry-marker-test.py restore
```

Interpretation:
- cmp_before N but no cmp_after N: strcmp() fault/hang at descriptor N.
- cmp_after N then add_begin near N but no add_done: ddebug_add_module() is the blocker.
- add_done continues but next 64-entry cmp_before is missing: fault is in the
  descriptor range after the last completed checkpoint.
- reaching i=8192 means the failure moved again; retain the same image for an
  exact replay before changing another subsystem.
