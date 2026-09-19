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
PROFILE="${GTS9_CONFIG_PROFILE:-bringup}"
BRINGUP_CONFIG="$ROOT/kernel/config/gts9wifi-bringup.config"
S9U_REFERENCE_CONFIG="$ROOT/kernel/config/s9u-mainline-aarch64.reference.config"
S9U_NOBTI_CONFIG="$ROOT/kernel/config/s9u-nobti.fragment"
S9U_VA48_CONFIG="$ROOT/kernel/config/s9u-va48.fragment"

# Optional compiler cache.  Auto-enable when ccache is installed, while keeping
# an explicit opt-out for reproducibility checks and constrained hosts.
CCACHE_MODE="${GTS9_CCACHE:-auto}"
CCACHE_ENABLED=0
case "$CCACHE_MODE" in
 auto)
  command -v ccache >/dev/null 2>&1 && CCACHE_ENABLED=1
  ;;
  1|on|yes|true)
  command -v ccache >/dev/null 2>&1 || {
   echo "GTS9_CCACHE=$CCACHE_MODE requested but ccache is not installed" >&2
   exit 1
  }
  CCACHE_ENABLED=1
  ;;
  0|off|no|false)
  ;;
 *)
  echo "Unknown GTS9_CCACHE: $CCACHE_MODE (expected auto, 1/on/yes/true, or 0/off/no/false)" >&2
  exit 1
  ;;
esac

MAKE_TOOLCHAIN=(ARCH=arm64 LLVM=1)
if (( CCACHE_ENABLED )); then
 : "${HOME:?HOME must be set when ccache is enabled}"
 export CCACHE_DIR="${CCACHE_DIR:-$HOME/.cache/ccache}"
 export CCACHE_MAXSIZE="${CCACHE_MAXSIZE:-20G}"
 export CCACHE_COMPILERCHECK="${CCACHE_COMPILERCHECK:-content}"
 mkdir -p "$CCACHE_DIR"
 MAKE_TOOLCHAIN+=(CC="ccache clang" HOSTCC="ccache clang")
 echo "ccache enabled: dir=$CCACHE_DIR max=$CCACHE_MAXSIZE compiler_check=$CCACHE_COMPILERCHECK"
else
 echo "ccache disabled (GTS9_CCACHE=$CCACHE_MODE)"
fi

mkdir -p work artifacts/kernel

case "$PROFILE" in
 bringup|s9u-control|s9u-nobti|s9u-va48) ;;
 *)
  echo "Unknown GTS9_CONFIG_PROFILE: $PROFILE (expected bringup, s9u-control, s9u-nobti or s9u-va48)" >&2
  exit 1
  ;;
esac
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
case "$PROFILE" in
 bringup)
  make -C "$SRC" O="$OUT" "${MAKE_TOOLCHAIN[@]}" KCONFIG_ALLCONFIG="$BRINGUP_CONFIG" allnoconfig
  ;;
 s9u-control|s9u-nobti|s9u-va48)
  [[ -f "$S9U_REFERENCE_CONFIG" ]] || { echo "Missing S9 Ultra reference config" >&2; exit 1; }
  rm -f "$OUT/.config"
  merge_inputs=("$S9U_REFERENCE_CONFIG" "$BRINGUP_CONFIG")
  if [[ "$PROFILE" == "s9u-nobti" || "$PROFILE" == "s9u-va48" ]]; then
    [[ -f "$S9U_NOBTI_CONFIG" ]] || { echo "Missing S9 Ultra no-BTI override" >&2; exit 1; }
    merge_inputs+=("$S9U_NOBTI_CONFIG")
  fi
  if [[ "$PROFILE" == "s9u-va48" ]]; then
    [[ -f "$S9U_VA48_CONFIG" ]] || { echo "Missing S9 Ultra VA48 override" >&2; exit 1; }
    merge_inputs+=("$S9U_VA48_CONFIG")
  fi
  KCONFIG_CONFIG="$OUT/.config" bash "$SRC/scripts/kconfig/merge_config.sh" -m -O "$OUT" \
    "${merge_inputs[@]}"
  make -C "$SRC" O="$OUT" "${MAKE_TOOLCHAIN[@]}" olddefconfig
  ;;
esac
python3 scripts/check-config.py "$OUT/.config" --profile "$PROFILE"
make -C "$SRC" O="$OUT" "${MAKE_TOOLCHAIN[@]}" -j"${JOBS:-8}" Image qcom/sm8550-samsung-gts9wifi.dtb
if (( CCACHE_ENABLED )); then
 echo "ccache statistics after kernel build:"
 ccache --show-stats
fi
cp "$OUT/arch/arm64/boot/Image" artifacts/kernel/
cp "$OUT/arch/arm64/boot/dts/qcom/sm8550-samsung-gts9wifi.dtb" artifacts/kernel/
cp "$OUT/.config" artifacts/kernel/config
printf '%s\n' "$PROFILE" > artifacts/kernel/config-profile.txt
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
