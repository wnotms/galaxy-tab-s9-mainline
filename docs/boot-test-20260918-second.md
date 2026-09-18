# SM-X710 第二次启动测试

测试日期：2026-09-18；设备 SM-X710，revision 6，启动固件 X710ZCU5CYH4。测试源码提交 `3af02f6`。

## 测试改动与镜像

相对首次测试，将 KASLR、UH heap、UH guest 保留内存节点改为三星 ABL 使用的精确名称，保留地址及 `no-map`，避免同范围重复节点；cmdline 加入 `initcall_debug`。此次不更改内核 Image 或 initramfs。

```text
cd13f4ec463c143ec0734600c3f0dd64bd00d0f2de15740e43faf0b3fdf09e7a  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
d0ab8ad0fa65bb8e9b105aab1b4086f083772a1f7aa18057b85d3a8563449592  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

TWRP 身份、解锁状态、AVB flags、六个分区的当前尺寸及哈希、四个恢复备份校验通过。四个实验镜像写入并逐个回读通过，recovery / vbmeta 保持不变，然后请求正常重启。

## 日志与结论

Windows 未观察到 Linux / Samsung USB 设备或新增网络适配器，ADB 没有恢复。用户确认屏幕仍为三星标志及非官方软件警告。

返回 TWRP 后已保存 `/proc/last_kmsg`、recovery dmesg、recovery 日志及分区哈希。`last_kmsg` 为 2097136 字节，SHA256 为 `ee583504e9f157605b2bf8a6b1365e994f702eea63cd548d13cb2fd0a229805f`；pstore 为空。文件包含测试前 TWRP 退出日志、本次修复版的 ABL 启动日志及随后 recovery 引导记录。

ABL 的 cmdline 中出现 `rdinit=/init ... initcall_debug`，确认读到了本次镜像。修复版的 ABL 段出现三条明确错误：

```text
{ 13389408 }[ ABL ] ERROR: failed to reserve UH_HEAP_REGION
{ 13390476 }[ ABL ] ERROR: failed to reserve UH_GUEST_REGION
{ 13391757 }[ ABL ] ERROR: failed to reserve kaslr_region
```

这些错误之前还出现 `ERROR: Could not add ...`，但部分文本夹有 NUL 和损坏字节，不能可靠还原全部参数。ABL 随后仍记录 `Update Device Tree total time` 和退出 UEFI Boot Services，因此不能把上述错误直接表述为 ABL 当场中止启动。

**同名预建节点方案未通过实机验证，不能认定它已经解决首次故障。** 主机的 FDT overlay 模拟合并不能代表三星 ABL 的新增节点行为。本次持久日志没有主线版本、initcall 跟踪或用户态就绪输出，也没有首次的 `TZBSP_ERR_FATAL_NOC_ERROR` 标记；因此本次是否进入主线内核及具体停止位置仍未确认。没有重叠警告不能证明修复有效，因为本次没有主线保留区解析日志。

下一项诊断为移除这三个预建节点、由 ABL 自行添加它们，并保留 `initcall_debug`；其他保护区仍由 DTS 保留。该方案随后已实现并开始 [第三次实机测试](boot-test-20260918-third.md)。

## 恢复与归档

日志保存后已恢复采集时的 boot、init_boot、vendor_boot、dtbo，四个分区逐个回读哈希匹配原备份。recovery / vbmeta 保持不变；`restore/report.json` 的最终阶段为 `restored`。只读确认设备仍在 TWRP，未请求重启 Android。

本地归档位于 `artifacts/boot-tests/second-sm-x710/`，包括 `tested-bundle/`、`preflight/`、`flash/`、`restore/`、`recovery-before/`、`recovery-after/`、Windows 枚举前后快照和 `result.json`。这些设备文件被 Git 忽略。
