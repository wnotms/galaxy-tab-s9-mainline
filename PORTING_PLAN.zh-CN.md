# Galaxy Tab S9 主线 Linux 移植方案

制定日期：2026-09-18。

建议采用 **SM8550 主线内核 + Tab S9 独立板级支持 + Ubuntu 24.04 arm64 用户空间**。复用 Ultra 项目的构建、启动打包和已验证的 SoC 支持，以 Tab S9 原厂设备树重建外设描述。先从 microSD 启动并取得日志，再实现原生显示与触控，最后考虑 UFS 安装和双启动。

本方案以 **SM-X710 / gts9wifi / Wi-Fi 版**为目标；后续 TWRP 采集已确认连接设备为 SM-X710、revision 6，实机数据见第 8 节。SM-X716 等蜂窝版本需要单独核实，基带不属于首期目标。

这里的“主线 Linux”指 upstream Linux 基础上的移植内核，早期仍含板级驱动和补丁；不表示未经修改的 upstream Linux 已完整支持 Tab S9。

当前已建立独立仓库并完成启动调试基线的编译和离线镜像验证，详见 [README](README.md)。下文早期预编译 DTBO 信息仅作为历史核对线索；当前设备树以实机快照和物理 DTBO 第 1 项为准。

## 1. 已核实的参考基线

实际本地目录是 `../ubuntu-galaxy-tab-s9-ultra`，并非当前目录下的 `./ubuntu-galaxy-tab-s9-ultra`。

| 项目 | 本次核实结果 |
|---|---|
| Ultra 参考仓库 | `../ubuntu-galaxy-tab-s9-ultra` |
| 本地参考提交 | `32273b0a410b3e73b20a3a2451e24260fb2a36bd`，2026-09-14 |
| 内核固定版本 | `v7.2-rc3` |
| 内核固定提交 | `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` |
| Tab S9 原厂硬件参考 | `../android_device_samsung_gts9wifi/prebuilt/{dtb,dtbo}.img` |
| Tab S9 恢复环境参考 | `../android_device_samsung_gts9wifi`，README 明确针对 SM-X710 |

