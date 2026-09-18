# 在 TWRP 恢复原四个启动分区

本脚本对应本机 2026-09-18 采集的 SM-X710、X710ZCU5CYH4 快照。这里的“原镜像”指移植测试前的采集备份，不是另行下载的三星出厂固件。

恢复包已准备在主机 `artifacts/restore-original-boot/`，包含脚本、SHA256SUMS 和 boot.img、init_boot.img、vendor_boot.img、dtbo.img，共 216 MiB。备份不提交 Git。平板 microSD 位置为 `/external_sd/gts9wifi-original-boot-20260918/`；后续进入 TWRP 后需确保 microSD 已挂载。

在 TWRP 的终端先检查：

```sh
sh /external_sd/gts9wifi-original-boot-20260918/twrp-restore-original.sh --check
```

执行恢复：

```sh
sh /external_sd/gts9wifi-original-boot-20260918/twrp-restore-original.sh --restore
```

也可通过电脑运行 `adb shell` 后执行相同命令。把整个恢复包移到其他目录时，给脚本传入第二个参数作为备份目录。默认不带参数只检查，不写入。

脚本要求 root、recovery 进程及匹配的机型和启动固件；在任何写入前检查全部四份备份的固定 SHA256、完整大小，以及四个目标分区的大小。恢复逐个写入并同步，然后计算完整分区哈希回读验证。recovery 和 vbmeta 在执行前后计算哈希核对；脚本不自动重启。出现错误应留在 TWRP，修复缺失或损坏的备份后重新执行；已经成功写入的分区不会自动回滚。

如果更新了启动固件，脚本会拒绝使用这套旧快照；应重新采集并核实配套备份，而不是直接删除机型、固件或哈希检查。

第七次测试已在实际 SM-X710 上通过只读检查、缺失备份的拒绝检查，以及恢复四个原分区和完整回读核对。TWRP 刚启动时 microSD 可能尚未挂载，应等恢复包目录可访问后再执行。
