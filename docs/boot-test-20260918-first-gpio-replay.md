# 首次日志分析与首次内核 + GPIO 保留复现实验

## 能确定的原因与不能确定的部分

首次留下日志是因为主线确实运行到持久控制台的 probe：首次归档有 Linux 7.2.0-rc3、8 CPU、initramfs 解包，约 0.023623 秒启用 sec_log 控制台，0.023705 秒报告映射 0x880200000、大小 2 MiB。该控制台使用 CON_PRINTBUFFER，注册时回放此前 printk。因此从 0.000000 开始的日志不是 setup_arch 阶段就开始持久写入的证据；日志保存路径实测成立，却有注册前的观察盲区。最后可见主线时间 0.031484 秒，随后固件记录 TZBSP_ERR_FATAL_NOC_ERROR，未确认用户态运行。

首次日志 144231 字节，SHA256 17568d9bf4da5336bae002911e051c540a767e7778086170af209a83f7b276e2。测试前 stock last_kmsg 的 SHA256 为 e655309ff475be801b5eb0d6daaab1e4aba3fe86f75e05186c3dfb7b4ff62b38，其中没有本主线版本和 NoC 致命标记。这排除了首次主线日志只是测试前旧输出的解释。

后续日志通常为 2097136 字节（2 MiB 减 16 字节头），包含 TWRP／固件内容而没有新主线版本。这说明导出了接近整个持久环形区，不能把文件非空或哈希变化当作主线输出。首次经过 TZ fatal 固件采集路径，后续人工按键复位的路径未必相同；首次日志映射是 MEMREMAP_WB 且没有后来加入的显式 PoC clean。复位路径、缓存是否落到可保留内存、环形索引、固件写入及返回 recovery 前的额外重启都可能影响保留内容；它们目前仍是假设，不能根据文件长度单独确认。

已完成的对照约束如下，详细哈希矩阵保存在 artifacts/first-gpio-replay/history-analysis.json：

| 实验 | 内核 | 输入 DTB | initcall_debug | 新主线日志 |
|---|---|---|---|---|
| 首次 | 初始四补丁原 Image | 初始 DTB | 无 | 有，随后 NoC fatal |
| 第九次 | 同首次原 Image | 同首次 | 有 | 无 |
| 第十一次完整回放 | 首次四镜像逐字节一致 | 同首次 | 无 | 无 |
| GPIO Test11 热启动 | Test10 八补丁诊断 Image | 初始 DTB + GPIO 保留 | 无 | 无，ABL 正常选择 boot |

第二次改变保留区节点名称时，ABL 有明确新增／保留失败；它确实改变了固件行为。第三次到后续又有 DTS、initcall_debug 和诊断补丁变化，不能直接归因为同一回归。但第十一次完整回放也没有恢复日志，故这些软件改动不能解释全部后续现象。首次与回放的区别还可能位于启动环境或日志保留过程。目前没有足够证据在“内核较早停住”和“执行过但日志没有保留”之间做唯一归因。UEFI End 只说明固件到达退出 Boot Services 的记录，不能证明已执行内核指令。

Ultra 仓库固定固件面对的 DTB，并报告结构移动可能使其 ABL 在 Linux 保存日志前复位；这是 SM-X910 的经验，不能直接视为 SM-X710 的已证实根因。本机精确回放无日志也提示不能把所有问题都解释成 DTB 结构移动。参考 [Ultra 构建脚本](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/main/scripts/build-mainline-kernel.sh)，本机分析使用旁边仓库的已固定版本。

## GPIO 修复依据及边界

