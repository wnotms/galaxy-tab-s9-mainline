# SM-X710 Boot Test - entry-marker-20260918T153621Z

## 测试目标

在已经确认 Linux 与 initramfs 用户态可正常运行的基础上，继续区分 USB gadget configfs 配置、UDC 出现、UDC 绑定、usb0 本地配置和主机枚举阶段。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T153621Z/`

本轮精确镜像 SHA256 已由本地 `TEST-RECORD.md` / `test-record.json` 保存；用户提供的 collect 输出未包含本轮四镜像哈希，因此仓库记录不重复猜测。

## 自动分类

原脚本输出：

`USB_GADGET_CONFIGURED+UDC_BIND_TIMEOUT+USER_RESET`

pstore 文件数为 0，未记录 `TZBSP_ERR_FATAL_NOC_ERROR`。最终 reset reason 是人工 7 秒复位。

## 已确认正常的启动路径

以下路径继续稳定通过：

- Linux 7.2-rc3 进入；
- `mmu_enabled_at_boot=0x0`；
- 全部 initcall 等级完成；
- `rdinit_access=0 path=/init`；
- `kernel_execve("/init")` 返回 0；
- initramfs `/init` 已进入；
- BusyBox 链接建立；
- devtmpfs、proc、sysfs、devpts、tmpfs 基础挂载完成。

因此本轮再次确认：内核和 initramfs 用户态本身不是当前阻塞点。

## USB 关键日志

最关键的用户态 marker 为：

`GTS9WIFI: configfs mount failed`

随后旧脚本仍然无条件输出：

`GTS9WIFI: USB gadget configured`

并继续进入 UDC 等待，最终得到：

`GTS9WIFI: UDC no controller yet`

`GTS9WIFI: UDC bind timeout`

这里后两条不能作为“UDC 驱动一定没有 probe”的可靠结论，因为 USB gadget configfs 在更早阶段已经失败。

另外，从时间戳看：

- `UDC no controller yet`：约 0.051452 s
- `UDC bind timeout`：约 0.071661 s

两者只相差约 20 ms，而旧脚本设计为最多执行 30 次 `sleep 1`。因此旧脚本的等待也没有形成预期的约 30 秒窗口，`UDC_BIND_TIMEOUT` 不能按正常超时理解。

## 驱动 initcall

日志中以下 initcall 均返回 0：

- `ptn3222_driver_init`
- `snps_eusb2_hsphy_driver_init`
- `dwc3_driver_init`
- `dwc3_qcom_driver_init`
- `gadget_cfs_init`

这些结果只证明驱动/子系统注册过程返回成功，不证明对应 platform device 已经完成 probe 或已经注册 UDC。

DTS 中当前 USB 路径为：

- PTN3222 repeater：enabled；
- SM8550 eUSB2 HS PHY：enabled；
- `usb_1`：`dr_mode = "peripheral"`；
- `maximum-speed = "high-speed"`；
- `usb_1`：enabled。

## 根因分析

当前 initramfs 脚本在挂载 sysfs 前执行：

`mkdir -p /sys/kernel/config`

随后：

`mount -t sysfs sysfs /sys`

会用新的 sysfs 挂载覆盖原先的 `/sys` 目录树，因此之前创建的 `/sys/kernel/config` mountpoint 被遮蔽。紧接着执行：

`mount -t configfs configfs /sys/kernel/config`

存在 mountpoint 不再可见而失败的风险，与本轮实际的 `configfs mount failed` 完全一致。

## 后续修改

下一轮脚本已经调整为：

1. 先挂载 sysfs；
2. 再创建 `/sys/kernel/config`；
3. 捕获并记录 configfs mount stderr；
4. configfs 失败时完全跳过 gadget/UDC 测试，避免假阳性；
5. gadget configfs 配置只有整组命令成功后才输出 `USB gadget configured`；
6. 等待循环显式使用 `/bin/busybox sleep 1`；
7. 真正无 UDC 时记录 `/sys/class/udc`；
8. 尝试记录 `devices_deferred`；
9. 记录 dwc3 / dwc3-qcom platform driver 实际绑定的设备；
10. 分类器优先报告 `CONFIGFS_MOUNT_FAILED`，不再把其误分类成 UDC 超时。

下一轮才可以可靠判断 configfs 修复后是否真正出现 UDC，以及 DWC3 platform device 是否完成 probe。
