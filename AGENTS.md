# Codex handoff: Galaxy Tab S9 mainline bring-up

This file is the **current handoff for coding agents** working on this repository.
Read it before changing the kernel, DT, boot bundle, or test harness.

Last updated: 2026-09-19  
Repository: `wnotms/galaxy-tab-s9-mainline`  
Handoff baseline HEAD: `f4c5a5ac2c1952fe98d4392c1e2bfb7471f76e94`

## 1. Scope

Target device:

- Samsung Galaxy Tab S9 Wi-Fi
- model: SM-X710
- codename: `gts9wifi`
- SoC: Qualcomm SM8550

This is a **Linux mainline bring-up project**, not an Android kernel feature project.
The immediate goal is to make the pinned mainline kernel boot reliably far enough to
identify and fix the next platform blocker while preserving reproducible A/B tests.

Do not generalize results to SM-X716, S9+, S9 Ultra, or earlier board revisions.

## 2. Pinned kernel and build baseline

Authoritative source pins are in `device/sources.json`.

Current Linux baseline:

- tag: `v7.2-rc3`
- commit: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`

The build script is `scripts/build-kernel.sh`.

Supported config profiles currently include:

- `bringup`
- `s9u-control`
- `s9u-nobti`
- `s9u-va48`
- `s9u-va48-norelr`

The active patch list is **only** `kernel/patches/series`.
There are additional patch files in `kernel/patches/` that are not necessarily
active. Never infer that a patch is applied merely because the file exists.

Before changing patches, run or inspect:

```sh
python3 scripts/check-patch-series.py
cat kernel/patches/series
```

## 3. Important confirmed results

The device is capable of entering mainline Linux with a known-good archived bundle.
A/B replay recorded in:

`docs/boot-test-entry-marker-20260918T170424Z.md`

That replay confirmed:

- Linux executes on the device.
- `setup_arch` checkpoints complete.
- all initcall levels complete in that known-good path.
- `kernel_execve("/init")` returns 0.
- initramfs starts.
- devtmpfs, procfs, sysfs, devpts and configfs are mounted.
- USB gadget configfs setup succeeds.

That same known-good path still has a later USB problem:

- `/sys/class/udc` is empty.
- `dwc3` / `dwc3-qcom` are not bound.
- manual bind of `a600000.usb` returns `EAGAIN/EPROBE_DEFER`.
- TCSR / eUSB2 PHY supplier binding is incomplete.

Therefore, do **not** treat “device cannot execute mainline Linux at all” as the
current working hypothesis.

Earlier tests also showed that ABL/recovery selection can invalidate an experiment.
A log containing recovery boot data, stale TWRP output, or merely `UEFI End` is
not proof that the candidate Linux kernel executed.

## 4. Current active blocker

The current investigation has moved past the earliest ABL/EFI handoff and into a
specific Linux init path.

The latest s9u-va48 replay reaches:

`dynamic_debug_init()`

The built-in `__dyndbg` section reports:

- descriptors: 17,160
- descriptor walk observed through approximately `i=7168`
- `i=8192` was not observed
- `walk_done` was not observed

The recorded section geometry is internally consistent: the observed section span
matches 17,160 descriptors at the expected descriptor size, and logged iterator
addresses remained consistent through the last confirmed checkpoint.

This makes a globally broken `__dyndbg` section boundary less likely than a
failure associated with a particular descriptor range or module transition.

The active diagnostic patch is:

`kernel/patches/record-dynamic-debug-init-checkpoints.patch`

The immediate test plan is:

`docs/next-test-dynamic-debug-walk-window.md`

It narrows the range `i=7168..8192` by adding:

- `cmp_before` / `cmp_after` every 64 descriptors
- `add_begin` / `add_done` around every module transition in that window

## 5. How to interpret the next log

Use the marker pairs literally.

### Case A: strcmp-side failure

If the last markers look like:

```text
cmp_before i=N
# no cmp_after i=N
```

focus on:

```c
strcmp(modname, iter->modname)
```

and the corresponding `struct _ddebug` entry.

Primary suspects then include:

- invalid or unexpectedly relocated `modname` pointer
- corruption of one descriptor
- a mapping/relocation issue affecting the descriptor's referenced strings
- a boundary/alignment issue local to that descriptor range

Do not immediately rewrite the entire dynamic-debug subsystem.

### Case B: ddebug_add_module-side failure

If the log reaches:

```text
cmp_after i=N
add_begin ...
# no add_done
```

focus on `ddebug_add_module()` and its allocation/table/list path.

### Case C: checkpoints continue to 8192

If `i=8192` appears, the failure moved later.
Keep the exact same image and obtain a strict replay before changing another
subsystem.

## 6. Exact next experiment

The repository already contains the intended single-variable test.

Recommended sequence:

```sh
python3 scripts/twrp-entry-marker-test.py restore
git pull --rebase origin main
JOBS=10 python3 scripts/twrp-entry-marker-test.py build \
  --clean-source \
  --config-profile s9u-va48
