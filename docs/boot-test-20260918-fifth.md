# SM-X710 第五次启动测试

日期：2026-09-18；SM-X710，revision 6，启动固件 X710ZCU5CYH4。基于 `990651a`，新增第六个补丁 `clean-sec-log-cache-before-reset.patch`，检查第四次未取得日志是否涉及手动复位前未完成缓存清理。

## 改动与主机验证

日志正文写入后，对实际片段执行 ARM64 同步 `dcache_clean_poc`（回绕时清理两段）；随后更新 index / previous_index 并清理头部。保留 WB 映射、console_initcall 注册时机、S9 / 保留区检查、到达标记和环形格式；Kconfig 限制为 ARM64。PoC 清理不保证数据经过固件及强制复位后仍保留，测试未通过也不能单独排除缓存因素。

全部六个补丁在干净固定源码上按顺序应用通过，与编译源码逐字节一致。`make bundle`、四镜像验证器和 `make check` 均通过。目标文件反汇编包含三处 `dcache_clean_poc` 调用重定位，覆盖首段、回绕第二段及头部。

镜像 SHA256：

```text
c2003b4d783c6a58a26936edd5b051dcc1c2090f8d473f5f14df5c0da0a79f3c  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c23fff2ebadab9ecd9e8eef73587e39d7bed48694f9f7a703dbe1a0c6ec5bcbc  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机状态

TWRP 预检通过：身份、解锁状态、AVB flags 2、当前原分区及恢复备份哈希匹配。四个镜像已写入并逐个回读通过，recovery / vbmeta 未改变，随后请求正常重启。

Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB。用户确认屏幕仍停在三星标志及非官方软件警告。

## 日志与结论

返回 TWRP 后已保存 `/proc/last_kmsg`、recovery dmesg、recovery 日志、pstore 列表及分区哈希。持久日志为 2097136 字节，SHA256 为 `3226e221d90f4c60e701925b057e51dcaff44524a48e55e3ea8f6f235909eba3`；pstore 为空。

本次 ABL cmdline 包含 `rdinit=/init ... initcall_debug`，未出现第二次的 `Could not add` 或 `failed to reserve` 错误，并记录：

```text
{ 13397796 }[ ABL ] Update Device Tree total time: 24 ms
Shutting Down UEFI Boot Services: 13439 ms
{ 13555755 }[ XBL ] Exit EBS        [13561] UEFI End
```

**新增 PoC 缓存清理后仍未取得 console 到达标记，完整启动未通过。** 日志没有 `GTS9WIFI: console_initcall reached`、`gts9wifi-sec-log`、主线内核版本或 initcall 跟踪，也没有首次的 `TZBSP_ERR_FATAL_NOC_ERROR` 标记。无法确认本次进入主线及停止位置。

不能由标记缺失认定缓存清理无效或排除缓存问题：日志映射、标记写入及缓存清理本身是否执行仍未确认。下一次应将独立标记前移到更早的架构启动阶段，并区分到达、映射及写入步骤；本次未自动开始第六次刷写。

## 恢复状态

日志保存后，原 boot、init_boot、vendor_boot、dtbo 已恢复，四个分区逐个回读哈希匹配采集备份；recovery / vbmeta 保持不变。`restore/report.json` 最终阶段为 `restored`，设备留在 TWRP，未请求重启 Android。

完整本地归档位于 `artifacts/boot-tests/fifth-sm-x710/`；实际镜像保存在 `tested-bundle/`，设备日志及二进制被 Git 忽略。
