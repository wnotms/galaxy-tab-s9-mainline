# SM-X710 第六次启动测试

日期：2026-09-18；SM-X710，revision 6，启动固件 X710ZCU5CYH4。基于提交 `75c4c46`，新增第七个补丁 `record-sec-log-setup-arch-checkpoints.patch`。

## 改动与主机验证

在 ARM64 setup_arch 的 `after_fdt`、`after_memblock`、`after_paging`、`after_unflatten` 和 `after_bootmem` 五处直接记录标记。函数首先校验 flat DT 的 S9 compatible 及 sec-log 精确 reg，然后临时映射日志首个 4 KiB，写入标记、清理正文到 PoC、更新索引并清理头部，最后解除映射。只有第一个标记初始化本次环形缓冲；console_initcall 接管时保留早期数据及索引。输入 DTB、initramfs、保留区布局和 cmdline 不变。

CONFIG 关闭时调用为空函数；启用后也不能观测 FDT 检查、早期映射及地址检查之前的故障，标记缺失不能单独定位停止点。PoC 清理仍不保证强制复位后的保留。

七个补丁在干净固定源码上按顺序应用通过，文件与编译源码逐字节一致。`make bundle`、四镜像检查和 `make check` 通过；setup.o 反汇编有五处 early_checkpoint 调用重定位，完整 console 初始化仍位于 console initcall 区间。

镜像 SHA256：

```text
240952aad24e976a1450e397895ebf450402cd6c84da34b5bfce0c7f648edd38  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c23fff2ebadab9ecd9e8eef73587e39d7bed48694f9f7a703dbe1a0c6ec5bcbc  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机状态

TWRP 预检通过：身份、解锁状态、AVB flags 2、当前原分区及恢复备份哈希匹配。四个镜像已写入并逐个回读通过，recovery / vbmeta 保持不变，然后请求正常重启。

Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB。当前等待返回 TWRP，回收本次早期标记日志，再恢复原启动分区；四个启动分区仍为第六版实验镜像。

完整本地归档位于 `artifacts/boot-tests/sixth-sm-x710/`；实际测试镜像在 `tested-bundle/`，日志和二进制被 Git 忽略。
