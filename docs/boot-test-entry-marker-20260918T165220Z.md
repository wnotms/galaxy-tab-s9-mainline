# SM-X710 Boot Test - entry-marker-20260918T165220Z

## 测试目标

验证显式启用 `CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y` / `CONFIG_DT_IDLE_GENPD=y` 后，RPMh RSC → TCSR → eUSB2 PHY → DWC3 deferred-probe 链是否恢复。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T165220Z/`

精确刷入镜像 SHA256 由本地 `TEST-RECORD.md` / `test-record.json` 保存；本次 collect 输出未包含四镜像哈希，因此仓库记录不猜测哈希。

## 自动分类

`ABL_UEFI_END_NO_KERNEL_MARKER`

pstore 文件数为 0。

## 本轮实际结果

本轮没有任何 mainline Linux 执行 marker：

- `G9E1301..G9E1305`：全部 0；
- `setup_arch` checkpoints：全部 0；
- `Linux version`：0；
- initcall / initramfs / USB marker：全部 0。

与此同时 ABL/XBL 路径明确存在：

- `BootMode = 0`；
- `Requested Partition: boot`；
- `Exit EBS / UEFI End`。

因此本轮只能够确认：

**ABL 已沿正常 boot 路径加载测试镜像并完成 ExitBootServices，但没有留下 mainline Linux 进入证据。**

本轮尚未运行到 PSCI cpuidle domain、RPMh RSC、TCSR、eUSB2 PHY 或 DWC3 的 probe 阶段，所以不能据此判断上一提交的配置修复是否有效。

## USB diagnostics 污染说明

旧 collector 在没有 `Linux version` marker 时仍会对整个 `/proc/last_kmsg` 搜索 USB 关键字，因此摘要中出现了大量：

- Android/Samsung `msm-dwc3`；
- `a600000.ssusb`；
- recovery 进程；
- Android 内核 IRQ 统计。

这些行不是本轮 mainline USB bring-up 证据，应全部忽略。

collector 已调整为：只有检测到本轮 mainline `Linux version` 后，才从该行开始生成 USB 专项诊断；没有 mainline marker 时 USB diagnostics 直接抑制。

## 解释

该设备此前已经出现过明显的启动可复现性波动：完全相同的已归档四分区镜像曾经一次进入 Linux、另一次在 ABL ExitBootServices 后没有任何 Linux marker。

而 `ARM_PSCI_CPUIDLE_DOMAIN` 的功能路径位于 Linux 已经进入后的 cpuidle/genpd 初始化阶段；它本身不能直接解释“连 setup_arch marker 都没有”的语义执行路径。虽然配置变化会改变最终 Image 二进制布局，但当前单次结果不足以把 pre-entry 失败归因于该选项。

## 下一步

**不重新构建、不修改 DTS、不修改 kernel config、不恢复原分区，直接原样重放同一个 tested bundle 一次。**

在当前 TWRP 中执行：

`python3 scripts/twrp-entry-marker-test.py flash --force-new-run`

这会创建新的 run directory，但使用当前 `artifacts/boot-bundle` 原样再次刷入/启动，从而保留本轮记录并进行严格同镜像复现。

若第二次相同 bundle 能重新进入 Linux，再检查：

`17a00000.rsc -> 1fc0000.clock-controller -> 88e3000.phy -> a600000.usb`

是否从 `-517` 转为成功。

若相同 bundle 连续第二次仍停在 `ABL_UEFI_END_NO_KERNEL_MARKER`，再进行上一工作 bundle 与新 kernel Image 的 A/B 对比，不应提前继续修改 RPMh/USB 代码。
