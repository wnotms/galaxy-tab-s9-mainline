# Next test: S9 Ultra config control

## Goal

Determine whether the X710 pre-entry regression seen after enabling
`CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y` is specific to the minimal
`allnoconfig` environment.

The control uses the working Galaxy Tab S9 Ultra mainline ARM64 base config from
`agcarbajo/ubuntu-galaxy-tab-s9-ultra` at commit
`32273b0a410b3e73b20a3a2451e24260fb2a36bd`.  That project uses the same Linux 7.2-rc3 kernel commit as
this port.

The S9 Ultra base is merged with the X710 bring-up fragment, so the test keeps
the X710 DTS, diagnostic patches, KASLR-off policy, local version, built-in
USB/RPMh path and initramfs.  It does **not** use the X910 DTS.

## Why this test comes before deleting apps_rsc power-domains

The X710 stable/no-domain kernel boots with the current initramfs, while the
minimal kernel with PSCI cpuidle domains has twice failed before an observable
Linux marker.  The S9 Ultra is a hardware-near control where PSCI cpuidle
domains, DT idle genpd, RPMh, TCSR, SM8550 interconnect and DWC3 coexist in a
working 7.2-rc3 system.

If this profile boots, the next step is to bisect the S9 Ultra base config down
toward the minimal X710 config.  If it still fails before Linux entry, the next
test should focus on the X710 ABL/Image handoff rather than USB.

`/delete-property/ power-domains` on `&apps_rsc` remains a later diagnostic
bypass, not the preferred fix.

## Build

```bash
git pull --rebase origin main

python3 scripts/twrp-entry-marker-test.py build \
  --config-profile s9u-control
```

The build must print that the `s9u-control` profile passed config validation.

Check the resulting profile and key settings:

```bash
cat artifacts/kernel/config-profile.txt

grep -E 'CONFIG_(SUSPEND|PM_SLEEP|PM_GENERIC_DOMAINS_SLEEP|CPU_PM|CPU_IDLE_MULTIPLE_DRIVERS|DT_IDLE_STATES|DT_IDLE_GENPD|ARM_PSCI_CPUIDLE_DOMAIN|INTERCONNECT_QCOM_(BCM_VOTER|RPMH|SM8550))=' \
  artifacts/kernel/config
```

Expected profile:

```text
s9u-control
```

Verify the bundle:

```bash
python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
```

## Flash and collect

Only after the build and verification pass:

```bash
python3 scripts/twrp-entry-marker-test.py flash
```

After observation, return to TWRP and collect:

```bash
python3 scripts/twrp-entry-marker-test.py collect
```

Then restore:

```bash
python3 scripts/twrp-entry-marker-test.py restore
```

## Interpretation

### A. Linux enters

This shows that `ARM_PSCI_CPUIDLE_DOMAIN` itself is not sufficient to cause
the X710 failure.  Compare the generated S9U-control config against the minimal
domain-enabled config and bisect the supporting options.

Primary runtime checks then become:

```text
17a00000.rsc
1fc0000.clock-controller
1600000.interconnect
16e0000.interconnect
24100000.interconnect
interconnect-1
88e3000.phy
a600000.usb
```

### B. ExitBootServices with no Linux marker

Do not change USB.  The result points back to the X710 ABL/kernel-image handoff
or another pre-entry property of the larger/domain-enabled Image.  Preserve the
tested bundle for byte-identical replay.

### C. Linux enters but suppliers remain blocked

The config/entry problem and the RPMh supplier problem are separate.  At that
point the bounded `&apps_rsc { /delete-property/ power-domains; };` experiment
becomes useful to prove whether `cluster_pd` is the remaining blocker.
