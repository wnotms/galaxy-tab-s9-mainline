# SM-X710 Boot Test - entry-marker-20260918T165902Z

## 测试目标

对 `entry-marker-20260918T165220Z/tested-bundle` 做严格同镜像重放，判断上一轮 `ABL_UEFI_END_NO_KERNEL_MARKER` 是否只是已知的偶发启动非确定性。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T165902Z/`

## 自动分类

`ABL_UEFI_END_NO_KERNEL_MARKER`

pstore 文件数为 0。

## 实际结果

第二次使用与 `entry-marker-20260918T165220Z` byte-for-byte 相同的 tested bundle，仍然只观察到：

- `BootMode = 0`
- `Requested Partition: boot`
- `Exit EBS / UEFI End`

但以下 mainline Linux 证据全部缺失：

- `G9E1301..G9E1305`
- `setup_arch` checkpoints
- `Linux version`
- initcall markers
- initramfs markers

因此，新 kernel/config bundle 已连续两次在 ABL ExitBootServices 之后没有留下 mainline Linux marker。

## USB diagnostics 污染

本轮本地 collector 尚未同步最新的 suppression 修复，因此摘要中仍出现大量 Samsung/TWRP recovery 的：

- `msm-dwc3`
- `a600000.ssusb`
- recovery task
- Android IRQ statistics

这些不是本轮 mainline Linux USB 证据，应忽略。

远端主分支已在提交 `1bd449fe2035de9e1d0faa831d95b976a16932c5` 中修正：没有 mainline `Linux version` marker 时不再生成 USB bring-up diagnostics。

## 解释

单次 `ABL_UEFI_END_NO_KERNEL_MARKER` 仍可能由此前观察到的启动非确定性解释，但同一 bundle 连续两次得到相同结果后，新 kernel/config 组合本身成为更强嫌疑。

不过，`CONFIG_ARM_PSCI_CPUIDLE_DOMAIN` 的功能语义发生在 Linux 已经进入之后；它本身不会直接解释在 `setup_arch` marker 之前停止。更合理的下一步是 A/B：

1. 先恢复原始四分区；
2. 不重新构建；
3. 重放最近一个已确认能进入 Linux 的 `entry-marker-20260918T163750Z/tested-bundle`；
4. 若旧 bundle 仍能进入 Linux，则把问题锁定为新 kernel Image/config 布局或其构建差异；
5. 若旧 bundle 同样连续停在 ExitBootServices 后，则设备/固件启动状态的非确定性仍然是主要变量。

只有旧工作 bundle 在当前状态下重新成功进入 Linux，才适合继续做新旧 kernel Image 的二进制/config A/B。
