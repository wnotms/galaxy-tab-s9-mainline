# SM-X710 第十次启动测试

首次测试的命令行没有 initcall_debug，第二至第九次均包含它。第九次 boot / init_boot / dtbo 与首次逐字节一致，vendor_boot 的正文除命令行字段外也与首次相同；命令行唯一差异就是 initcall_debug。仍然没有主线输出，因此还需隔离这个共同变量。

本次移除默认命令行的 initcall_debug，保留早期日志补丁、loglevel=8 / ignore_loglevel，以及第八次的精确首次 DTB。相对于第八次，Kernel Image、DTB、initramfs、boot / init_boot / dtbo 镜像全部不变，只有 vendor_boot 的命令行及其对应 AVB 哈希变化。参数导致固件 FDT 扩展或内核时序变化的假设仍未验证，不能提前归因。

正在构建、验证和测试，完整本地记录位于 `artifacts/boot-tests/tenth-sm-x710/`。
