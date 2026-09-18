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

Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB。随后检测到用户返回 TWRP，已保存持久日志再执行恢复。本次没有额外取得屏幕状态确认。

## 日志与结论

`/proc/last_kmsg` 为 2097136 字节，SHA256 为 `afbd90d1485165350c99af1f280277328bfe168c4bbd911c0970670ea41f6342`；同时保存 recovery dmesg、recovery 日志、pstore 列表和分区哈希，pstore 为空。

本次 ABL cmdline 包含 `rdinit=/init ... initcall_debug`，没有第二次的 `Could not add` 或 `failed to reserve` 错误，并记录：

```text
{ 6604744 }[ ABL ] Update Device Tree total time: 26 ms
Shutting Down UEFI Boot Services: 6641 ms
{ 6764869 }[ XBL ] Exit EBS        [ 6766] UEFI End
```

**五个 setup_arch 标记均未找到，完整启动仍未通过。** `after_fdt`、`after_memblock`、`after_paging`、`after_unflatten` 和 `after_bootmem` 均无输出；也没有正式 console 标记、主线内核版本、initcall 跟踪或首次的 `TZBSP_ERR_FATAL_NOC_ERROR` 标记。

标记写入前仍有 flat DT 的 compatible、节点名称、reg 检查及临时映射，因此不能根据缺失标记认定内核未进入 setup_arch，或认定已经定位到 FDT 解析之前。实际 ABL 修补后的 DTB、过滤条件是否通过、写入路径是否执行及复位保留行为仍未确认。下一步应区分过滤、映射、写入及复位保留这几个环节，而不是仅根据缺失日志继续前移；本次没有自动开始第七次刷写。

## 恢复状态

日志保存后已恢复原 boot、init_boot、vendor_boot、dtbo，四个分区逐个回读哈希与采集备份匹配；recovery / vbmeta 保持不变。`restore/report.json` 最终阶段为 `restored`，设备留在 TWRP，未请求重启 Android。

完整本地归档位于 `artifacts/boot-tests/sixth-sm-x710/`；实际测试镜像在 `tested-bundle/`，日志和二进制被 Git 忽略。
