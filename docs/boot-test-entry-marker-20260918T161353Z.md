# SM-X710 Boot Test - entry-marker-20260918T161353Z

## 测试目标

在修正基础伪文件系统和 configfs 诊断后，确认 USB gadget 能否正常建立，以及主线 SM8550 DWC3 控制器是否实际注册 UDC。

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T161353Z/`

精确刷入镜像 SHA256 由本地 `TEST-RECORD.md` / `test-record.json` 保存；本次 collect 输出未包含四镜像哈希，因此仓库记录不重复猜测。

## 自动分类

`USB_GADGET_CONFIGURED+UDC_BIND_TIMEOUT+USER_RESET`

pstore 文件数为 0，未记录 `TZBSP_ERR_FATAL_NOC_ERROR`。最终 reset reason 为人工 7 秒复位。

## 已确认正常的启动路径

以下路径继续稳定通过：

- Linux 7.2-rc3 进入；
- `mmu_enabled_at_boot=0x0`；
- 全部 initcall 等级完成；
- `rdinit_access=0 path=/init`；
- `kernel_execve("/init")` 返回 0；
- initramfs `/init` 正常执行。

## 基础文件系统结果

以下挂载明确成功：

- devtmpfs：`/dev`
- procfs：`/proc`
- sysfs：`/sys`
- tmpfs：`/run`
- tmpfs：`/tmp`

`/proc/mounts` 同样确认这些挂载真实存在。

`/proc/filesystems` 中明确包含：

- sysfs
- configfs
- devtmpfs
- tmpfs

debugfs 未编入/不可用。

devpts 本轮失败：

`mount: mounting devpts on /dev/pts failed: No such file or directory`

同时旧 `mount_checked()` 错误记录为 `rc=0`。这是诊断脚本 bug：`/dev/pts` 在挂 devtmpfs 前创建，随后被新的 `/dev` 覆盖；并且旧函数在失败的 `if` 之后读取 `$?`，没有保存真实 mount 返回码。该问题与当前 DWC3/UDC 主故障无直接证据关联，但下一轮已修复。

## configfs 结果

本轮已经完全排除上一轮的 configfs 假象：

`GTS9WIFI: configfs mountpoint present path=/sys/kernel/config`

`GTS9WIFI: configfs mounted path=/sys/kernel/config`

`none /sys/kernel/config configfs rw,relatime 0 0`

USB gadget configfs 创建同样成功：

`GTS9WIFI: USB gadget configured`

因此当前问题已经不在 configfs 或 gadget 描述符创建阶段。

## UDC / DWC3 关键结果

首次检查：

`GTS9WIFI: UDC no controller yet`

脚本随后进行了真实约 30 秒等待：

- 首次检查约 0.064735 s
- timeout 约 30.184743 s

最终：

`GTS9WIFI: UDC bind timeout`

`GTS9WIFI: UDC class entries=<empty>`

这次 timeout 是真实等待窗口，不是此前 20 ms 的脚本假超时。

platform driver 状态：

`GTS9WIFI: platform_driver dwc3 bound=<none>`

`GTS9WIFI: platform_driver dwc3-qcom bound=<none>`

因此可以确认：

**DWC3 与 QCOM DWC3 驱动均已注册，但当前没有任何 platform device 成功绑定到它们，也没有 UDC 注册。**

## 对固定 Linux DTSI 的核对

固定 Linux commit：

`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`

SM8550 主线 `usb_1` 是单节点 DWC3/QCOM glue 设计：

`usb@a600000`

compatible：

`"qcom,sm8550-dwc3", "qcom,snps-dwc3"`

主线 `dwc3-qcom` 驱动的 OF match 包含：

`"qcom,snps-dwc3"`

因此当前 DTS 中通过 `&usb_1 { status = "okay"; }` 启用该节点的方向是正确的；不存在还需要额外启用一个隐藏 `usb_1_dwc3` 子节点的问题。

## 下一步

下一轮保持 kernel/DTS 不变，先只改 initramfs，以减少变量。

新增诊断包括：

1. 枚举 `/sys/bus/platform/devices` 中与 `a600000` / USB / DWC3 相关的 platform device；
2. 记录每个设备的：
   - sysfs name
   - 当前 driver
   - modalias
   - OF compatible
   - OF status
   - supplier links
3. 如果 `a600000.usb` 存在但未绑定，向：
   `/sys/bus/platform/drivers/dwc3-qcom/bind`
   手动写入设备名一次；
4. 记录手动 bind 的真实返回码、stderr 和 bind 后 driver 状态；
5. 再观察 UDC 是否因此出现；
6. 修复 devpts 创建顺序；
7. 修复 `mount_checked()` 的真实返回码记录。

如果 platform device 根本不存在，问题转向 OF platform population / DT 节点状态。

如果 platform device 存在、modalias/compatible 正确，但手动 bind 返回错误，则下一步根据 errno 与内核日志定位 `dwc3_qcom_probe()` 的 reset/clock/IRQ/core/PHY/interconnect 阶段。
