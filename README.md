# Galaxy Tab S9 Wi-Fi 主线 Linux

面向 **Samsung Galaxy Tab S9 Wi-Fi / SM-X710 / gts9wifi** 的独立移植仓库。基于 [S9 Ultra 项目](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra)的启动经验，使用本机通过 TWRP 提取的分区和设备树建立 S9 板级配置。

当前是**可构建的启动调试基线**：主线内核、独立 S9 DTB、RAM 中运行的 USB 网络诊断环境，以及 Android v4 启动镜像生成工具。**首次实机日志确认主线内核执行、8 个 CPU 启动及 initramfs 解包；约 31 毫秒后固件报告 NoC 致命错误，完整启动尚未通过。第六次增加五个 setup_arch 早期标记，仍未取得标记、主线输出或 USB 枚举；过滤、映射、写入及复位保留环节尚需区分。第八至第十次参照 Ultra 固定初始 DTB、回退首次真实内核、移除 initcall_debug，均未恢复主线输出或 USB 枚举，问题尚未修复。全部日志已归档，原四个启动分区已恢复并回读匹配，设备留在 TWRP。屏幕和触控尚未实现，不能作为可用的 Ubuntu 桌面系统。**

实机记录：[首次](docs/boot-test-20260918.md)、[第二次](docs/boot-test-20260918-second.md)、[第三次](docs/boot-test-20260918-third.md)、[第四次](docs/boot-test-20260918-fourth.md)、[第五次](docs/boot-test-20260918-fifth.md)、[第六次](docs/boot-test-20260918-sixth.md)、[第七次](docs/boot-test-20260918-seventh.md)、[第八次](docs/boot-test-20260918-eighth.md)、[第九次](docs/boot-test-20260918-ninth.md)、[第十次](docs/boot-test-20260918-tenth.md)。

## 当前内容

| 内容 | 状态 |
|---|---|
| Linux `v7.2-rc3`、Clang/LLVM ARM64 构建 | 已完成本机编译 |
| S9 DTS：board `04`，覆盖实机 revision `6` | 已生成 DTB 并校验 |
| Samsung 保留内存与持久内核日志 | 首次已回收主线日志；第十版移除 initcall_debug 仍无早期标记，入口和复位保留未确认 |
| eUSB2、NXP PTN3222、USB2 peripheral / NCM | 驱动已编入，枚举待实测 |
| microSD / ext4 | 驱动已编入；当前 initramfs 不自动挂载 SD |
| Android v4 的四个启动镜像 | 十次写入及回读通过；启动未通过，原四分区均已恢复 |
| ANA38407 AMSA10FA01、STM FTS1BA90A、Wacom | 保留实机资料；未启用驱动 |
| WLAN、音频、充电、相机、指纹、GPU | 后续阶段，当前未启用 |

仅支持本次采集的 **SM-X710、board04 系列**。SM-X716、S9+、S9 Ultra 及早期 board02 均不在此基线的验证范围内。

## 构建

主机需要 Linux、Python 3.12+、Git、Make、Clang/LLVM/lld、GCC、Bison、Flex、OpenSSL 和 libelf 开发头文件、`dpkg-deb`。本次使用 Clang/LLVM 21.1.8。内核使用 LLVM 交叉编译，无需安装 GNU AArch64 交叉工具链。

```sh
make bundle
make check
```

首次构建会下载固定的主线内核、Debian ARM64 静态 BusyBox、LZ4 和 AOSP avbtool，全部保存在 `work/`。版本、提交与 SHA256 记录在 `device/` 中；后续缓存齐全时可离线构建。默认 `JOBS=8`，例如 `JOBS=4 make bundle`。

产物：

```text
artifacts/kernel/       Image、sm8550-samsung-gts9wifi.dtb、config
artifacts/initramfs/    initramfs.cpio.gz
artifacts/boot-bundle/  boot.img、init_boot.img、vendor_boot.img、dtbo.img
                       manifest.json、SHA256SUMS
```

四个镜像大小依次为 96 MiB、8 MiB、96 MiB、16 MiB，与提取时的分区尺寸一致。镜像使用无签名的 AVB 哈希 footer，供已解锁、关闭 AVB 校验的开发设备使用；它们不是三星签名镜像。本次设备的 `vbmeta` flags 为 `2`，仓库不生成或修改 `vbmeta`。

`make bundle` 和所有构建、导入脚本**只生成主机文件，不调用刷写命令**。镜像组合与恢复方法见 [启动说明](docs/boot.md)。

## 使用已经提取的资料

原始快照位于 `artifacts/device-snapshot-sm-x710-20260918/`，包含 33 个分区镜像及元数据；Git 已忽略整个 `artifacts/`。`recovery.img` 是当前 TWRP，快照不被视为未经修改的原厂固件。

本仓库已导入以下不包含设备序列号的资料：

- `device/boot-profile.json`：实机启动 header、地址、分区大小、DTBO 选择信息及来源哈希。
- `device/stock-hardware.json`：当前 `vendor_boot` 基础 DTB 与物理 `dtbo` 第 1 项合并后的硬件属性。
- `kernel/dts/sm8550-samsung-gts9wifi.dts`：转换到主线 binding 的独立设备树。
- `device/stock-assets.json`：已找到的 S9 面板命令配置、STM/Wacom 固件与 DSP 固件的本地路径和哈希。

需要重新导入时，先运行 `make kernel`，再执行：

```sh
SNAP=artifacts/device-snapshot-sm-x710-20260918
python3 scripts/analyze-device-snapshot.py "$SNAP"
mkdir -p work/stock
work/kernel-build/scripts/dtc/fdtoverlay \
  -i "$SNAP/unpacked/vendor_boot/dtb-0.dtb" \
  -o work/stock/sm-x710-board04.dtb \
  "$SNAP/unpacked/dtbo/overlay-1.dtbo"
python3 scripts/import-snapshot.py "$SNAP" \
  --merged-dtb work/stock/sm-x710-board04.dtb
```

当前物理 DTBO 只有两项：revision `02..03` 和 `04..20`。恢复环境 cmdline 中的 `dtbo_idx=3` 属于 TWRP 的嵌入式旧表，不能用作当前物理 DTBO 的索引。

已提供固件和 vendor 的只读解包工具：

```sh
python3 scripts/stage-stock-files.py "$SNAP" --vendor
```

此可选工具在 amd64 Linux 主机使用固定版本的 mtools/erofs-utils，将 `apnhlos` 的固件和 `vendor` 的文件解包到 `artifacts/stock-files/`，并生成文件哈希清单；不挂载设备分区。工具可能需要主机提供其 Debian/Ubuntu 运行库。原始固件、面板命令资料、EFS、persist 和设备日志均不纳入 Git，也不作为可再分发资源。

## 后续移植

ABL 交接主线内核及 TWRP 回收持久日志已验证；下一步利用 `initcall_debug` 定位早期 NoC 故障，再验证 USB NCM、SD，随后适配显示与输入。S9 与 Ultra 的差异、实机映射和具体推进顺序见 [硬件说明](docs/hardware.md)及 [完整移植方案](PORTING_PLAN.zh-CN.md)。

本次检查结果见 [验证记录](docs/validation.md)。来源、补丁调整和许可证见 [kernel/PROVENANCE.md](kernel/PROVENANCE.md)与 [LICENSE](LICENSE)。Linux 源码和工具缓存不提交到此仓库；默认分支为 `main`。

TWRP 四分区恢复包和独立脚本见 [恢复说明](docs/twrp-restore.md)。最新三次修复与对照结果见 [第十次测试](docs/boot-test-20260918-tenth.md)。
