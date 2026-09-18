# SM-X710 Boot Test - entry-marker-20260918T162702Z

## 测试目标

在确认 configfs、USB gadget 与 platform device 均正常出现后，判断 `a600000.usb` 为什么没有绑定 `dwc3-qcom`，并通过 sysfs 手动 bind 获取 driver-core 返回状态。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T162702Z/`

## 自动分类

`USB_GADGET_CONFIGURED+UDC_BIND_TIMEOUT+USER_RESET`

pstore 文件数为 0。最终 reset reason 为人工 7 秒复位。

## 已确认正常的路径

本轮再次确认：

- Linux 7.2-rc3 正常进入；
- `mmu_enabled_at_boot=0x0`；
- 全部 initcall 完成；
- `kernel_execve("/init")` 返回 0；
- devtmpfs、procfs、sysfs、devpts、tmpfs 均正常挂载；
- configfs 存在并成功挂载到 `/sys/kernel/config`；
- USB gadget configfs 配置成功。

devpts 的上一轮脚本问题也已修复，本轮明确出现：

`mount devpts success target=/dev/pts`

## DWC3 platform device

本轮首次明确确认 `a600000.usb` platform device 实际存在，并且：

- `status=okay`
- `driver=<none>`
- modalias 匹配 `qcom,sm8550-dwc3` / `qcom,snps-dwc3`
- OF compatible 为 `qcom,sm8550-dwc3,qcom,snps-dwc3`

因此已排除“DT 节点没有创建 platform device”和“compatible 完全不匹配”。

同时 `dwc3` 与 `dwc3-qcom` platform driver 均已注册，但 `bound=<none>`。

## 手动 bind 结果

向 `/sys/bus/platform/drivers/dwc3-qcom/bind` 写入 `a600000.usb` 后，用户态得到：

`Resource temporarily unavailable`

脚本记录：

`manual_dwc3_bind dev=a600000.usb rc=1 bound=<none>`

固定 Linux 7.2-rc3 driver core 中，`device_driver_attach()` 会把 `-EPROBE_DEFER` 专门转换为 `-EAGAIN` 返回给 sysfs。因此这里的 `Resource temporarily unavailable` 说明：

**`a600000.usb` 对 `dwc3-qcom` 的 probe 被 deferred。**

## Supplier links

本轮已经观察到 `a600000.usb` 存在多个 supplier device links，包括 clock controller、interconnect、USB PHY 和 interrupt controller等，但旧诊断只记录了 link 名，没有记录 supplier 自身是否已经绑定 driver。

因此当前还不能区分：

1. driver core 在进入 `dwc3_qcom_probe()` 前因为 supplier 未 ready 返回 `-EPROBE_DEFER`；
2. 已经进入 `dwc3_qcom_probe()` / `dwc3_core_probe()`，其中某项资源获取返回 `-EPROBE_DEFER`。

## 下一轮

保持 kernel Image 和 DTS 不变，只增强 initramfs：

- 读取 `a600000.usb/waiting_for_supplier`；
- 解析每个 `supplier:<bus>:<device>`；
- 记录 supplier 的 driver、waiting_for_supplier、OF status、modalias、compatible；
- 手动 bind 前后分别记录 `waiting_for_supplier`。

判据：

- `waiting_for_supplier=1`：deferred probe 明确发生在 driver-core supplier gating；
- `waiting_for_supplier=0` 且手动 bind 仍 EAGAIN：下一步给 `dwc3_qcom_probe()` / DWC3 core 加阶段 marker。
