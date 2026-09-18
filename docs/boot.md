# 启动镜像与恢复

构建脚本只生成离线镜像；`scripts/twrp-boot-test.py` 默认只读预检，指定 `--flash` 才写入四个启动分区，指定 `--restore` 才恢复备份。**首次实机日志确认 ABL 交接主线内核，但约 31 毫秒后发生固件报告的 NoC 致命错误，未进入 USB 诊断环境；四个原启动分区已恢复并回读校验**。见 [首次启动记录](boot-test-20260918.md)。结构和哈希检查不能替代实机启动验证。

## 镜像组合

| 分区 | 内容 | 本次实机尺寸 |
|---|---|---|
| boot | Android header v4，`Image.gz + S9 DTB` | 100663296 |
| init_boot | Android header v4，ARM64 BusyBox 诊断 initramfs | 8388608 |
| vendor_boot | header v4，平台空 ramdisk、相同 S9 DTB、cmdline、bootconfig | 100663296 |
| dtbo | 4096 字节非 DT-table payload，加 AVB footer | 16777216 |

generic 和 vendor ramdisk 都使用 **legacy LZ4**，匹配 Ultra 已验证的 ABL 拼接路径。仓库生成确定的 newc 文件顺序、mtime 和压缩内容。

`vendor_boot` 地址取自 S9 快照：kernel `0x8000`、ramdisk `0x02000000`、DTB `0x01f00000`、tags `0x01e00000`，page 为 4096；保留原 header name，不会套用 Ultra 脚本的 `base=0x80000000`。实际 ABL 的放置和 DT 修补行为仍需启动日志验证。

Ultra 已实测通过的路径使用附加 DTB，并用非 DT-table 的 `dtbo` 触发 ABL 回退，避开 Samsung downstream overlay 合并。此处沿用其机制作为 **S9 待验证实验**。生成的 `dtbo.img` 不是原厂 overlay，也不是标准的空 DT table。不要保留 stock DTBO 与此主线 DTS 混用，也不要单刷 boot 后假定完成整套切换。

AVB footer 使用 `algorithm=NONE`，提供哈希而非可信签名。打包不生成 vbmeta；本次快照的 `vbmeta` flags 为 2。关闭校验并不意味着任意三星 bootloader 都会接受该启动组合。

## 启动测试的恢复基线

本次保存的 `boot.img`、`init_boot.img`、`vendor_boot.img`、`dtbo.img` 位于原始快照 `partitions/`，校验值在快照的 `SHA256SUMS` 和 `manifest.json` 中。首次启动实验需要整体保存和整体恢复这四个分区。保持 recovery/TWRP 不变，使用 TWRP 回收主线日志并在启动失败时恢复。

这里的备份恢复到采集时设备状态，不保证是未修改的出厂状态。不要把 EFS、persist、GPT、super 或 recovery 纳入日常主线切换；四个启动镜像已足够进行这一阶段实验。Linux 桌面 rootfs 后续放在 microSD，当前 `/init` 完全在 RAM 中运行。

## RAM 诊断环境

若内核启动并且 USB 链路正常，initramfs 创建 USB NCM 网络设备，平板地址 `172.16.71.1/24`。Linux 主机将对应 USB 网卡配置为 `172.16.71.2/24` 后可使用：

```sh
telnet 172.16.71.1 23
cat /run/boot-dmesg.txt
dmesg
cat /proc/cmdline
```

通过 `dmesg` 中的 probe 报错定位；后续需要查看 `devices_deferred` 时可在配置中启用 DEBUG_FS 并挂载 debugfs。NCM 必须由主机驱动支持；当前主机是 WSL + Windows ADB，设备启动后会变成 USB 网卡，不会保留 TWRP 的 ADB 通道，需要在实际接收 USB 设备的 Windows/Linux 环境配置网卡。

诊断 telnet shell 无认证，仅适合直连 USB 的开发镜像。镜像不包含 SSH、Wi-Fi、桌面及自动挂载根分区的逻辑。

如果不能枚举 USB，按设备的恢复组合回到 TWRP，通过 ADB 读取 `/proc/last_kmsg`。日志驱动与 TWRP 共用 `sec_log_buf`；首次测试已验证主线日志能够跨重启保留。没有日志本身仍不能直接证明内核未执行。

## 离线检查

```sh
python3 scripts/verify-boot-bundle.py artifacts/boot-bundle
(cd artifacts/boot-bundle && sha256sum -c SHA256SUMS)
make check
```

验证器检查实际打包的 DTB、两份 DTB 一致性、S9 carveout 覆盖及无重叠、Android v4 地址和尺寸、平台 ramdisk 表、legacy LZ4 解压和四份 AVB 哈希。未运行完整的 `dtbs_check` binding schema 校验；当前 DTS 的三星选择属性和补丁中的 repeater 属性仍是实验接口。
