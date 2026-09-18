# SM-X710 Boot Test - entry-marker-20260918T170424Z

## 测试目标

A/B 验证：在新 PSCI-domain kernel bundle 连续两次停在 `ABL_UEFI_END_NO_KERNEL_MARKER` 后，重新刷入最近一个已确认能进入 Linux 的旧工作 bundle（`entry-marker-20260918T163750Z/tested-bundle`），判断当前设备状态是否仍可启动 mainline。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T170424Z/`

## 自动分类

`USB_GADGET_CONFIGURED+DWC3_BIND_DEFERRED+UDC_BIND_TIMEOUT+USER_RESET`

pstore 文件数为 0。

## A/B 结论

旧工作 bundle 在当前设备状态下重新成功进入 mainline Linux：

- `setup_arch` 全部 checkpoints 出现；
- `mmu_enabled_at_boot=0x0`；
- 全部 initcall 等级完成；
- `kernel_execve("/init")` 返回 0；
- initramfs、devtmpfs、procfs、sysfs、devpts、configfs 均成功；
- USB gadget configfs 配置成功。

随后仍复现旧问题：

- `/sys/class/udc` 为空；
- `dwc3` / `dwc3-qcom` 均未绑定；
- 手动 bind `a600000.usb` 返回 EAGAIN/EPROBE_DEFER；
- TCSR 与 eUSB2 PHY supplier 仍未绑定。

因此当前设备/固件状态并没有普遍失去启动 mainline 的能力。

结合新 bundle `entry-marker-20260918T165220Z` 与其严格重放 `165902Z` 连续两次都停在 ExitBootServices 后无任何 Linux marker，当前更强的嫌疑已经转向：

**新 kernel/config 生成的 boot payload 本身。**

这还不能证明 `CONFIG_ARM_PSCI_CPUIDLE_DOMAIN` 的运行时逻辑直接导致 pre-entry 失败，因为该功能路径发生在 Linux 已进入后的 initcall/genpd 阶段；需要先比较旧/新实际 kernel payload 的大小、header 与打包内容。

## 下一步

新增 `scripts/compare-boot-bundles.py`，用于直接比较两个 archived tested bundle：

- boot partition SHA256；
- AVB original image size；
- Android v4 kernel field size；
- gzip kernel stream size；
- raw ARM64 Image size/SHA256；
- ARM64 `text_offset` / `image_size` / `flags`；
- appended DTB size/SHA256；
- init_boot ramdisk size/SHA256；
- manifest input hashes。

推荐比较：

`entry-marker-20260918T163750Z/tested-bundle`

与：

`entry-marker-20260918T165220Z/tested-bundle`

若 DTB 完全一致而 raw kernel 仅因 PSCI domain 配置变化，则下一轮做“当前 initramfs + 回退 PSCI domain kernel”的单变量 A/B。

若 kernel field / ARM64 header / DTB 或其他 boot payload 也发生意外变化，则先修打包/布局差异。
