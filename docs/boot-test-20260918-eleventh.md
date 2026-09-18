# Test 11 修改报告：保留 SM-X710 Secure GPIO 36–39

本报告遵循用户 `C:\Users\ms\Desktop\test11.md`。此处 Test 11 是该文件的 GPIO 单变量实验名称；本机此前的“第十一次完整首次镜像回放”已完成，其原记录保存在 [首次镜像回放记录](boot-test-20260918-eleventh-baseline-replay.md)，归档仍为 `artifacts/boot-tests/eleventh-sm-x710/`，不把两次实验日志混用。

## 唯一功能修改

目标文件：`kernel/dts/sm8550-samsung-gts9wifi.dts`。

```dts
&tlmm {
 gpio-reserved-ranges = <36 4>;
};
```

stock 新 DTB 的 `/soc/pinctrl@f000000` 有 `qcom,gpios-reserved = <0x24 0x25 0x26 0x27>`，即 36、37、38、39。主线标准属性在现有 `/soc@0/pinctrl@f100000`、compatible 为 `qcom,sm8550-tlmm` 的节点中添加，地址及 reg 没有修改。固定源码中的 qcom,sm8550-tlmm.yaml 支持此属性，gpiolib 以 start/count 解析并清除对应 valid_mask 位；尚未实机证明这些引脚就是 NoC 原因，或证明所有 TLMM probe MMIO 访问都会因此被避开。

stock DTB SHA256：`9d645c1d0051f65d43f22bc16aa0ebd92b4e7f465f0465c61a43a79d7be80bf3`。根目录用户提供的文件保留，副本、原测试说明和原始来源数据仅存放在被 Git 忽略的 `artifacts/test11/evidence/`。

## Baseline 与未修改内容

修改前 HEAD：`5fe78f71e2a0955e96d3fd20db00fb2fe27153e1`；其 git status 与原 diff 已保存在 `test11-before-status.txt` 和 `test11-before.patch`。

分支中已有用户提交的 EFI 候选配置，本实验不删除、不使用该候选。实际复用 Test 10 归档中的原始 Kernel Image、嵌入的原配置和 initramfs，Linux 固定提交 `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`、工具链 Clang/LLVM 21.1.8 均未切换。Kernel Image SHA256 为 `91f93af69d91d7345a7ea3f679ccf37c46e793627e18c70055061800b7c69c83`，从已验证的 Test 10 boot 镜像提取；嵌入配置已解压保存为 baseline.config，EFI 和 RELOCATABLE 为关闭状态，匹配该实验基线。原八个内核补丁不改动。

没有更改 reserved-memory、kaslr/UH、lpass_ag_noc、USB/DWC3/eUSB2、SDHCI/UFS、显示、framebuffer、cmdline、initramfs、boot header、vendor_boot 构建参数或 DTBO 方案。当前 root kernel config 文件未修改；实验原内核字节完全相同，配置随原内核保持相同。

## 机械性校验调整

旧校验要求固件端 DTB 与首次二进制哈希完全一致；新增属性会被它拒绝。因而 `device/firmware-dtb-baseline.json` 新增一个精确 GPIO 候选哈希，`scripts/check-device-tree.py` 和 `scripts/build-kernel.sh` 仅扩展已知哈希检查来接受该候选，继续接受原基线，仍拒绝未知旧布局。没有修改 boot image builder。此例外先比较整个 DT：删去唯一新属性后，各节点、全部属性值及 FDT reserve-map 与 Test 10 完全相同，再登记候选；这不是取消保留区或镜像验证。

候选 DTB：116855 字节，SHA256 `e59fddefe738a235e8a70f7e6ee6d1f2ebee6e0a5d580a91844f96988b04f025`。

## 验证结果

- DTS 编译成功；从最终 vendor_boot 解析出的 DTB 与输出 DTB 一致，正确 TLMM 节点有 `gpio-reserved-ranges = <0x24 0x04>`。
- 全树只增加这一项属性，FDT reserve-map 相同；Kernel Image 和 initramfs 的输入哈希与 Test 10 一致。
- boot 中压缩内核字节与 Test 10 相同；vendor_boot 正文只改变 DTB 及 dtb_size，cmdline、地址、ramdisk、bootconfig 相同；init_boot / dtbo 两镜像逐字节相同。
- 四镜像 Android v4、AVB 哈希、39 个固定保留区和 ramdisk 检查通过；make check 五个镜像边界测试和 shell 语法检查通过；git diff --check 通过。
- 原基线和新 GPIO 候选均通过检查，篡改 GPIO 为 <36 3> 的候选被哈希校验拒绝。

