# SM-X710 第八次启动测试

日期：2026-09-18；SM-X710 revision 6，启动固件 X710ZCU5CYH4。

## 参考项目发现与修改

对照本机 Ultra 仓库提交 `32273b0a410b3e73b20a3a2451e24260fb2a36bd` 的 `scripts/build-mainline-kernel.sh` 第 110 行起的说明：ABL 对 DTB 结构移动敏感，增加无功能节点、固定 phandle 后仍曾启动失败；它因此从固定提交生成已验证 DTB，并在 Linux 运行后添加新设备配置。`docs/boot-strategy.md` 同时确认 vendor_boot 中的 DTB 才是 ABL 使用的板级描述。这个 Ultra 经验不能直接证明 S9 的原因，但与 S9 首次取得主线日志、改名／删除保留区后没有主线输出的现象相符。

本次恢复 S9 提交 `ef83018` 的原 DTS，并从固定主线重新构建。生成 DTB 与第一次实际写入的 boot 镜像中提取的 DTB **逐字节一致**，大小 116814 字节，SHA256 为 `26d173d871ce9f9fa7fa95c6cd4918a3a797eee3abf85ab89c66b84b4c35e0c8`。`device/firmware-dtb-baseline.json` 记录来源与哈希，构建脚本强制核对，避免后续 DTB 意外漂移。第一次只是执行到内核、八个 CPU 和 initramfs 解包后出现固件 NoC 错误，不能把该 DTB 称为完整启动成功的基线。

保留第七次的八个补丁和配置；原始 Kernel Image、initramfs、cmdline、打包参数和恢复包均未改变，只替换两处一致的 DTB。这同时恢复旧的 kaslr / UH heap / UH guest 三个 no-map 保留区；因此能测试恢复该 DTB 的效果，不能单独归因于二进制布局或映射属性。ABL 仍可能增加三处同范围的保留节点并产生重复警告，不能据此认定 NoC 已修复。

DTB 检查器仅在哈希完全等于第一次实测 DTB 时允许旧的三处保留区，并核对精确 reg 和 no-map。普通 DTB 仍要求 ABL 范围不存在，所有输入仍检查 39 个 stock 固定保留区、板级参数及无重叠。旧基线不支持直接套用 --abl-updated 验证，其实际 ABL 更新后的描述仍需实机回收审查。

## 主机验证

`make bundle`、四镜像 Android v4 / AVB / ramdisk 检查及 `make check` 通过。首次归档 DTB 和第七次现代布局 DTB 均通过相应输入检查；将旧基线 model 的一个字节改为同长度有效字符串后，检查器因哈希不匹配拒绝。内核和 initramfs 输入哈希与第七次一致。

镜像 SHA256：

```text
affb95de789ad4fbe9934aba7be743b3b6140172e2c993ea65d520dc97bf7871  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
6ff1bc5b377b1d6b00eb9381798be0bc26cad33f95f8a3671be97158872d1945  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机结果

TWRP 预检通过：机型、固件、AVB flags 2、六个当前分区及四份原备份符合预期。四个镜像已写入且完整回读匹配，recovery / vbmeta 保持不变，已请求正常重启。Windows 未观察到 Linux / Samsung USB、新网卡或 ADB；用户返回 TWRP 后已保存日志，再恢复原四个分区；最终六个分区哈希与测试前原分区匹配，设备留在 TWRP。测试镜像与日志位于被 Git 忽略的 `artifacts/boot-tests/eighth-sm-x710/`。

启动验证未通过。last_kmsg 为 2097136 字节，SHA256 `6f9a0081c49714cef0b4e637ec8e21af4ce57844cb0724cc615a98f900f3c314`；没有 compatible 诊断、五个检查点、正式 console 标记、主线内核版本、保留区错误或 NoC 致命标记。实验 ABL DT 更新 5930237 微秒、Exit EBS 6092619 微秒。恢复第一次 DTB 没有恢复可观察的内核输出，不能把二进制布局解释为唯一原因；下一次将用首次实际内核二进制对照。
