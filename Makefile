.PHONY: all kernel initramfs tools bundle check clean
all: bundle
kernel:
	./scripts/build-kernel.sh
initramfs:
	python3 scripts/build-initramfs.py
tools:
	python3 scripts/stage-host-tools.py
bundle: kernel initramfs tools
	python3 scripts/build-boot-bundle.py
	python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
check:
	python3 scripts/check-patch-series.py
	bash -n scripts/build-kernel.sh
	sh -n initramfs/init
	sh -n scripts/twrp-restore-original.sh
	python3 -m unittest discover -s tests -v
clean:
	rm -rf work/kernel-build artifacts/kernel artifacts/initramfs artifacts/boot-bundle
