#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
python3 scripts/check-patch-series.py --quiet
PIN=$(python3 -c 'import json; print(json.load(open("device/sources.json"))["linux_commit"])')
TAG=$(python3 -c 'import json; print(json.load(open("device/sources.json"))["linux_tag"])')
CACHE="$ROOT/work/linux-mainline"
SRC="$ROOT/work/kernel-src"
OUT="$ROOT/work/kernel-build"
mkdir -p work artifacts/kernel
if [[ ! -d "$CACHE/.git" ]]; then
 git clone --depth 1 --branch "$TAG" https://github.com/torvalds/linux.git "$CACHE"
fi
[[ $(git -C "$CACHE" rev-parse HEAD) == "$PIN" ]] || { echo 'Linux cache does not match pinned commit' >&2; exit 1; }
export KBUILD_BUILD_USER=gts9wifi KBUILD_BUILD_HOST=builder KBUILD_BUILD_VERSION=1
export KBUILD_BUILD_TIMESTAMP="$(git -C "$CACHE" show -s --format=%cD "$PIN")"
PATCH_ID=$(python3 - <<'PY'
import hashlib,pathlib
p=pathlib.Path('kernel/patches'); h=hashlib.sha256()
for n in (p/'series').read_text().splitlines():
 if n and not n.startswith('#'): h.update(n.encode()); h.update((p/n).read_bytes())
print(h.hexdigest())
PY
)
if [[ ! -f "$SRC/.gts9-source" ]]; then
 [[ ! -e "$SRC" ]] || { echo 'Unmarked source directory; move work/kernel-src aside' >&2; exit 1; }
 mkdir -p "$SRC"
 git -C "$CACHE" archive "$PIN" | tar -x -C "$SRC"
 while IFS= read -r patch; do
  [[ -z "$patch" || "$patch" == \#* ]] && continue
  GIT_CEILING_DIRECTORIES="$ROOT/work" git -C "$SRC" apply --check "$ROOT/kernel/patches/$patch"
  GIT_CEILING_DIRECTORIES="$ROOT/work" git -C "$SRC" apply "$ROOT/kernel/patches/$patch"
 done < kernel/patches/series
 printf '%s %s\n' "$PIN" "$PATCH_ID" > "$SRC/.gts9-source"
fi
[[ $(cat "$SRC/.gts9-source") == "$PIN $PATCH_ID" ]] || { echo 'Source pin or patches changed; move work/kernel-src aside' >&2; exit 1; }
cp kernel/dts/sm8550-samsung-gts9wifi.dts "$SRC/arch/arm64/boot/dts/qcom/"
mkdir -p "$OUT"
make -C "$SRC" O="$OUT" ARCH=arm64 LLVM=1 KCONFIG_ALLCONFIG="$ROOT/kernel/config/gts9wifi-bringup.config" allnoconfig
python3 scripts/check-config.py "$OUT/.config"
make -C "$SRC" O="$OUT" ARCH=arm64 LLVM=1 -j"${JOBS:-8}" Image qcom/sm8550-samsung-gts9wifi.dtb
cp "$OUT/arch/arm64/boot/Image" artifacts/kernel/
cp "$OUT/arch/arm64/boot/dts/qcom/sm8550-samsung-gts9wifi.dtb" artifacts/kernel/
cp "$OUT/.config" artifacts/kernel/config
python3 scripts/check-device-tree.py artifacts/kernel/sm8550-samsung-gts9wifi.dtb
python3 - <<'DTB_PIN_CHECK'
import hashlib,json,pathlib
baseline=json.loads(pathlib.Path('device/firmware-dtb-baseline.json').read_text())
dtb=pathlib.Path('artifacts/kernel/sm8550-samsung-gts9wifi.dtb').read_bytes()
allowed={(baseline['sha256'],baseline['size'])}
variant=baseline.get('gpio_reserved_variant')
if variant: allowed.add((variant['sha256'],variant['size']))
if (hashlib.sha256(dtb).hexdigest(),len(dtb)) not in allowed:
 raise SystemExit('Firmware-facing DTB differs from the pinned baseline or GPIO-only candidate')
print('Firmware-facing DTB matches the pinned baseline or GPIO-only variant')
DTB_PIN_CHECK
sha256sum artifacts/kernel/Image artifacts/kernel/sm8550-samsung-gts9wifi.dtb artifacts/kernel/config > artifacts/kernel/SHA256SUMS
echo 'Kernel and DTB: artifacts/kernel/'