本机新 stock DTB 记录 qcom,gpios-reserved=<36 37 38 39>。主线保留属性使用 gpio-reserved-ranges=<36 4>，既有节点 /soc@0/pinctrl@f100000 和 reg 保持不变。固定 Linux 源码的 gpiolib 先应用该 start/count 到 valid_mask，注册 GPIO 时仅对有效线调用 get_direction；msm 的 get_direction 读取 TLMM ctl 寄存器。因此该属性能避开 GPIO 注册时对 36–39 的逐线方向读取，有具体代码依据。参考 [上游 gpiolib](https://github.com/torvalds/linux/blob/master/drivers/gpio/gpiolib.c)，实测构建仍使用 device/sources.json 中固定提交。

这不证明 36–39 就是首次 NoC 原因，也不保证所有 pinctrl/MMIO 路径都避开它们。SM8550 TLMM 驱动注册使用 arch_initcall，首次日志驱动为普通 builtin_platform_driver；不能因为末条日志是 PF_PACKET 就把下一阶段直接认定为 TLMM probe。probe 延迟、后续消费者访问以及其他驱动都有可能，首次 TZ 细节为加密数据，没有确认的触发地址。三个 ABL 重复保留区和 CONFIG_BOOT_CONFIG 未启用是已见现象，但不是已经确认的 NoC 原因。

## 本轮如何复现

使用第一次实际刷入归档 artifacts/boot-tests/first-sm-x710/tested-bundle，而非当前编译输出或 Test10 Image。scripts/build-first-gpio-replay.py 校验原四镜像，提取原 raw Image、其嵌入配置和原 initramfs，复用原 kernel gzip 字节。保留首次 DTB 的所有其他节点／属性和 FDT reserve-map，仅加入 TLMM GPIO 保留属性；现有已核对 GPIO DTB 与该条件一致。

首次 raw Image SHA256：93cdf5c9fdbd0f5a74d9c7c54294a78fb4df0977beab543d5e7f8724874bfc7a。原 EFI、RELOCATABLE、BOOT_CONFIG 配置不改，最初四个补丁原样保留，不加入后来四个早期日志补丁。首次 cmdline、initramfs、Android v4 地址、vendor ramdisk、bootconfig、DTBO 方案不改。当前仓库已有的八补丁源码及 EFI 候选配置也未改写。

与首次的四镜像比较，init_boot/dtbo 逐字节一致；boot 只改变附加 DTB、kernel_size 及必要 AVB 元数据；压缩内核字节完全相同。vendor_boot 正文只改变 DTB 和 dtb_size，其余 header、cmdline、ramdisk、table、bootconfig 相同。AVB 元数据按改变后的正文重新计算。本轮 vendor_boot 与上轮 GPIO 候选一致，boot 更换为首次原内核。

构建产物 artifacts/first-gpio-replay/，实机归档 artifacts/boot-tests/first-gpio-replay-sm-x710/。四镜像格式／AVB／ramdisk／保留区检查和所有比较通过；make check 的五项镜像边界检查及 shell 语法检查通过。

```sh
python3 scripts/build-first-gpio-replay.py
python3 scripts/verify-boot-bundle.py artifacts/first-gpio-replay
```

输出目录必须不存在，避免覆盖已有实验；需要重新构建时指定新的 --output。

```text
acaeec176c36fbe50b668edad04555d6c3060a6a2aeefca868cfa8d2bca97f53  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
36d6813421bc0ce859f10b83d49e3969b6dc84ca9369f2d2086b8647d8378124  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机状态

已保存本轮刷写前 pstore、last_kmsg、Windows USB／网络基线，TWRP 可用。计划同首次所记录的 adb reboot 正常热启动；首次实际断电及按键细节没有完整记录，不能声称复现了所有硬件／固件状态。

Result：PENDING，尚待刷写启动。先检查正常 boot 选择和是否有属于本轮的新主线版本，再评估是否运行超过首次 31 毫秒或到达用户态。首次内核没有后来 setup_arch 检查点，不能用这些标记缺失判定未启动。无新日志判 INCONCLUSIVE，NoC 未见只能记 unknown，不根据它断言已修复。返回 TWRP 后先 pstore，再 last_kmsg，采集完成后恢复原四分区并核对六哈希。
