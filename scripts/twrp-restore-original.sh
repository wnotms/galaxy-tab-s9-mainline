#!/system/bin/sh
# SPDX-License-Identifier: MIT
# SM-X710 owner snapshot, X710ZCU5CYH4. Run with sh from TWRP.
set -eu
fail() { echo "ERROR: $*" >&2; exit 1; }
case "${1:---check}" in --check|--restore) mode=${1:---check} ;; *) fail "Usage: sh $0 [--check|--restore] [backup-directory]" ;; esac
[ "$#" -le 2 ] || fail "Too many arguments"
backup=${2:-$(dirname "$0")}
[ "$(id -u)" = 0 ] || fail "Root required"
[ -n "$(pidof recovery || true)" ] || fail "Run inside TWRP recovery"
[ "$(getprop ro.boot.em.model)" = SM-X710 ] || fail "Expected SM-X710"
[ "$(getprop ro.bootloader)" = X710ZCU5CYH4 ] || fail "Firmware differs from captured snapshot"
for tool in blockdev sha256sum dd sync wc tr; do command -v "$tool" >/dev/null || fail "Missing $tool"; done
image_sha256() { result=$(sha256sum "$1") || fail "Cannot hash $1"; echo "${result%% *}"; }
# Validate ALL backups and target geometry before the first write.
[ -f "$backup/boot.img" ] || fail "Missing boot.img"
[ "$(wc -c < "$backup/boot.img" | tr -d '[:space:]')" = 100663296 ] || fail "Wrong boot.img size"
[ "$(image_sha256 "$backup/boot.img")" = 66b9746b31ead824ee148dec81eebe683b12e9171aee9e8f7624616057c58985 ] || fail "Wrong boot.img hash"
[ -b /dev/block/by-name/boot ] || fail "Missing boot block device"
[ "$(blockdev --getsize64 /dev/block/by-name/boot)" = 100663296 ] || fail "Wrong boot partition size"
[ -f "$backup/init_boot.img" ] || fail "Missing init_boot.img"
[ "$(wc -c < "$backup/init_boot.img" | tr -d '[:space:]')" = 8388608 ] || fail "Wrong init_boot.img size"
[ "$(image_sha256 "$backup/init_boot.img")" = 2971eb317c71d828af4d75532fa48b6f0b71ebda9ed117020e2dd7c5688dd4da ] || fail "Wrong init_boot.img hash"
[ -b /dev/block/by-name/init_boot ] || fail "Missing init_boot block device"
[ "$(blockdev --getsize64 /dev/block/by-name/init_boot)" = 8388608 ] || fail "Wrong init_boot partition size"
[ -f "$backup/vendor_boot.img" ] || fail "Missing vendor_boot.img"
[ "$(wc -c < "$backup/vendor_boot.img" | tr -d '[:space:]')" = 100663296 ] || fail "Wrong vendor_boot.img size"
[ "$(image_sha256 "$backup/vendor_boot.img")" = 5931bd19033555d27c093b9a14bd74a4f4c23315eb0dc0d6cdebe1a1a4a06ab2 ] || fail "Wrong vendor_boot.img hash"
[ -b /dev/block/by-name/vendor_boot ] || fail "Missing vendor_boot block device"
[ "$(blockdev --getsize64 /dev/block/by-name/vendor_boot)" = 100663296 ] || fail "Wrong vendor_boot partition size"
[ -f "$backup/dtbo.img" ] || fail "Missing dtbo.img"
[ "$(wc -c < "$backup/dtbo.img" | tr -d '[:space:]')" = 16777216 ] || fail "Wrong dtbo.img size"
[ "$(image_sha256 "$backup/dtbo.img")" = ebf3ec4a1418fc2510671f32026d38932360c9cb6c5f1007e9783a115239ec7b ] || fail "Wrong dtbo.img hash"
[ -b /dev/block/by-name/dtbo ] || fail "Missing dtbo block device"
[ "$(blockdev --getsize64 /dev/block/by-name/dtbo)" = 16777216 ] || fail "Wrong dtbo partition size"
recovery_before=$(image_sha256 /dev/block/by-name/recovery)
vbmeta_before=$(image_sha256 /dev/block/by-name/vbmeta)
echo "All four backups and target sizes verified."
[ "$mode" = --restore ] || { echo "Check complete; no partitions written."; exit 0; }
trap 'echo "Restore interrupted or failed. Keep TWRP open and rerun --restore after fixing the error." >&2' HUP INT TERM
echo "Restoring boot..."
dd if="$backup/boot.img" of=/dev/block/by-name/boot bs=1048576 || fail "Write failed: boot; keep TWRP open"
sync
[ "$(image_sha256 /dev/block/by-name/boot)" = 66b9746b31ead824ee148dec81eebe683b12e9171aee9e8f7624616057c58985 ] || fail "Readback mismatch: boot; keep TWRP open"
echo "Verified boot: 66b9746b31ead824ee148dec81eebe683b12e9171aee9e8f7624616057c58985"
echo "Restoring init_boot..."
dd if="$backup/init_boot.img" of=/dev/block/by-name/init_boot bs=1048576 || fail "Write failed: init_boot; keep TWRP open"
sync
[ "$(image_sha256 /dev/block/by-name/init_boot)" = 2971eb317c71d828af4d75532fa48b6f0b71ebda9ed117020e2dd7c5688dd4da ] || fail "Readback mismatch: init_boot; keep TWRP open"
echo "Verified init_boot: 2971eb317c71d828af4d75532fa48b6f0b71ebda9ed117020e2dd7c5688dd4da"
echo "Restoring vendor_boot..."
dd if="$backup/vendor_boot.img" of=/dev/block/by-name/vendor_boot bs=1048576 || fail "Write failed: vendor_boot; keep TWRP open"
sync
[ "$(image_sha256 /dev/block/by-name/vendor_boot)" = 5931bd19033555d27c093b9a14bd74a4f4c23315eb0dc0d6cdebe1a1a4a06ab2 ] || fail "Readback mismatch: vendor_boot; keep TWRP open"
echo "Verified vendor_boot: 5931bd19033555d27c093b9a14bd74a4f4c23315eb0dc0d6cdebe1a1a4a06ab2"
echo "Restoring dtbo..."
dd if="$backup/dtbo.img" of=/dev/block/by-name/dtbo bs=1048576 || fail "Write failed: dtbo; keep TWRP open"
sync
[ "$(image_sha256 /dev/block/by-name/dtbo)" = ebf3ec4a1418fc2510671f32026d38932360c9cb6c5f1007e9783a115239ec7b ] || fail "Readback mismatch: dtbo; keep TWRP open"
echo "Verified dtbo: ebf3ec4a1418fc2510671f32026d38932360c9cb6c5f1007e9783a115239ec7b"
[ "$(image_sha256 /dev/block/by-name/recovery)" = "$recovery_before" ] || fail "Recovery changed"
[ "$(image_sha256 /dev/block/by-name/vbmeta)" = "$vbmeta_before" ] || fail "Vbmeta changed"
echo "RESTORED: boot init_boot vendor_boot dtbo. Recovery/vbmeta unchanged. No reboot requested."
