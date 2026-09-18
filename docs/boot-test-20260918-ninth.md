# SM-X710 第九次启动对照测试

按 Ultra 使用实际验证镜像做对照的策略，从首次归档 boot 镜像提取原始 Image；该内核只有最初四个补丁，不包含后续四个日志诊断补丁。重新封装后 boot.img 与首次实际镜像逐字节一致，init_boot / dtbo 也与首次一致；vendor_boot 与第八次一致，保留初始 DTB 和 initcall_debug。此对照不是当前八补丁源码的构建结果，来源与原始 Image 哈希记录在 tested-bundle/manifest.json 的 kernel_provenance。

相对于第八次仅替换内核；相对于第一次仅改变 vendor_boot 的诊断命令行。首次内核曾在约 31 毫秒发生固件 NoC 错误，不代表完整启动成功，也不保证本次可重复。四个完整镜像已通过格式、AVB 和 ramdisk 检查。

正在准备实机测试，结果保存在 `artifacts/boot-tests/ninth-sm-x710/`。
