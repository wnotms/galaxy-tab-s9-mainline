# SM-X710 第十二次 ARM64 固件入口兼容测试

本次对齐本机 Ultra 仓库的 ARM64 启动支持：S9 最小配置原先关闭 EFI / EFI_STUB 和 RELOCATABLE，Ultra 启用这些配置。固定主线 `Documentation/arch/arm64/booting.rst` 说明原生入口与 EFI PE/COFF 入口不同，EFI stub 完成工作后才转入正常内核；不能因为 ABL 退出 UEFI 就断言它调用了哪一个入口。

新增显式 CONFIG_KERNEL_MODE_NEON=y、CONFIG_EFI=y、CONFIG_RELOCATABLE=y；KASLR 保持关闭，避免引入随机装载位置。配置检查要求 EFI、EFI_STUB、RELOCATABLE 和 NEON 实际启用，并拒绝 RANDOMIZE_BASE=y。该配置是否解决停滞尚待实机验证，不是已确认根因。

内核源码仍是固定主线与原八个补丁；初始 DTB 字节布局、命令行、initramfs 和 Android v4 包装不变。构建仍强制核对固件端 DTB 的首次哈希；候选 Image 将检查 ARM64 magic、MZ 和有效 AArch64 EFI application PE header。

构建、实机预检、启动日志和恢复结果待记录。完整本地资料位于 `artifacts/boot-tests/twelfth-sm-x710/`。