## Git Diff

功能 diff：

```diff
diff --git a/kernel/dts/sm8550-samsung-gts9wifi.dts b/kernel/dts/sm8550-samsung-gts9wifi.dts
index 2bd8302..b5bfbba 100644
--- a/kernel/dts/sm8550-samsung-gts9wifi.dts
+++ b/kernel/dts/sm8550-samsung-gts9wifi.dts
@@ -221,3 +221,7 @@
  * Their downstream facts are recorded in device/stock-hardware.json.
  * UFS stays disabled: the diagnostic initramfs runs entirely in RAM.
  */
+
+&tlmm {
+ gpio-reserved-ranges = <36 4>;
+};
```

完整代码 diff（含机械性校验调整）保存在 `artifacts/test11/full-code-diff.patch`，不含文档迁移。

## Build Artifacts 与 SHA256

目录：`artifacts/test11/`；四镜像与 SHA256SUMS、manifest.json、baseline-Image、baseline.config、baseline-initramfs.cpio.gz、最终 vendor_boot DTB/DTS、dtb-delta.json、修改前记录和完整代码 diff 均已保存。旧 Test 10 归档没有覆盖。

```text
682f63ae74a3e91a151d15c14e2079e5fe33850d7ca8df6db429260ab56c901e  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
36d6813421bc0ce859f10b83d49e3969b6dc84ca9369f2d2086b8647d8378124  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

构建命令使用现有脚本和显式基线输入：

```sh
python3 scripts/build-boot-bundle.py \
 --kernel artifacts/test11/baseline-Image \
 --dtb artifacts/test11/sm8550-samsung-gts9wifi.dtb \
 --initramfs artifacts/test11/baseline-initramfs.cpio.gz \
 --output artifacts/test11
