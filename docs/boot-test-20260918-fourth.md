# SM-X710 第四次启动测试

日期：2026-09-18；SM-X710，revision 6，启动固件 X710ZCU5CYH4。基于提交 `6c28ca6`，增加本地第五个补丁，将持久 console 从 platform probe 移到 `console_initcall`。

## 改动与主机验证

日志使用静态状态，直接读取 DT 的 memory-region，限制为 S9 compatible 和采集时的 `0x880200000` / 2 MiB；映射后直接写入 `GTS9WIFI: console_initcall reached` 标记，再注册 console 并回放 printk。环形缓冲格式、previous_index 更新和 WB 映射不变；保留第三版的 ABL 添加 KASLR / UH 节点方案及 `initcall_debug`。

`console_init()` 位于 MM / IRQ 初始化之后、SMP 和普通 initcall 之前，无法覆盖所有最早期故障。独立标记只能证明映射及写入阶段到达，不能证明完整启动。

五个补丁在干净固定源码上顺序应用通过，所得文件与实际编译源码逐字节一致。`make bundle`、四镜像检查器及 `make check` 通过；`llvm-nm` 确认 `gts9wifi_sec_log_console_init` 的 initcall 项位于 `__con_initcall_start` 和 `__con_initcall_end` 之间。

镜像 SHA256：

```text
ecf8a55310aab3f4819c42f95bef34f4b46b59734d8911135715418bca10fa3f  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c23fff2ebadab9ecd9e8eef73587e39d7bed48694f9f7a703dbe1a0c6ec5bcbc  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机状态

TWRP 预检通过：设备身份、解锁状态、AVB flags 2、当前启动分区与恢复备份哈希匹配。四个镜像已写入并逐个回读通过，recovery / vbmeta 保持不变，然后请求正常重启。

Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB。用户确认屏幕仍停在三星标志及非官方软件警告。

## 日志与结论

返回 TWRP 后已保存 `/proc/last_kmsg`、recovery dmesg、recovery 日志、pstore 列表和分区哈希。持久日志为 2097136 字节，SHA256 为 `1d8609ee85817510a954474a280228b5512e0d7136da790f03bf0da0f76b4f60`；pstore 为空。

本次 ABL cmdline 含 `rdinit=/init ... initcall_debug`，未出现第二次的 `Could not add` 或 `failed to reserve` 错误，并记录：

```text
{ 13432352 }[ ABL ] Update Device Tree total time: 25 ms
Shutting Down UEFI Boot Services: 13474 ms
{ 13589549 }[ XBL ] Exit EBS        [13595] UEFI End
```

**提前注册 console 的方案尚未取得新增诊断证据，完整启动仍未通过。** 持久日志中未找到 `GTS9WIFI: console_initcall reached` 标记、`gts9wifi-sec-log` 输出、主线内核版本或 initcall 跟踪，也没有首次的 `TZBSP_ERR_FATAL_NOC_ERROR` 标记。

独立标记位于 DT 身份／保留区检查及 WB 映射成功之后。因此标记缺失可能来自更早停止、前置检查／映射未成功，或手动重启时缓存日志未保留；这些均未获证实。不能把标记缺失直接表述为内核没有执行，或已定位在 `console_init` 之前。下一次应验证 WB 缓存日志在手动复位下的落存行为，再决定是否继续前移采集点。

## 恢复状态

日志保存后已恢复采集时的 boot、init_boot、vendor_boot、dtbo，四个分区逐个回读哈希与原备份匹配；recovery / vbmeta 保持不变。`restore/report.json` 最终阶段为 `restored`，设备留在 TWRP，未请求重启 Android。

完整本地归档位于 `artifacts/boot-tests/fourth-sm-x710/`；实际镜像在 `tested-bundle/`，设备日志及二进制均被 Git 忽略。
