# SM-X710 第十次启动测试

首次测试的命令行没有 initcall_debug，第二至第九次均包含它。第九次 boot / init_boot / dtbo 与首次逐字节一致，vendor_boot 的正文除命令行字段外也与首次相同；命令行唯一差异就是 initcall_debug。仍然没有主线输出，因此还需隔离这个共同变量。

本次移除默认命令行的 initcall_debug，保留早期日志补丁、loglevel=8 / ignore_loglevel，以及第八次的精确首次 DTB。相对于第八次，Kernel Image、DTB、initramfs、boot / init_boot / dtbo 镜像全部不变，只有 vendor_boot 的命令行及其对应 AVB 哈希变化。参数导致固件 FDT 扩展或内核时序变化的假设仍未验证，不能提前归因。

镜像输入与三份未改镜像哈希一致，vendor_boot 正文除命令行字段外逐字节一致；四镜像检查和 TWRP 预检通过，四个镜像已写入并回读匹配，recovery / vbmeta 未变，已正常重启。Windows 未观察到 Linux / Samsung USB、新网卡或 ADB，返回 TWRP 后已回收日志和恢复原分区，完整本地记录位于 `artifacts/boot-tests/tenth-sm-x710/`。

镜像 SHA256：

```text
affb95de789ad4fbe9934aba7be743b3b6140172e2c993ea65d520dc97bf7871  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c6b91d0f12620c98ca10ff0bdc96005699d14e8f0b4be0d721a6be13e6bfd151  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机结果与恢复

本次已回到 TWRP，保存 last_kmsg、dmesg、recovery 日志、pstore 和分区哈希。last_kmsg 为 2097136 字节，SHA256 `58b51abf38b462dd2f01c84c8cf836f0d015400ef5f5b4d50c0986c7ff74bd1c`，pstore 为空。实验 ABL cmdline 确认没有 initcall_debug；DT 更新为 6202083 微秒，Exit EBS 为 6361629 微秒。未取得 compatible 诊断、五个检查点、正式 console 标记、主线内核版本或 NoC 致命标记，也没有三处保留区错误。没有额外取得本次屏幕状态确认。

**本次启动验证未通过，移除参数没有恢复可观察的内核输出。** 日志缺失不能直接证明内核未执行，实际 ABL 修补后的 DTB、入口调用、映射／写入路径及复位保留仍未确认。

日志保存后，microSD 恢复脚本已写回原 boot、init_boot、vendor_boot、dtbo，逐个完整回读匹配。最终六个分区哈希与测试前原分区一致，recovery / vbmeta 未变，设备留在 TWRP，未自动重启。恢复记录位于 restore/，result.json 阶段为 completed。

## 本轮对照

| 测试 | 实际内核 | 固件端 DTB | initcall_debug | 主线日志 / USB |
|---|---|---|---|---|
| 首次 | 初始四补丁 | 初始布局 | 无 | 取得主线日志、随后 NoC；无 USB |
| 第八次 | 后续八补丁 | 与首次逐字节一致 | 有 | 均未取得 |
| 第九次 | 首次真实内核 | 与首次逐字节一致 | 有 | 均未取得 |
| 第十次 | 后续八补丁 | 与首次逐字节一致 | 无 | 均未取得 |

当前结果没有证明 DTB 布局、后续诊断补丁或 initcall_debug 能单独解释停滞。首次原内核、不含参数的完整四镜像重复试验，以及断电冷启动对照尚未执行；不能从本矩阵断言首次组合已不再可启动。后续需要验证内核入口和独立日志观测渠道，避免仅靠 last_kmsg 缺失推断停止阶段。本轮没有自动开始第十一次刷写。
