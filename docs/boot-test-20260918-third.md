# SM-X710 第三次启动测试

测试日期：2026-09-18；设备 SM-X710，revision 6，启动固件 X710ZCU5CYH4。基于提交 `95d3186`，移除三个预建的 KASLR / UH 保留内存节点，由 ABL 添加；保留 `initcall_debug`，其他内核及 initramfs 输入不变。

## 主机检查与镜像

`make bundle`、四镜像验证器、`make check` 均通过。输入 DTB 不含三个 ABL 节点及其范围，仍覆盖 stock 的 39 个有效固定保留区。模拟添加三个 ABL 节点后无重叠；检查器的 `--abl-updated` 模式要求它们存在且地址正确。输入 / 添加后模式混用均被拒绝。模拟检查不替代真实 ABL 的行为验证。

```text
f930f61b56c0c6509660c7d84e56c500419d21e8b03580a00c9bf764774e5e66  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c23fff2ebadab9ecd9e8eef73587e39d7bed48694f9f7a703dbe1a0c6ec5bcbc  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

TWRP 预检通过：设备身份、解锁状态、AVB flags 2、当前分区尺寸及原备份哈希均匹配，四个恢复备份可用。

## 测试状态

四个镜像已写入并逐个回读通过，recovery / vbmeta 未改变，随后请求正常重启。Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB 连接。用户确认屏幕仍停在三星标志及非官方软件警告。

返回 TWRP 后已保存 `/proc/last_kmsg`、recovery dmesg、recovery 日志和分区哈希。持久日志为 2097136 字节，SHA256 为 `17d93ecc2d4d2379e437e6f2828a924ecbae609c5a19f7b241bb317f65df843a`；pstore 为空。文件包含测试前 TWRP 日志、第三版 ABL 启动段及随后的 recovery 引导。

## 日志与结论

本次 ABL cmdline 包含 `rdinit=/init ... initcall_debug`，没有第二次的 `Could not add ...` 或 `failed to reserve UH_HEAP_REGION / UH_GUEST_REGION / kaslr_region` 错误，并继续记录：

```text
{ 12738935 }[ ABL ] Update Device Tree total time: 25 ms
Shutting Down UEFI Boot Services: 12779 ms
{ 12899761 }[ XBL ] Exit EBS        [12905] UEFI End
```

**移除预建节点后，第二次观测到的 ABL 添加／保留错误不再出现；完整主线启动仍未通过。** 未获取 ABL 修补后的实际 DTB，因此不能仅凭没有错误确认三个保留区的最终属性或没有重叠。

本次没有主线内核版本、持久 console、initcall 跟踪或用户态就绪输出，也没有首次的 `TZBSP_ERR_FATAL_NOC_ERROR` 标记。`initcall_debug` 只出现在 ABL cmdline，不能当作内核 initcall 执行证据。当前无法确认主线执行到哪一步，日志缺失也不能证明主线没有运行。

下一项诊断需要更早的持久日志路径，并捕获 ABL 修补后的保留区属性；现有持久 console 可能尚未注册就发生停止，但这仍是待验证的假设。此次没有修改日志驱动，也没有自动开始第四次刷写。

## 恢复状态

日志保存后，原 boot、init_boot、vendor_boot、dtbo 已恢复，四个分区逐个回读匹配采集备份；recovery / vbmeta 哈希保持不变。`restore/report.json` 最终阶段为 `restored`。设备留在 TWRP，未请求重启 Android。

本地完整归档位于 `artifacts/boot-tests/third-sm-x710/`，包括预检、写入、恢复报告、USB/网卡快照及前后 recovery 日志。实际测试镜像保存在 `tested-bundle/`，设备日志和镜像均被 Git 忽略。
