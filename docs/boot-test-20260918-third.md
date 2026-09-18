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

当前等待返回 TWRP，以采集本次持久日志、核对 ABL 添加保留区及 initcall 跟踪，再恢复原四个启动分区。尚不能确认本次主线执行及修正效果；当前启动分区仍为第三版实验镜像。

本地完整归档位于 `artifacts/boot-tests/third-sm-x710/`，实际测试镜像保存在 `tested-bundle/`，设备日志和镜像均被 Git 忽略。
