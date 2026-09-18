# 来源与许可证

本仓库默认脚本、配置和文档为 MIT；DTS 为 BSD-3-Clause；Linux 驱动及其修改补丁为 GPL-2.0-only。具体文件 SPDX 优先。

参考项目：[agcarbajo/ubuntu-galaxy-tab-s9-ultra](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra)，本机提交 `32273b0a410b3e73b20a3a2451e24260fb2a36bd`。它记录的更早来源为 [postmarketos-galaxy-tab-s9-ultra](https://github.com/agcarbajo/postmarketos-galaxy-tab-s9-ultra)，参考提交 `b1dcca0`，设备包 `pmaports/device/testing/linux-samsung-gts9uwifi-mainline/`。本仓库直接导入的是上述 Ubuntu 提交中的四个补丁和部分 DTS 结构，没有导入完整桌面项目。

主线 Linux 固定为 `v7.2-rc3`、提交 `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`。内核源码在首次构建时从 torvalds/linux 下载，保持 Linux 原有许可和版权。

## 导入与修改

- `sm8550-samsung-gts9wifi.dts`：参考 Ultra 的保留内存、RPMh regulator 和 SD/USB bring-up 描述。重写为 S9 最小板级设备树；UH guest 大小、板级 ID、SD 电压范围和 repeater 初始化使用 S9 数据；不使用 Ultra 面板、Goodix、指纹或相机节点。
- `add-samsung-sec-log-console.patch`：保留 Ultra 日志驱动算法，改为 S9 compatible / symbol / 文件名；按固定内核重生成 Kconfig/Makefile hunk，保留 GPL-2.0-only。
- `keep-sec-log-previous-index-current.patch`：日志 previous_index 更新，适配 S9 名称。
- `match-samsung-sm8550-eusb2-phy-init.patch`：原样导入；PHY POR 延时与 CPBIAS 初始化。
- `configure-nxp-ptn3222-from-dt.patch`：导入寄存器覆盖功能；新增 `REGMAP_I2C` 的 Kconfig selection，修复在最小配置中出现的链接失败。原驱动的 Linaro Copyright 保留。

来源 SHA256、修改后 SHA256 和修改说明记录在 `device/sources.json`。补丁头中保留的 SM-X910 叙述描述原参考机型，不能解释为 S9 已实测支持。

## 本地诊断补丁

`register-sec-log-before-smp.patch` 是本仓库新增的 GPL-2.0-only 修改，按顺序应用在上述四个导入补丁之后。第四次测试将日志注册从 platform probe 移到 `console_initcall`，使用静态状态直接读取 DT 保留区；限制为 S9 compatible 和快照中确认的 `0x880200000` / 2 MiB，并写入到达标记。环形缓冲写入算法、previous_index 更新和 WB 映射方式保持不变。SHA256 记录在 `device/sources.json` 的 `local_patches`。

该时机仍晚于 `setup_arch`、MM 和 IRQ 初始化，不能覆盖所有最早期故障；需要实机回收日志验证效果。

## 实机资料

使用用户拥有的 SM-X710，通过 TWRP ADB 只读提取。来源标识、启动固件、分区镜像哈希和所用 overlay 信息记录在 `device/boot-profile.json`；公开的硬件属性记录在 `device/stock-hardware.json`。完整镜像、命令脚本、设备日志、校准及身份数据仅保存在被 Git 忽略的目录中，保留其原有权利，不依据本仓库的 MIT/BSD 许可证再分发。

## 构建工具

- Debian ARM64 `busybox-static`：固定包版本和包 SHA256 见 `device/busybox-source.json`，GPL-2.0；原包版权文件保留在缓存解包目录。本仓库不提交 BusyBox 二进制。
- AOSP avbtool：固定提交和源码 SHA256 见 `device/host-tools.json`，Apache-2.0；下载缓存保留原始版权头。
- LZ4 1.10.0：固定官方 release tarball SHA256，库为 BSD-2-Clause，命令行工具为 GPL-2.0-or-later；缓存保留 LICENSE。
- 可选 mtools/erofs-utils：固定 Ubuntu amd64 包和 SHA256；版权文件与二进制保留在本地缓存，不提交。

此仓库独立编写的 Android v4 封装器按 [AOSP boot header](https://source.android.com/docs/core/architecture/bootloader/boot-image-header)和 [vendor boot](https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions)的字段布局实现；使用 AOSP avbtool 检查最终哈希。它不是三星签名或 GKI 认证工具。
