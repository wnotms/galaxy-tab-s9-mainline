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

## 实机状态及下一次测试

文件第 30 节明确要求“不自动刷入设备”，因此本次仅构建验证及 TWRP 只读预检，不上传或写入镜像、不重启。设备目前留在 TWRP，原六个分区哈希已匹配，boot/init_boot/vendor_boot/dtbo 的恢复备份已检查，vbmeta/recovery 的主机备份另外核对通过。

- Boot type：尚未启动；计划 cold，实际类型必须届时确认。
- Screen / reboot behavior / time before reboot：尚未测试。
- USB：当前是 TWRP ADB，未作为 Linux 成功判据。
- pstore / last_kmsg：本 GPIO 候选尚未启动，没有属于它的新日志；不会把前次日志作为本次结果。
- Fatal NoC：Unknown。
- Result：NOT RUN；Secure GPIO fix 尚未确认。

收到刷写授权后才进入实机冷启动阶段。刷后返回 TWRP 时应优先保存 pstore，再取 last_kmsg；核对旧日志和本次日志，记录 cold/warm/unknown，只有取得继续运行的新内核证据后才评估 NoC 是否被修复。无新日志仅为 INCONCLUSIVE，不能据此证明修复，也不自动撤回 GPIO 属性。
