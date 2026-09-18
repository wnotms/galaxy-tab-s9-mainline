# SM-X710 第七次启动测试

日期：2026-09-18；SM-X710 revision 6，启动固件 X710ZCU5CYH4。在第六次测试的七个补丁上增加 `find-sec-log-by-validated-flat-dt-range.patch`。

早期诊断在 reserved-memory 的子节点中按精确 reg 查找 `0x880200000` / 2 MiB 日志区，避免依赖节点名称；根 compatible 的检查结果将作为 `flat_dt compatible=yes/no range=validated` 写入日志，匹配失败不再直接退出。S9 专用配置、精确范围验证、五个检查点、首个 4 KiB 临时映射及 PoC 清理仍保留。正式 console 身份过滤不变。此修改仅验证过滤条件的假设，缺失标记仍不能判定内核未执行或确认复位保留行为。

八个补丁已在固定主线的干净文件上顺序应用，结果与增量编译源码逐字节一致。`make bundle`、四个完整镜像结构及 AVB 哈希检查、`make check` 通过；目标对象确认有 reserved-memory 遍历、compatible 检查、early_memremap 和 PoC 清理调用。

本次同时新增独立 TWRP 原四分区恢复脚本及 microSD 恢复包，使用说明见 [恢复说明](twrp-restore.md)。实机预检发现 TWRP 的 `hash` 别名会覆盖同名函数，已将辅助函数改名；预检期间没有写入分区。

测试镜像、预检、启动日志及结果保存在被 Git 忽略的 `artifacts/boot-tests/seventh-sm-x710/`。

镜像 SHA256：

```text
83839ec678b88f8ba103da89f864507cfa875877650f3aaf433ecee7646bd7b5  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c23fff2ebadab9ecd9e8eef73587e39d7bed48694f9f7a703dbe1a0c6ec5bcbc  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 当前状态

恢复包的实机只读校验通过，缺失备份的 --restore 测试在写入前拒绝。机型、固件、AVB flags 2、当前原分区和四个恢复备份预检通过。四个镜像已写入并逐个回读核对，recovery / vbmeta 保持不变，已请求正常重启。Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB。已提示返回 TWRP；目前实验镜像仍在四个启动分区，日志尚未回收，原四分区尚未恢复。缺失 USB 枚举不能单独证明内核未执行。
