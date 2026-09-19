#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

PIN=$(python3 -c 'import json; print(json.load(open("device/sources.json"))["linux_commit"])')
TAG=$(python3 -c 'import json; print(json.load(open("device/sources.json"))["linux_tag"])')
PATCH_DIR="$ROOT/kernel/patches"
SERIES="$PATCH_DIR/series"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
linux="$tmp/linux"
paths="$tmp/paths"

# Keep CI lightweight: fetch the pinned tree metadata first, then materialize
# only files touched by our patch series.
git clone --quiet --filter=blob:none --no-checkout --depth 1 --branch "$TAG" \
  https://github.com/torvalds/linux.git "$linux"

actual=$(git -C "$linux" rev-parse HEAD)
if [[ "$actual" != "$PIN" ]]; then
  echo "Pinned Linux mismatch: $actual != $PIN" >&2
  exit 1
fi

while IFS= read -r patch; do
  [[ -z "$patch" || "$patch" == \#* ]] && continue
  sed -n 's#^diff --git a/\([^ ]*\) b/.*#\1#p' "$PATCH_DIR/$patch"
done < "$SERIES" | sort -u > "$paths"

git -C "$linux" sparse-checkout init --no-cone >/dev/null
git -C "$linux" sparse-checkout set --stdin < "$paths"
git -C "$linux" checkout --quiet --detach "$PIN"

count=0
while IFS= read -r patch; do
  [[ -z "$patch" || "$patch" == \#* ]] && continue
  echo "CHECK/APPLY: $patch"
  git -C "$linux" apply --check "$PATCH_DIR/$patch"
  git -C "$linux" apply "$PATCH_DIR/$patch"
  count=$((count + 1))
done < "$SERIES"

echo "PASS: applied $count patches in series order to pinned Linux $PIN"
