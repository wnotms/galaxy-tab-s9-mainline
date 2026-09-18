# SM-X710 Boot Test - entry-marker-20260918T152235Z

## 测试目标

确认 Linux 完成全部 initcall 后能否成功执行 `rdinit=/init`，并确认 initramfs 用户态可以运行到 USB NCM 初始化脚本末尾。

本轮使用的诊断镜像 SHA256：

| 分区 | SHA256 |
| --- | --- |
| `boot` | `3cabc411a3ee5630d082615a27f95c3a77a53c8540946e585019c3d09a38a234` |
| `init_boot` | `b0d6ec652d86e00431edae3111639524b95bdd8b26f417dcb62ddb8e3808ccd7` |
| `vendor_boot` | `36d6813421bc0ce859f10b83d49e3969b6dc84ca9369f2d2086b8647d8378124` |
| `dtbo` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T152235Z/`

## 自动分类

`INITRAMFS_USB_READY+USER_RESET`

pstore 文件数：0。

未记录到 `TZBSP_ERR_FATAL_NOC_ERROR`。最终 reset reason 为人工 7 秒复位：

`collect_rr_data : upload_cause = User press reset keys for 7 sec`

## 内核执行结果

主线 Linux 正常进入，且 ARM64 入口状态为：

`GTS9WIFI: start_kernel after_console_init mmu_enabled_at_boot=0x0 initcall_debug=1`

本轮确认固件以 MMU-off 状态交接 Linux。

全部 initcall 正常执行到 late 级结束，最后记录的 initcall 包括：

- `genpd_power_off_unused` returned 0
- `regulator_init_complete` returned 0
- `of_platform_sync_state_init` returned 0

因此没有证据表明 built-in initcall 挂死。

## rdinit 交接结果

`/init` 可访问：

`GTS9WIFI: kernel_init_freeable rdinit_access=0 path=/init`

随后内核实际调用并成功完成：

`GTS9WIFI: kernel_init before_rdinit_exec path=/init`

`GTS9WIFI: kernel_init after_rdinit_exec ret=0`

`GTS9WIFI: kernel_init rdinit_exec_success`

因此可以确认 `kernel_execve("/init")` 成功，PID 1 已进入 initramfs 用户态。

## initramfs 用户态结果

以下 marker 均出现：

- `GTS9WIFI: initramfs init entered`
- `GTS9WIFI: initramfs busybox links ready`
- `GTS9WIFI: initramfs devtmpfs mounted`
- `GTS9WIFI: initramfs pseudo filesystems ready`
- `initramfs ready; USB NCM address 172.16.71.1, telnet port 23`

最后一条出现在约 91 ms。

## 重要限制

当前 `initramfs ready` 不是“USB 已成功枚举”的充分证据。现有脚本在最多等待 30 秒 UDC 后，无论是否真正成功写入 `$G/UDC`、是否出现 `usb0`、以及主机是否完成 USB 枚举，都会继续执行 `ifconfig`、`telnetd` 并打印 ready marker。

因此本轮真正确认的是：

**Linux 内核与 initramfs 用户态启动路径已经成功；剩余主要问题已经转移到 USB gadget / UDC / 主机枚举链路。**

## 下一步

下一轮应分别记录：

1. `/sys/class/udc/*` 是否出现控制器；
2. configfs gadget 写入 `UDC` 是否成功；
3. 实际绑定的 UDC 名称；
4. `usb0` 是否出现并成功配置；
5. `/sys/class/udc/<name>/state` 的状态变化；
6. 是否达到 `configured`，以确认主机完成枚举。

这样可以区分设备端 DWC3/UDC 没有准备好、gadget bind 失败，以及设备端已绑定但 Windows 主机没有完成枚举。