内核版本既从本地 `scripts/fetch-mainline.sh` 核实，也从 [Linux 上游提交](https://github.com/torvalds/linux/commit/a13c140cc289c0b7b3770bce5b3ad42ab35074aa)核对。第一阶段沿用这一版本，避免同时引入跨机型和内核升级两种变量。完成 Tab S9 基础功能后，再评估稳定内核或后续主线版本。

Ultra 的功能说明见 [项目仓库](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra)。它只能证明 SM-X910 的参考能力，不能作为 SM-X710 的验收结果。

## 2. Tab S9 与 Ultra 的关键差异

下表的 Tab S9 数据来自本地预编译 DTBO 的二进制解析；是静态硬件描述，仍须与实机运行中的 DT 对照。Ultra 数据来自其 DTS 和驱动源码。

| 部分 | Ultra / SM-X910 | Tab S9 / SM-X710 | 移植动作 |
|---|---|---|---|
| 板级 compatible | `samsung,gts9uwifi` | 新建 `samsung,gts9wifi` | 独立 DTS；按 X710 原厂信息保留 ABL 选择属性 |
| 面板 | ANA38407 / AMSA46AS02 | ANA38407 / AMSA10FA01 | 可复用驱动结构，须重新提取命令与参数 |
| 面板分辨率 | 2960×1848 | 2560×1600 | 重建 DRM modes、地址窗口和物理尺寸 |
| DSC 分片 | 1480×77，2 slices | 原厂 120 Hz timing：1280×100，8 bpc、8 bpp | 重建 DSC 配置和 PPS，不仅修改 modes |
| 触控 | Goodix GT9916 / Berlin，`0x5d` | `stm,fts_touch`，`0x49`，FTS1BA90A 固件命名 | 需要 STM 协议支持，不能复用 Goodix 事件补丁 |
| 触控方向 | Ultra 驱动配置 | 01/02/04 描述为 1600×2560 | 实测坐标方向，再确定 swap/invert |
| S Pen | Wacom W90xx 自定义驱动 | DTBO 同样描述 `wacom,w90xx`、`0x56` | 候选复用，核实 query、报告和坐标范围 |
| 扬声器功放 | 4×CS35L45 | DTBO 描述 CS35L45，`0x30`～`0x33` | 核实声道、复位、供电和校准，不照搬音量配置 |
| 电源/USB PD | SM5714、SM5440 | DTBO 同样有这些器件 | 候选复用协议，电池参数与电流限制重新核实 |
| 内存、启动分区 | Ultra 特定布局 | 已采集，见第 8 节 | 所有地址、尺寸和 AVB 参数重新采集 |

已发现的板级选择信息：

```text
预编译 dtbo.img 的 qcom,board-id：
  <0x10008 0x00>
  <0x10008 0x01>
  <0x10008 0x02>
  <0x10008 0x04>

00：sec,max_coords = <1752 2800>
    sec,firmware_name = "tsp_stm/fts1ba90a_gts8p.bin"
01/02/04：sec,max_coords = <1600 2560>
          sec,firmware_name = "tsp_stm/fts1ba90a_gts9.bin"
```

00 的异常可能是早期板级遗留，不能依据文件内的第一项选择 overlay。需要实机 `/sys/firmware/fdt`、启动信息和触控识别结果共同确认。预编译文件不一定对应当前 One UI 固件。

板级 02 的静态描述还显示：面板 reset GPIO125、TE GPIO86、触控 IRQ GPIO25；触控 overlay 指向 downstream `qupv3_se4_i2c`，Wacom 指向 `qupv3_se3_i2c`。这些是核对线索。必须解析 fixups、供电 phandle 和控制器寄存器地址，不能把 downstream 标签直接替换成主线标签。

用于复核本次解析输入的 SHA-256：

```text
dtb.img   775e1f3c7638db39a986e9005beb94efc18e6a7311e66c63e095ff33efe3fdd6
dtbo.img  f9b86b9f4c7965cffee630b2dbd666af6d0fb6fdc329aeaf5b59f9c567a7a1fc
```

## 3. 启动架构

Ultra 已验证的启动分工是：Samsung ABL 从内置 UFS 的 `boot` 取内核、`init_boot` 取通用 initramfs、`vendor_boot` 取 DTB 和启动参数。参考打包使用 Android header v4，initramfs 使用 legacy LZ4，并把 DTB 附加到内核。它还用非 Android DT-table 的 `dtbo` 避开 Samsung 的 downstream overlay 路径。见 [启动文档](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/main/docs/boot-strategy.md)。

在 X710 上把以上作为待验证的起点，先拆解当前原厂 `boot`、`init_boot`、`vendor_boot` 和 AVB 元数据，确认同样的机制成立。不要直接刷 Ultra 生成的空 DTBO 或整套启动镜像。

```text
Samsung XBL / ABL（沿用原厂）
             │
             ├─ boot          → 主线 Image.gz + Tab S9 DTB
             ├─ init_boot     → 精简 initramfs
             └─ vendor_boot   → Tab S9 DTB、cmdline、必要早期固件
                                      │
                             Linux early init
                                      │
                         microSD ext4 → shell / SSH
                                      │
                             DRM + Mesa + Wayland
```

microSD 是 Linux 根文件系统位置，ABL 仍从 UFS 读取启动镜像。因此这一阶段依然会改变启动分区，需要保存原厂启动集合；不等同于无刷写试启动。

本地 TWRP 的 `BoardConfig.mk` 使用 header v2，这是其 recovery 的打包设置，不能由此断言普通系统 `boot` 也使用 v2。同一文件声明 `BOARD_BOOTIMAGE_PARTITION_SIZE=109576192`，而 Ultra 打包脚本固定为 `100663296`：这已足以说明应当重新测量；TWRP 配置本身也不能替代实机分区尺寸。

## 4. 分阶段实施及验收

### P0：实机硬件清单与恢复基线

产物：`docs/hardware-map.md`、原厂启动镜像备份、`configs/device-manifest.json`。

1. 确认型号、One UI 固件版本、bootloader 状态、板级 revision、RAM/存储规格及是否 A/B。
2. 从运行中的 Android 或匹配恢复环境采集 FDT、cmdline、bootconfig、分区名称与字节尺寸；从当前原厂固件获取启动镜像和匹配的 Samsung GPL 源码。
3. 用 AOSP `unpack_bootimg` 和 `avbtool info_image` 检查头版本、压缩格式、offset、签名/回滚信息。
4. 解析预编译 DTBO 作交叉核对。原厂 base DTB 与选中 overlay 可以离线组合分析；不要把原厂 overlay 应用到主线 DTB。
5. 为每个外设记录：控制器寄存器地址、I²C/SPI 地址、GPIO、IRQ 极性、regulator、时钟、固件文件和证据来源。
6. 核对 Download Mode 和 X710 恢复环境可用，备好匹配固件及启动分区备份。解锁 bootloader 通常会清空数据并影响 Knox，操作前完成备份。

只读采集命令示例，以下不触发刷写；需要设备已连接并且有相应读取权限：

```sh
mkdir -p docs/evidence
adb shell getprop ro.product.device > docs/evidence/product-device.txt
adb shell getprop ro.boot.em.model > docs/evidence/em-model.txt
adb shell getprop ro.bootloader > docs/evidence/bootloader.txt
adb shell getprop ro.boot.slot_suffix > docs/evidence/slot-suffix.txt
adb shell cat /proc/cmdline > docs/evidence/cmdline.txt
adb shell cat /proc/bootconfig > docs/evidence/bootconfig.txt
adb shell ls -l /dev/block/by-name > docs/evidence/partitions.txt
# 在有读取权限的原厂内核环境中执行；若文件不可读，需使用 root。
adb exec-out cat /sys/firmware/fdt > docs/evidence/stock-live.dtb
```

确认采集文件非空、FDT 能解析后才作为证据。TWRP 自己的型号属性和 DT 可能来自它的预编译内核，不能单独证明当前 Android 使用哪个 overlay。

验收：可以恢复到原厂 Android，能够独立进入恢复/Download Mode，拥有足够信息生成 X710 启动 manifest。

### P1：主线内核进入 initramfs，并能取得日志

产物：最小 `sm8550-samsung-gts9wifi.dts`、精简 initramfs、仅安装启动镜像的测试包。

1. 在固定主线版本上启用 CPU、GIC、timer、SCM、RPMh、SMEM、PMIC、基础时钟/电源域、pinctrl，以及经过核实的调试通道。
2. 根据 X710 原厂 live DT 重建 `/reserved-memory` 和 ABL 所需选择属性。原厂保留区域不能遗漏；Ultra 的高地址调试区域和 carveouts 也不能未经核实就复制。
3. 首次进入 RAM 中的 BusyBox `/init`，记录内核版本、设备树身份、内存和 probe 状态，暂不依赖显示或可写 UFS 根分区。
4. 优先建立 USB gadget NCM 网络和日志导出。该通道也需要验证 X710 的 eUSB2、repeater、Type-C 角色和保留电源状态；若 USB 尚不可用，使用经验证的持久日志或可访问串口。
5. `pstore/ramoops` 或 Samsung sec-log 只能在核实保留区域、数据布局后启用。Ultra sec-log 驱动的 compatible 和地址关联也需修改。
6. 如需早期画面，仅在已知原厂 framebuffer 地址、stride、格式和生命周期的情况下使用 simpledrm。它是诊断手段，后续由原生 DRM 替代。

验收：至少多次冷启动进入 `/init`，能确认运行的是新内核/新 DTB；失败后能够取回该次日志并恢复。黑屏本身不判定为内核启动失败。

### P2：microSD 根文件系统和远程操作

产物：Ubuntu 24.04 arm64 最小根文件系统、microSD 镜像、SSH 服务及网络配置。

1. 核实 X710 的 SD 控制器、供电与 card-detect，先把 MMC、SDHCI MSM、ext4 和早期供电/时钟依赖编进内核。
2. 设置独立文件系统标签，例如 `UBTS9_ROOT`；cmdline 使用 `root=LABEL=UBTS9_ROOT rootfstype=ext4 rootwait`，initramfs 必须支持按 LABEL 查找。
3. 先用精简 systemd + SSH，随后加入桌面软件。用户可通过 USB 网络操作系统，不等待 Wi-Fi。
4. 使用独立测试 microSD；准备镜像时核对目标介质，Linux 根分区采用 ext4。
5. 固件来自 X710 自己或匹配官方固件；重建文件映射和校验值，不沿用 Ultra 固件的设备专属 checksum。

参考仓库仍有 `scripts/build-sd-image.sh` 可借鉴，但它固定 Ultra 的 label；当前 `vendor_boot` cmdline 又指向 UFS，二者必须一起改。不能直接运行后就假定它会从卡启动。

验收：SD 根文件系统可读写、多次重启可登录，日志可保存，USB 网络能持续连接；不改动 Android 的 userdata 或 UFS GPT。

### P3：原生显示与 GPU

产物：AMSA10FA01 面板支持、Tab S9 DRM DT 描述和可用的 Wayland 会话。

1. 以 `kernel/drivers/panel-samsung-ana38407.c` 为代码结构参考，为 AMSA10FA01 建立独立 descriptor/compatible，例如待正式提交审查的 `samsung,ana38407-amsa10fa01`。
2. 从 X710 Samsung 源码和 DTBO 提取 init/on/off、reset、电源时序、TE、亮度范围、DSC PPS、显示地址窗口及面板版本差异。
3. 重建 2560×1600 modes、DSC 1280×100 分片配置和供电描述。保留 Ultra 的 prepare/enable 生命周期经验，但不照搬其命令表、panel ID、FOD/HBM 参数。
4. 从原厂已定义的一个模式开始；优先评估 60 Hz，若其独立命令尚不完整，就先实现原厂 120 Hz。不能简单把 120 Hz 的时钟减半当作 60 Hz 支持。
5. 先用 `modetest` 验证 KMS test pattern、亮度和 blank/unblank，再接 Mesa Freedreno/Turnip 与 Wayland。核对 render node 和 renderer，确认硬件加速。
6. Ultra 的 GPU/KMS 资源分离补丁和 `msm.separate_gpu_kms=1` 是候选参考，依据固定内核的实际表现决定是否继承。
7. 若复现 cold handoff 黑屏，区分面板、电源、DSI/PHY 与 DPU 状态。Ultra 的 platform suspend/resume 恢复方法仅作为有条件实验；先从 SD/RAM 根运行，避免直接将全系统 PM workaround 加到默认启动。

验收：冷启动显示、brightness、blank/unblank 和桌面渲染实际可用；运行负载后没有 GPU fault 或显示异常。只出现 DRM connector 不算点亮成功。

### P4：STM 触控和 S Pen

产物：FTS1BA90A 输入驱动支持、正确的触控坐标与 Wacom 输入。

1. 对照主线 `drivers/input/touchscreen/stmfts.c` 和 X710 downstream STM 驱动，核实 chip ID、启动/复位命令、IRQ/FIFO、事件长度与字段、固件依赖。主线已有 STM 驱动不等于支持该新器件。
2. 协议兼容则扩展现有驱动；差异大则编写最小独立驱动，采用标准 regulator、gpiod、threaded IRQ、input MT 和 PM 接口。
3. 首期实现初始化与多点事件，剥离 Samsung 工厂测试、sec_cmd、显示 notifier 等 Android 框架依赖。先核实控制器中的现有固件是否足以工作，确有需求再增加 Linux 固件加载；不把固件升级和校准写入作为探测默认动作。
4. 不使用 Ultra 的 Goodix FIFO、FOD 和掌拒补丁处理 STM 数据。用 `evtest`/`libinput` 检查十指、边缘、释放事件和方向，确认坐标是否需交换/反转。
5. 候选复用 `samsung_wacom_w90xx.c`；验证 X710 的 query/report 格式，读取设备返回的最大坐标，检查 GPIO/电源和 docking 协议。
6. 最后增加 pen proximity 时的触控抑制，并重新验证指尖事件释放与恢复。

验收：触控覆盖四角，多点无粘连；笔的 hover、pressure、tilt、side button 和方向实测正确。

主线 STM 驱动参考：[Linux stmfts.c](https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/stmfts.c)。这是协议比较入口，并非已验证的 Tab S9 方案。

### P5：无线、音频、充电和传感器

这阶段按单个子系统递增启用，保留 P2 的远程通道。

| 子系统 | 方法 | 最低验收 |
|---|---|---|
| Wi-Fi | 核实实际 WCN 型号/PCIe ID；若为 WCN7850，参考 ath12k、pwrseq、PCIe mux 补丁；核对 X710 board data | 冷启动连接、传输、重连，无反复固件崩溃 |
| Bluetooth | 核实 QCA UART、RTS/CTS、供电与匹配固件 | 控制器初始化、键鼠或音频实际使用 |
| 音频 | 参考 LPASS/ADSP、CS35L45 和 UCM，重建声道与供电；保护/校准未确认时限制输出 | 四声道正确，无明显失真；麦克风录音 |
| 电池/充电 | 分开验证 fuel gauge、基础充电、PD、PPS；重新设置电池容量/校准/温度与电流限制 | 电压/温度可信，基础充电和拔插稳定，再试快充 |
| 传感器 | 使用 X710 ADSP 固件，检查 SSC 接口及用户空间映射 | 实际旋转/光线变化对应读数 |
| USB host/DP | 验证 TCPM、SM5714、redriver、mux 和 HPD | 热插拔、外设传输、外接屏，均不破坏内屏 |

共享 SoC 和器件让复用具备价值，但 supply/GPIO、firmware/board data、校准及行为必须逐项核实。早期保留主线 thermal 和已有硬件保护机制，快充不是首次启动的前提。

摄像头、指纹、S Pen BLE、键盘盖、NPU、Gunyah 和 Waydroid 放在基础桌面之后。Ultra 的 secure fingerprint 和私有 SMC 路径不作为 X710 首期依赖，也不通过批量改 compatible 强行启用。

### P6：电源管理、UFS 根和安装器

产物：经过实机测试的休眠策略、X710 安装包及独立恢复说明。

1. 在 SD 根系统上先验证 UFS 枚举和只读访问，再独立验证存储读写，暂不修改 GPT。
2. 普通桌面阶段默认关闭自动 deep suspend；受控测试从 RAM/SD 根进行，内部 UFS 文件系统卸载后测真实 deep suspend/resume。
3. 检查唤醒时间、存储 uncached reads、文件哈希和 PHY/host 错误；随后受控测试文件写入、Wi-Fi、GPU、USB 与屏幕恢复。
4. 建议至少完成多次冷启动及数十轮短/长休眠、lid/idle 场景；次数是本项目拟定的验收门槛，不表示已经完成。
5. 独立验证稳定性后再选择 UFS 安装方式：继续保留 SD；或明确接受覆盖 userdata；或为 X710 单独设计和验证分区方案。
6. 双启动的启动集合、分区缩放和 Android 加密重建最后实现，不直接使用 `gts9u-split.zip`。

Ultra 文档记录过 UFS resume 导致 ext4 emergency read-only；本地后续文档又记录组合候选通过了三轮 RAM-root 测试，但长期验证仍未完成。参考 [恢复记录](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/main/docs/resume-recovery.md)和本地 `docs/ramroot-diagnostic.md`。这要求在 X710 上独立验收，不能从 README 的勾选状态推导休眠可靠。

## 5. 参考仓库必须修改的具体位置

| 位置 | 当前行为与所需调整 |
|---|---|
| `kernel/dts/sm8550-samsung-gts9uwifi.dts` | 作为参考，新建 X710 DTS；保留区域及外设须重建 |
| `scripts/build-mainline-kernel.sh` | 当前从 `5046f92f507d80b13d2e25c53a5d743861ba5a97` 提取历史 Ultra DTS。改为明确读取 X710 DTS，目标与 Makefile 也改为 gts9wifi |
| `kernel/patches/add-gts9uwifi-dtb.patch` | 改为 X710 DTB 编译目标，依据 ABL 验证结果保留符号生成设置 |
| `kernel/config/config-gts9uwifi.fragment` | 新建 X710 fragment，删除 Goodix/Ultra 首期无关功能；关键启动依赖保持 built-in |
| `kernel/drivers/panel-samsung-ana38407.c` | 增加 AMSA10FA01 支持；构建脚本的历史 panel 来源也要检查 |
| `scripts/build-android-v4-bundle.sh` | 用 X710 manifest 设置 header、offset、各分区尺寸与 AVB 参数；仅 `KERNEL_DTB` 覆盖不足以适配 |
| `configs/vendor_boot/{cmdline,bootconfig}.txt` | 使用 X710 参数、SD 根 LABEL 和正确设备标识 |
| `scripts/build-sd-image.sh` / `make-initramfs.sh` | 更改 label，校验压缩格式和实机 init_boot 容量 |
| `configs/twrp/ubuntu-update-binary` | 新建 X710 安装器，保留积极型号核验、尺寸/挂载/校验检查；P1/P2 不写 rootfs 到 userdata |
| `scripts/validate-bundle.sh` | 从 X710 manifest 检查镜像；不能删除检查来绕过 Ultra 固定值 |
| `scripts/build-device-package.sh` 及 rootfs overlay | 去掉首期必须存在的指纹/SPSS/相机依赖，只安装对应阶段功能 |
| 固件 staging / SHA 文件 / UCM / services | 逐项核实硬件与包内容，再生成 X710 对应配置 |

构建脚本的 `fingerprint_baseline` 固定为 `5046f92f507d80b13d2e25c53a5d743861ba5a97`。关键行为是它通过 `git show "$fingerprint_baseline:kernel/dts/..."` 取出历史 DTS，而非读取刚编辑的工作区 DTS。移植时必须消除这一隐式覆盖，构建后反编译产物 DTB 验证 `model`、compatible、board-id 和外设参数。

`ENABLE_FINGERPRINT_EXPERIMENTAL=0` 只是参考脚本的一个选项，并不能关闭其全部 SPSS/QTEE、相机、Gunyah 或用户空间依赖。适配首期构建应采用明确的补丁列表和配置，而非把现有脚本中的所有 `gts9u` 字符串批量替换。

## 6. 建议的工程产物

```text
galaxy-tab-s9-mainline/
├── PORTING_PLAN.zh-CN.md
├── docs/
│   ├── hardware-map.md
│   ├── boot-strategy.md
│   ├── test-matrix.md
│   └── evidence/
├── configs/
│   ├── device-manifest.json
│   ├── vendor_boot/
│   └── twrp/
├── kernel/
│   ├── dts/sm8550-samsung-gts9wifi.dts
│   ├── config/config-gts9wifi.fragment
│   ├── drivers/
│   └── patches/
├── scripts/
├── artifacts/       # 镜像、模块、校验值及构建 manifest
└── work/            # 独立内核源码/构建目录，避免混用 Ultra 对象
```

以上除本方案文件外均为建议结构，尚未实现。构建目录置于当前工作区，不沿用参考脚本默认的 `/root/ubuntu-gts9u`。

每次产物记录：参考仓库提交、Linux 提交、工具链版本、补丁列表与哈希、DTS 哈希、最终 config、内核 release、模块签名信息、镜像哈希。若使用模块签名强制检查，内核与模块须匹配；不能混装旧 Ultra 模块。

编译和验证顺序：固定源代码 → 应用明确补丁 → merge config/olddefconfig → 编译 Image/DTB/所需模块 → DT 静态检查 → 打包 → 从生成镜像重新拆包核对 → 实机测试与日志归档。

带有 Samsung ABL legacy 属性的启动兼容 DTB 应与未来提交上游的板级描述分开处理；新增正式 binding 需要 YAML schema 与 `dtbs_check`。优先提交通用 STM/面板支持和可解释的 SoC 修复，随后板级 DTS，最后逐步减少移植补丁。

## 7. 当前应当开始的工作

第一轮只推进 P0/P1/P2：获取 **实机 live DT + 当前启动镜像/分区尺寸 + 匹配源码**，建立 X710 最小 DTS 和 USB 日志通道，并从 microSD 根启动。接下来最主要的工程工作是 **AMSA10FA01 面板参数/命令适配**与 **FTS1BA90A 触控协议实现**。

本次仅完成参考资料检查、静态硬件差异分析和方案制定。没有编译内核、访问连接设备、刷写镜像或验证 Tab S9 上的任何功能。

## 8. 后续实机资料提取（2026-09-18）

用户随后授权通过已连接的 TWRP ADB 提取资料，已保存至 `artifacts/device-snapshot-sm-x710-20260918/`。具体目录、校验结果和来源说明见该目录的 `README.zh-CN.md`。

实机确认 SM-X710、bootloader `X710ZCU5CYH4`、硬件 revision `6`、解锁状态；boot/init_boot 为 v4，recovery 为 v2。实际 boot 与 vendor_boot 分区均为 100663296 B；109576192 B 对应当前 recovery 分区，因此之前 TWRP BoardConfig 的 boot size 声明不能用于打包普通 boot。

已提取并核对 33 份分区镜像约 2.91 GiB，含 vendor 等动态分区、启动链和固件/校准分区；还保留 UFS GPT 元数据和恢复环境日志。当前物理 dtbo 含 board-id 02、04 两项，区别于本地预编译参考的 00、01、02、04 四项。TWRP live DT 为 board-id 04，其索引不可直接套用到物理 dtbo 集合。

资料来自当前设备状态，recovery 和 live DT 明确属于 TWRP。尚未采集运行中 Android 的 live DT，未编译或启动主线内核，也未对设备执行刷写或分区修改。