python3 scripts/verify-boot-bundle.py artifacts/test11
```

## 实机测试结果：恢复模式启动，INCONCLUSIVE

用户随后明确回复“测试”，授权本次刷写及启动验证。已保存刷写前 pstore、last_kmsg 和 Windows USB／网络基线，并将候选四镜像归档到 `artifacts/boot-tests/test11-gpio-sm-x710/tested-bundle/`。

TWRP 新一轮预检通过，原六个分区大小及哈希匹配，四个恢复备份验证通过。boot/init_boot/vendor_boot/dtbo 已刷入并逐一回读确认候选哈希；vbmeta/recovery 校验未变。未执行普通 reboot，而是执行 `adb shell reboot -p`，返回码 0。随后用户报告等待 15 秒后开机，未按音量键，设备自动进入 TWRP。按用户描述记为 cold；主机没有独立验证断电状态，是否先发生自动重启及进入恢复的耗时未知。

返回 TWRP 后优先保存 pstore 的目录清单并拉取文件，再读取 Samsung last_kmsg、dmesg、cmdline、恢复日志与六分区哈希。pstore 为空，拉取 0 文件；日志采集时四分区仍匹配 GPIO 候选，故已排除此次候选未写入的问题。

本次 last_kmsg 共 2097136 字节，SHA256 `43779b8f730866b974045eee6243f20ca7657a778d86b24220cd8551fcd2d333`，与刷前不同。它包含旧 TWRP 的关机记录及一段 ABL 恢复模式启动记录：

```text
PARAM Flag is PARAM_BOOT_RECOVERY_ENTER:
Booting Into Recovery Mode
BootMode = 2
Requested Partition: recovery
```

当前 TWRP 的 cmdline 也包含 `androidboot.boot_recovery=1`。所见 ABL 启动段选择的是 recovery，没有 Test10 主线的 `rdinit=/init`，没有新主线内核版本、GTS9WIFI 检查点或 Fatal NoC 字符串。恢复模式标志的设置来源尚未确定；这段记录支持启动路径受恢复选择影响，不能据此断言从关机到本次 TWRP 之间绝未尝试过主线。旧日志可能保留，日志哈希变化也不等于 GPIO 候选运行。

- Boot type：cold（用户报告等待 15 秒且未按音量键）。
- Screen：自动进入 TWRP；是否先自动重启及耗时未知。
- USB：返回 TWRP 后 ADB 可用；没有捕获主线 USB 观察窗口，不能把 TWRP USB 当作主线成功。
- pstore：空；last_kmsg 已保存，新主线运行未证实，STALE LOG POSSIBLE。
- Fatal NoC：Unknown；日志未见该字符串，不能证明 NoC 已修复。
- Result：INCONCLUSIVE；本次没有取得可评估 GPIO 修复效果的主线运行证据。

采集后使用 microSD 上的独立恢复脚本恢复原 boot/init_boot/vendor_boot/dtbo；每个分区回读通过，再独立核对六分区哈希与刷前完全一致，vbmeta/recovery 校验未变。设备留在 TWRP，未再次重启。GPIO 属性保留，不根据无新内核日志自动撤回。

完整证据保存在 `artifacts/boot-tests/test11-gpio-sm-x710/`：flash/report.json、boot-operation.json、recovery-before/、recovery-after/、restore/report.json 和 result.json。构建 manifest 保留为输入记录，实时结果以本次 result.json 为准。下一次实验应先核实并记录正常启动选择，避免 recovery 参数标志使 GPIO 测试再次无效；不直接修改未确认布局的 Samsung param 分区。

## 同镜像热启动复测：正常 boot 路径，INCONCLUSIVE

用户继续授权“继续刷入测试”。为核实正常启动选择，本轮不再关机，由 TWRP 中 `adb reboot` 请求正常重启；这属于 warm 复测，不与上面的 cold 记录混用。GPIO 候选四镜像、Test10 Kernel Image、initramfs、DTB、cmdline 和打包参数均未改变，也未直接写入 Samsung param 分区。

本轮归档为 `artifacts/boot-tests/test11-gpio-warm-sm-x710/`。保存刷前 pstore、last_kmsg、Windows USB／网络基线及候选四镜像；新一轮 TWRP 预检通过，四分区写入和回读验证通过，vbmeta/recovery 校验未变，正常重启命令执行成功。用户观察本轮停在三星标识。Windows 采样未发现目标 Linux USB 或 Samsung USB 候选，未新增网络接口，ADB 未连接。用户随后手动返回 TWRP；优先保存 pstore，再读取 last_kmsg。停留标识及无 USB 均不能独立证明内核未运行。

本次 pstore 清单为空，拉取 0 文件。last_kmsg 为 2097136 字节，SHA256 `f5ef53b356dc2ebf577762898c17b6fd29a206aadbfd5f1db50c8ddc7da57ffc`，与刷前不同；采集时四分区仍匹配 GPIO 候选。

保存的正常启动段记录：

```text
Booting Into Mission Mode
BootMode = 0
Requested Partition: boot
```

这一段含主线 `rdinit=/init` 参数，并到达 `UEFI End`。刷前日志没有 Mission Mode、BootMode=0 或 rdinit=/init，支持这是一段新增正常启动尝试；已单独保存为 recovery-after/test-abl-segment.txt。其后还有用户手动进入恢复的段落，已另存，不能用后段的 recovery 选择替代前段结果。本轮确实观察到 ABL 正常选择 boot，前轮直接选择 recovery 的现象没有在该启动段复现；这不证明内核指令已执行。

仍没有新主线 Linux 版本、GTS9WIFI 检查点或 Fatal NoC 字符串，也没有 probe 进展证据。日志存在旧 TWRP 内容，标记 STALE LOG POSSIBLE；不能用日志变化、UEFI End 或未见 NoC 来确认 GPIO 修复。启动段没有保留区重叠报错，不代表已验证 ABL 修改后的 DT 内存布局。

- Boot type：warm，TWRP 中 adb reboot。
- Screen：停在三星标识，随后用户手动进入 TWRP。
- ABL selection：正常 boot，BootMode=0，主线 rdinit 参数存在。
- USB：一次 Windows 采样未观察到目标 Linux USB、新网络接口或 ADB，不能据此证明内核未运行。
- pstore：空；新主线执行未证实。
- Fatal NoC：Unknown。
- Result：INCONCLUSIVE；GPIO 修复效果仍未确认。

采集后恢复原 boot/init_boot/vendor_boot/dtbo，每个回读通过；再独立核对全部六分区哈希与刷前一致，vbmeta/recovery 校验未变，最终保持 TWRP，未再次重启。restore/report.json、result.json 保存本轮收尾。GPIO 属性继续保留；后续需取得内核执行或 probe 进展证据，单纯重复这组无日志启动不能确定故障位置。
