# SM-X710 Boot Test - entry-marker-20260918T163750Z

## 测试目标

继续定位 `a600000.usb` 对 `dwc3-qcom` 的 deferred bind 来源，记录直接 supplier 的 driver 与 waiting-for-supplier 状态。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T163750Z/`

## 自动分类

`USB_GADGET_CONFIGURED+DWC3_BIND_DEFERRED+UDC_BIND_TIMEOUT+USER_RESET`

pstore 文件数为 0。最终 reset reason 为人工 7 秒复位。

## 已确认正常的启动路径

本轮继续确认 Linux、全部 initcall、`kernel_execve("/init")`、initramfs、devtmpfs/proc/sysfs/devpts/tmpfs、configfs 与 USB gadget 配置均正常。

configfs 成功后 USB gadget 已创建，但约 30 秒后：

`UDC class entries=<empty>`

`dwc3` 与 `dwc3-qcom` 仍然均为 `bound=<none>`。

## DWC3 bind 状态

`a600000.usb` platform device 存在，`status=okay`，compatible 为 `qcom,sm8550-dwc3,qcom,snps-dwc3`，但 `driver=<none>`。

手动向 `dwc3-qcom/bind` 写入 `a600000.usb` 前后：

`waiting_for_supplier=0`

bind 仍返回：

`Resource temporarily unavailable`

固定 Linux driver core 会把 `-EPROBE_DEFER` 转换为 sysfs bind 可见的 `-EAGAIN`，因此 bind 仍处于 deferred 状态。

需要注意：设备的 `waiting_for_supplier` 属性只检查 fwnode supplier，不代表所有 managed device-link 都已经 AVAILABLE，所以这里的 0 不能排除 driver-core supplier gating。

## 关键 supplier

直接 supplier 中已经观察到：

- `1fc0000.clock-controller`：`driver=<none>`、`waiting_for_supplier=1`
- `88e3000.phy`：`driver=<none>`、`waiting_for_supplier=1`，compatible 为 SM8550 SNPS eUSB2 PHY
- `24100000.interconnect`：未绑定但 `waiting_for_supplier=0`
- `b220000.interrupt-controller`：已绑定 `qcom_pdc`
- `interconnect-1`：未绑定但 `waiting_for_supplier=0`

固定 SM8550 DTSI 的依赖链显示：

`a600000.usb -> 88e3000.phy -> 1fc0000 TCSR -> rpmhcc`

并且 `a600000.usb` 自身也直接使用 TCSR 提供的 USB3 CLKREF。

内核配置已经包含 `CONFIG_QCOM_CLK_RPMH=y`、`CONFIG_SM_TCSRCC_8550=y`、`CONFIG_PHY_SNPS_EUSB2=y` 和 `CONFIG_QCOM_COMMAND_DB=y`，因此不是简单的驱动配置缺失。

## 下一轮

保持 kernel Image/DTS 不变，增强 initramfs 诊断：

1. 读取每条 supplier device-link 的真实 `status`；
2. 同时记录 `auto_remove_on`、`runtime_pm` 与 `sync_state_only`；
3. 沿 supplier 链递归追踪最多 3 层；
4. 完整打印最多 50 条 `platform_supplier` / `device_link` 记录；
5. USB 专项日志增加 RPMh/TCSR 关键字。

重点判据：

- direct link 为 `dormant/not tracked`：supplier 尚未 AVAILABLE，优先沿递归链找最上游阻塞点；
- TCSR 的上游若指向未 ready 的 RPMh clock controller，则下一步集中到 `apps_rsc/rpmhcc`；
- 如果所有 direct device-link 都为 `available`，但手动 bind 仍 EAGAIN，再给 `dwc3_qcom_probe()` / `dwc3_core_probe()` 加内核阶段 marker。


## 后续 grep 分析：RPMh RSC 为更上游阻塞点

对本轮 `last_kmsg.txt` 做 probe 关键字 grep 后，确认 deferred-probe 链条比 DWC3 更上游：

- `17a00000.rsc`（RPMh RSC）反复返回 `-517`；
- `1fc0000.clock-controller`（TCSR）随后反复返回 `-517`；
- `88e3000.phy`（SM8550 eUSB2 PHY）反复返回 `-517`；
- `a600000.usb` 最终反复返回 `-517`。

固定 SM8550 DTSI 中 `apps_rsc` 声明：

`power-domains = <&cluster_pd>`

而 `cluster_pd` 是 PSCI hierarchical cpuidle domain provider 提供的 genpd。

仓库的 kernel build 使用：

`KCONFIG_ALLCONFIG=kernel/config/gts9wifi-bringup.config allnoconfig`

当前 fragment 虽然启用了 `CONFIG_ARM_PSCI_CPUIDLE=y`、`CONFIG_PM_GENERIC_DOMAINS_OF=y`，但没有显式启用 `CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y`。在 allnoconfig 模式下，这会使 PSCI domain 支持有被裁掉的风险，从而导致 `cluster_pd` provider 缺失，解释 RPMh RSC 的持续 deferred probe。

下一轮改为显式启用：

`CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y`

该选项会选择 `CONFIG_DT_IDLE_GENPD`。生成后的最终 `.config` 还会由 `scripts/check-config.py` 同时验证：

- `CONFIG_ARM_PSCI_CPUIDLE=y`
- `CONFIG_ARM_PSCI_CPUIDLE_DOMAIN=y`
- `CONFIG_DT_IDLE_GENPD=y`
- `CONFIG_PM_GENERIC_DOMAINS_OF=y`

如果修复有效，预期链条应依次出现成功 probe：

`17a00000.rsc -> rpmhcc -> 1fc0000 TCSR -> 88e3000 eUSB2 PHY -> a600000 DWC3 -> UDC`
