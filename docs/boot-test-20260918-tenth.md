# SM-X710 第十次启动测试

首次测试的命令行没有 initcall_debug，第二至第九次均包含它。第九次 boot / init_boot / dtbo 与首次逐字节一致，vendor_boot 的正文除命令行字段外也与首次相同；命令行唯一差异就是 initcall_debug。仍然没有主线输出，因此还需隔离这个共同变量。

本次移除默认命令行的 initcall_debug，保留早期日志补丁、loglevel=8 / ignore_loglevel，以及第八次的精确首次 DTB。相对于第八次，Kernel Image、DTB、initramfs、boot / init_boot / dtbo 镜像全部不变，只有 vendor_boot 的命令行及其对应 AVB 哈希变化。参数导致固件 FDT 扩展或内核时序变化的假设仍未验证，不能提前归因。

镜像输入与三份未改镜像哈希一致，vendor_boot 正文除命令行字段外逐字节一致；四镜像检查和 TWRP 预检通过，四个镜像已写入并回读匹配，recovery / vbmeta 未变，已正常重启。Windows 未观察到 Linux / Samsung USB、新网卡或 ADB，等待返回 TWRP 回收日志和恢复原分区，完整本地记录位于 `artifacts/boot-tests/tenth-sm-x710/`。

镜像 SHA256：

```text
affb95de789ad4fbe9934aba7be743b3b6140172e2c993ea65d520dc97bf7871  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c6b91d0f12620c98ca10ff0bdc96005699d14e8f0b4be0d721a6be13e6bfd151  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

截至本记录，第十次仍等待用户返回 TWRP，ADB 未连接。四个启动分区当前仍是测试镜像，尚未执行原分区恢复；没有本次内核日志，不能判定停止位置或将其归因于 initcall_debug。第八、九次已完成日志回收和原分区恢复。
