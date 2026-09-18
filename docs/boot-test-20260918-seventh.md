# SM-X710 第七次启动测试

日期：2026-09-18；SM-X710 revision 6，启动固件 X710ZCU5CYH4。在第六次测试的七个补丁上增加 `find-sec-log-by-validated-flat-dt-range.patch`。

早期诊断在 reserved-memory 的子节点中按精确 reg 查找 `0x880200000` / 2 MiB 日志区，避免依赖节点名称；根 compatible 的检查结果将作为 `flat_dt compatible=yes/no range=validated` 写入日志，匹配失败不再直接退出。S9 专用配置、精确范围验证、五个检查点、首个 4 KiB 临时映射及 PoC 清理仍保留。正式 console 身份过滤不变。此修改仅验证过滤条件的假设，缺失标记仍不能判定内核未执行或确认复位保留行为。

八个补丁已在固定主线的干净文件上顺序应用，结果与增量编译源码逐字节一致。`make bundle`、四个完整镜像结构及 AVB 哈希检查、`make check` 通过；目标对象确认有 reserved-memory 遍历、compatible 检查、early_memremap 和 PoC 清理调用。

本次同时新增独立 TWRP 原四分区恢复脚本及 microSD 恢复包，使用说明见 [恢复说明](twrp-restore.md)。实机预检发现 TWRP 的 `hash` 别名会覆盖同名函数，已将辅助函数改名；预检期间没有写入分区。

测试镜像、预检、启动日志及结果保存在被 Git 忽略的 `artifacts/boot-tests/seventh-sm-x710/`。

## 当前状态

正在准备实机预检和写入；启动及恢复结果待实机验证。
