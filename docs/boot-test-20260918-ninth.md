# SM-X710 第九次启动对照测试

按 Ultra 使用实际验证镜像做对照的策略，从首次归档 boot 镜像提取原始 Image；该内核只有最初四个补丁，不包含后续四个日志诊断补丁。重新封装后 boot.img 与首次实际镜像逐字节一致，init_boot / dtbo 也与首次一致；vendor_boot 与第八次一致，保留初始 DTB 和 initcall_debug。此对照不是当前八补丁源码的构建结果，来源与原始 Image 哈希记录在 tested-bundle/manifest.json 的 kernel_provenance。

相对于第八次仅替换内核；相对于第一次仅改变 vendor_boot 的诊断命令行。首次内核曾在约 31 毫秒发生固件 NoC 错误，不代表完整启动成功，也不保证本次可重复。四个完整镜像已通过格式、AVB 和 ramdisk 检查。

TWRP 预检通过，四个镜像已写入并完整回读匹配，recovery / vbmeta 保持不变，已请求正常重启。Windows 未观察到 Linux / Samsung USB、新网卡或 ADB。用户返回 TWRP 后已回收日志，随后恢复原四分区、完整回读匹配，recovery / vbmeta 未变，设备留在 TWRP；完整记录保存在 `artifacts/boot-tests/ninth-sm-x710/`。

镜像 SHA256：

```text
c3b3fc4a4b8b26f131e69258d12de5587e442b8c0a6e477d2fc59a3c381d0993  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
6ff1bc5b377b1d6b00eb9381798be0bc26cad33f95f8a3671be97158872d1945  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

本次未取得主线输出。last_kmsg 为 2097136 字节，SHA256 `c931a31bd581beee38a23c24f74acedd4d6d3d3629bad4f57d98242d883eac41`。实验 ABL DT 更新 13400510 微秒、Exit EBS 13558836 微秒；无保留区错误或固件 NoC 致命标记。此内核不包含后续四个诊断补丁，不能把没有早期标记当成诊断路径未执行。

核对 AVB 前的 vendor_boot 正文，除了 cmdline 字段，其余字节与首次完全相同；cmdline 唯一差异是增加 initcall_debug。因此没有证明撤回内核诊断改动能够恢复输出，也没有排除诊断参数或固件启动状态的影响。第十次将与第八次比较，只去除 initcall_debug。
