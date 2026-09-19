# Next test: fixed boot geometry control

## Reason

Do **not** flash the full S9 Ultra config-control bundle as the next A/B test.

That profile produced a raw Image of 137026048 bytes and a gzip stream of
47588516 bytes, while the failed minimal PSCI-domain bundle used an 8399360-byte
raw Image and a 3499096-byte gzip stream.  Although the 96 MiB boot partition
still validates statically, this changes the ABL load/decompression geometry far
too much for a clean pre-entry comparison.

The cleaner control keeps the byte-identical known-working raw kernel
(`a25fde1f...`) but pads its **gzip header** with the standard RFC 1952
FEXTRA field so that the appended DTB starts at exactly the same offset as the
failed `165220Z` PSCI-domain bundle.

This changes no decompressed kernel bytes.

## Inputs

Known-working raw kernel SHA-256:

```text
a25fde1f5a7407deaa4f7e93609500d2f612757cc97b22f1364c42cfee0f2008
```

Failed 165220Z gzip stream size:

```text
3499096
```

Its raw kernel size and ARM64 image_size field were already identical to the
known-working minimal kernel.  The appended DTB is also identical.

## Build the control

If the reproducible old kernel still exists:

```bash
sha256sum /tmp/gts9-old-kernel/arch/arm64/boot/Image
```

It must equal the known-working hash above.

Then:

```bash
rm -rf artifacts/boot-bundle-oldkernel-fixedgeom

python3 scripts/build-boot-bundle.py \
  --kernel /tmp/gts9-old-kernel/arch/arm64/boot/Image \
  --dtb artifacts/kernel/sm8550-samsung-gts9wifi.dtb \
  --initramfs artifacts/initramfs/initramfs.cpio.gz \
  --kernel-gzip-target-size 3499096 \
  --output artifacts/boot-bundle-oldkernel-fixedgeom

python3 scripts/verify-boot-bundle.py \
  artifacts/boot-bundle-oldkernel-fixedgeom
```

## Required comparison

```bash
python3 scripts/compare-boot-bundles.py \
  artifacts/boot-tests/entry-marker-20260918T165220Z/tested-bundle \
  artifacts/boot-bundle-oldkernel-fixedgeom
```

The important fields should now be identical:

```text
boot.arm64_image_size_field
boot.avb_original_size
boot.boot_kernel_field_size
boot.gzip_kernel_size
init_boot partition/payload
appended DTB
```

The expected meaningful differences are the raw kernel SHA-256 and therefore
the final boot partition SHA-256.

## Interpretation

### Old kernel + matched geometry boots

ABL accepts the larger gzip stream and the shifted appended-DTB offset.  That
rules out the 1867-byte stream-size/DTB-offset change as a sufficient cause of
the PSCI-domain failures.  The next investigation should target the changed
raw Image / very-early execution rather than USB.

### Old kernel + matched geometry does not boot

The result is not yet evidence against the raw kernel.  First suspect ABL gzip
parsing or sensitivity to the FEXTRA/header/DTB placement.  Restore immediately
and keep the ordinary known-working bundle as control.

This experiment is diagnostic only; FEXTRA padding is not intended for the
final boot format.