python3 scripts/twrp-entry-marker-test.py flash
```

After the observation window:

```sh
python3 scripts/twrp-entry-marker-test.py collect
python3 scripts/twrp-entry-marker-test.py restore
```

Preserve the collected artifact directory and write a result document before
changing the diagnostic window again.

## 7. Areas that should NOT be changed yet

Until the `dynamic_debug_init()` window is resolved, avoid unrelated changes to:

- DTB hardware nodes
- USB/DWC3
- eUSB2 PHY
- EFI/EFI_STUB
- Android boot image layout
- initramfs behavior
- display/input
- WLAN/audio/GPU
- broad ARM64 entry instrumentation

Those areas have already consumed multiple experiments and changing them together
would destroy the current single-variable diagnosis.

In particular, do not restart from the old assumption that the Samsung logo or
lack of USB enumeration means the kernel did not execute.

## 8. ARM64 entry-marker history

There are several ARM64 entry/MMU diagnostic patch files in `kernel/patches/`.
Some were used to diagnose pre-MMU/MMU-on/high-VA transitions and helper placement.

Key lesson already established: code intended to run after the final virtual switch
must be reachable through the normal kernel mapping. A helper living only in
`.idmap.text` must not be called as a normal post-switch kernel-VA target.

Do not reintroduce an old entry-marker patch blindly. Check the active
`kernel/patches/series` first and read the corresponding test report.

## 9. Config/relocation investigation context

Current profiles intentionally allow controlled comparison of:

- S9 Ultra reference config vs minimal bring-up config
- BTI disabled
- VA48
- RELR disabled

The current dynamic-debug investigation is relevant to relocation and referenced
string pointers, so `CONFIG_RELOCATABLE`, VA layout, RELA/RELR behavior, and the
final linked `__dyndbg` contents are legitimate next areas to inspect **after**
the exact failing descriptor/module boundary is known.

Prefer offline inspection of the built `vmlinux` first:

- locate `__start___dyndbg` / `__stop___dyndbg`
- map descriptor index to address
- inspect the descriptor at the final successful and first failing indexes
- resolve `modname`, `function`, `filename`, and `format` references
- compare control / VA48 / no-RELR builds

Do not introduce another runtime variable until that inspection is complete.

## 10. Test discipline

For every real-device experiment:

1. Keep one functional variable whenever possible.
2. Record the exact kernel config profile.
3. Record Image/DTB/boot-bundle SHA256 values.
4. Distinguish cold boot, warm boot and recovery selection.
5. Treat stale `last_kmsg` as possible unless the new run is positively identified.
6. Do not treat an empty pstore as proof that Linux never ran.
7. Do not treat Samsung-logo persistence as a precise fault location.
8. Restore the original boot partitions after the test unless the user explicitly
   requests otherwise.
9. Preserve raw evidence under ignored `artifacts/`; commit only reproducible
   metadata, scripts, patches and written conclusions.
10. Update this file when the primary blocker changes.

## 11. Repository documentation precedence

For the current bring-up state, use this order:

1. `AGENTS.md` — current Codex handoff and active blocker.
2. latest matching `docs/next-test-*.md` — exact next experiment.
3. latest `docs/boot-test-*.md` / entry-marker report — observed evidence.
4. `kernel/patches/series` — authoritative active patch order.
5. `device/sources.json` — authoritative source pins.
6. `README.md` — project overview only; parts of its historical “current status”
   section lag behind the latest experiments.

## 12. Current objective

Do not attempt a broad “make everything boot” rewrite.

The immediate objective is:

> Identify the exact `__dyndbg` descriptor or module transition between the last
> confirmed checkpoint near index 7168 and the missing checkpoint before/at 8192,
> then determine whether the failure is in descriptor/string access or
> `ddebug_add_module()`.

Once that is known, make the smallest reproducible change that tests the resulting
hypothesis.
