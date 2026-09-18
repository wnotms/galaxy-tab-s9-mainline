# SM-X710 Boot Test - entry-marker-20260918T160309Z

## 测试目标

继续验证 initramfs 基础伪文件系统与 configfs 的真实挂载状态，避免把 configfs 失败后的 gadget/UDC 结果误判为 USB 控制器故障。

本轮刷入镜像沿用上一轮相同 kernel/vendor_boot/dtbo，仅 initramfs 发生变化：

| 分区 | SHA256 |
| --- | --- |
| `boot` | `3cabc411a3ee5630d082615a27f95c3a77a53c8540946e585019c3d09a38a234` |
| `init_boot` | `8aa0b5bc8062a1faa3edd25e80b525ae9edc929b20be220b0f34b2e7292ba2d4` |
| `vendor_boot` | `36d6813421bc0ce859f10b83d49e3969b6dc84ca9369f2d2086b8647d8378124` |
| `dtbo` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` |

本地完整资料：

`artifacts/boot-tests/entry-marker-20260918T160309Z/`

## 自动分类

`INITRAMFS_PSEUDO_FS_READY+CONFIGFS_MOUNT_FAILED+USER_RESET`

pstore 文件数为 0，未记录 `TZBSP_ERR_FATAL_NOC_ERROR`。最终 reset reason 为人工 7 秒复位。

## 已确认正常的路径

以下路径再次稳定通过：

- Linux 7.2-rc3 进入；
- `mmu_enabled_at_boot=0x0`；
- 全部 initcall 等级完成；
- `rdinit_access=0 path=/init`；
- `kernel_execve("/init")` 返回 0；
- initramfs `/init` 已开始运行；
- BusyBox 链接建立；
- 脚本执行到基础伪文件系统阶段。

## 本轮关键结果

configfs 内核 initcall：

`configfs_init returned 0`

USB 相关驱动注册 initcall：

- `ptn3222_driver_init returned 0`
- `snps_eusb2_hsphy_driver_init returned 0`
- `dwc3_driver_init returned 0`
- `dwc3_qcom_driver_init returned 0`
- `gadget_cfs_init returned 0`

用户态随后记录：

`GTS9WIFI: configfs mountpoint created by userspace`

`GTS9WIFI: configfs mount failed error=`

`GTS9WIFI: USB gadget skipped because configfs unavailable`

`GTS9WIFI: USB UDC test skipped because gadget setup failed`

因此本轮已经消除了之前的 gadget/UDC 假阳性：configfs 未成功挂载时，没有再继续声称 gadget 已配置或 UDC 已超时。

## 新的疑点

`configfs_init()` 返回成功时，固定 Linux 源码会通过 `sysfs_create_mount_point(kernel_kobj, "config")` 创建 configfs 的 sysfs mountpoint。

但本轮在用户态挂载 sysfs 后，脚本没有看到 `/sys/kernel/config`，而是通过 userspace fallback `mkdir` 创建了该目录。

这说明需要先验证更基础的一层：

- procfs 是否真的挂载成功；
- sysfs 是否真的挂载成功；
- devpts/tmpfs 是否真的挂载成功；
- `/proc/filesystems` 是否列出 configfs；
- `/proc/mounts` 中真实的 proc/sysfs 挂载表；
- configfs mount 的准确返回码；
- BusyBox mount 的完整 stdout/stderr。

此前的 `initramfs pseudo filesystems ready` 是在多个 mount 命令后无条件打印的，因此它不能单独证明这些文件系统全部成功挂载。

## 下一轮修改

下一轮 initramfs 已改为：

1. 对 devtmpfs/proc/sysfs/devpts/run-tmpfs/tmp-tmpfs 逐项执行带返回值检查的 mount；
2. 每项记录 success 或 `rc + stderr`；
3. 只有全部基础挂载成功才输出 `initramfs pseudo filesystems ready`；
4. 记录 `/proc/filesystems` 中 proc/sysfs/configfs/devtmpfs/tmpfs/debugfs 的存在性；
5. 记录 `/proc/mounts` 中 /proc、/sys、/dev、/run、/tmp 的真实条目；
6. 先尝试把 configfs 挂到 `/sys/kernel/config`；
7. 主路径失败时，再尝试挂到普通目录 `/config`；
8. 两处均失败才分类为 `CONFIGFS_MOUNT_FAILED`；
9. sysfs 本身失败则优先分类为 `SYSFS_MOUNT_FAILED`。

这样下一轮可以明确区分：

- sysfs 根本没有挂载；
- configfs 没有注册；
- `/sys/kernel/config` mountpoint/path 问题；
- configfs 在任意普通目录也无法挂载；
- configfs 成功后才进入真正的 gadget/UDC 诊断。
