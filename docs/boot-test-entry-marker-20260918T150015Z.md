# SM-X710 Boot Test - entry-marker-20260918T150015Z

## 测试目标

继续定位主线 Linux 在完成内核初始化后、进入 initramfs 用户态之前的停滞位置。本轮在 `start_kernel`、`rest_init`、`kernel_init`、`kernel_init_freeable`、initcall 各等级以及 `rdinit=/init` 交接前加入 persistent-console 检查点，并强制启用 `initcall_debug`。

观察窗口按 entry-marker 测试默认值执行；启动后未自动恢复到可交互用户态，最终通过 7 秒按键复位进入 TWRP 采集日志。

## 实际刷入镜像

| 分区 | SHA256 |
| --- | --- |
| `boot` | `215dc353100bf3a95cfd6f5927f5f39d2b0769816f459ab890942a4949e100e6` |
| `init_boot` | `4973e6b0c1fe1502a79931597be996dd50d8f71b09f8cc337462a1391826e637` |
| `vendor_boot` | `36d6813421bc0ce859f10b83d49e3969b6dc84ca9369f2d2086b8647d8378124` |
| `dtbo` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |

本地 tested bundle 与完整日志位于：

`artifacts/boot-tests/entry-marker-20260918T150015Z/`

## 关键结果

自动分类结果：

`KERNEL_BEFORE_RDINIT_EXEC+USER_RESET`

pstore 文件数为 0；未记录到 `TZBSP_ERR_FATAL_NOC_ERROR`。最终 reset reason 为：

`collect_rr_data : upload_cause = User press reset keys for 7 sec`

主线 Linux 已明确执行，日志包含：

`Linux version 7.2.0-rc3-gts9wifi-bringup`

ARM64 入口状态记录为：

`GTS9WIFI: start_kernel after_console_init mmu_enabled_at_boot=0x0 initcall_debug=1`

因此本轮确认固件以 MMU-off 状态交接 Linux。

## 已确认执行路径

以下检查点全部出现：

- `setup_arch after_fdt`
- `setup_arch after_memblock`
- `setup_arch after_paging`
- `setup_arch after_unflatten`
- `setup_arch after_bootmem`
- `console_initcall reached`
- `start_kernel before_rest_init`
- `rest_init enter`
- PID 1 创建成功
- kthreadd 创建并 ready
- `kernel_init enter`
- `kernel_init_freeable enter`
- pre-SMP initcalls 完成
- SMP 初始化完成
- `do_basic_setup()` 完成
- 全部普通 initcall 等级完成
- `wait_for_initramfs()` 完成
- `console_on_rootfs()` 完成
- `rdinit_access=0 path=/init`
- `kernel_init_freeable done`
- `kernel_init kernel_init_freeable_done`
- `kernel_init before_rdinit_exec path=/init`

全部 initcall 等级都正常走到结束，其中最后一级为：

`GTS9WIFI: initcall level late end`

最后几项 initcall 也有成对的 calling/returned，包括：

`genpd_power_off_unused`

`regulator_init_complete`

`of_platform_sync_state_init`

因此本轮没有证据表明某个 built-in initcall 挂死。

## 未观察到

本轮没有出现：

- `kernel_init rdinit_exec_failed`
- `GTS9WIFI: initramfs init entered`
- `initramfs ready; USB NCM address ...`
- Fatal NoC

需要注意，本轮 initramfs 中的用户态 marker 位于 `mount -t devtmpfs devtmpfs /dev` 之后，而初始 cpio 没有预置 `/dev/kmsg`。因此“没有 initramfs marker”不能单独证明 `/init` 没有开始执行。

## 结论

本轮已将停滞范围从“Linux 内核初始化阶段”缩小到 `kernel_execve("/init")` 与 initramfs 最早期用户态之间。

可以排除本轮普通 initcall 未返回作为直接原因；`/init` 已确认存在且 `init_eaccess()` 返回 0。下一轮需要同时记录 `kernel_execve("/init")` 的返回值，并在 initramfs cpio 中预置 `/dev/kmsg`，把用户态 marker 移到 `/init` 的第一条实际命令。

针对这一结论，后续诊断已经加入：

- `kernel_init after_rdinit_exec ret=...`
- `kernel_init rdinit_exec_success`
- cpio 内置 `/dev/kmsg`
- `initramfs init entered`
- `initramfs busybox links ready`
- `initramfs devtmpfs mounted`
- `initramfs pseudo filesystems ready`

这样下一轮可以直接区分 exec 失败、exec 成功但未进入用户态、以及 initramfs 具体卡在哪一条早期初始化路径。
