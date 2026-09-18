# SM-X710 硬件与适配边界

主要依据本次提取的 `vendor_boot` DTB、当前物理 `dtbo` 第 1 项和 TWRP live DT。设备为 SM-X710，启动固件 `X710ZCU5CYH4`，revision `6`。TWRP 的 live DT 和日志代表恢复环境，不能作为 Android 驱动运行结果。

## 关键差异

| 部件 | S9 实机 | 与 Ultra 的区别 / 当前处理 |
|---|---|---|
| 面板 | ANA38407 AMSA10FA01，2560×1600 | Ultra 为 AMSA46AS02、2960×1848；未导入 Ultra 面板驱动 |
| 120 Hz DSC | 1280×100，两个 slices，8 bpc / 8 bpp | Ultra 使用 1480×77；须重做 PPS、地址窗口与时序 |
| 触控 | I2C4 `0xa90000`，`0x49`，STM FTS1BA90A | Ultra 为 Goodix；需要核实 STM 协议，不能改 compatible 假装支持 |
| 触控 IRQ / 坐标 | TLMM25，1600×2560 | 固件 `tsp_stm/fts1ba90a_gts9.bin`；坐标旋转须实测 |
| 触控电源 | PM8550B L12 1.8 V、L14 | L14 downstream min/max 为 3.3 V、init 为 3.2 V，差异需核实 |
| S Pen | I2C3 `0xa8c000`，`0x56`，Wacom W90xx | IRQ154、PDCT137、FWE179；Ultra 驱动为后续候选 |
| eUSB2 repeater | I2C6 `0xa98000`，`0x4f`，NXP | S9 有五组寄存器设置，Ultra 四组 |
| repeater 供电 / reset | B L15 1.8 V、B L5 3.104 V、VS-D GPIO4 | 在 bring-up DTS 中启用，USB 强制 peripheral / high-speed |
| eUSB2 PHY | `0x88e3000`，VS-E L1 0.88 V、L3 1.2 V | 使用主线 SNPS eUSB2 驱动与 Samsung 时序补丁 |
| XO / sleep clock | 76.8 MHz / 32 kHz | 按 S9 stock DT 设置；不沿用 Ultra 的 sleep-clock 32764 Hz |
| SD | `0x8804000`，4-bit、PM8550 GPIO12 card detect | B L9 2.96–3 V，B L8 1.8–3 V；已描述，读卡待实测 |
| 内部 UFS | reset TLMM210，B L17 / G L1 / G L3 | 当前保持 upstream 的 disabled 状态；诊断环境不使用内部盘 |
| 功放 | 四个 CS35L45，`0x30..0x33` | 后续核实声道、复位和校准，禁止直接套用 Ultra 音量参数 |

S9 repeater 的 value/register 顺序为：

```text
20/06  21/07  63/08  03/09  01/0a
```

## 保留内存

S9 UH guest 为 `0xb1000000 + 0x03600000`，Ultra 为 `+0x03a00000`。ADSP/SLPI 使用 `0x9ea00000 + 0x059b4000`。持久日志为 `0x880200000 + 0x00200000`，保留 Samsung 四字段环形日志头，并允许驱动映射。

设备树校验会检查当前 stock DT 中所有有效固定 carveout 均被主线 DTB 的保留区覆盖，同时拒绝保留区重叠。空区及 stock 中 disabled 的 Trust UI / hwfence 区不计入必须覆盖的区。主线继承的保留区仍保留，其中 hwfence 大小调整为 S9 描述值。

## 显示资料的限制

Samsung 面板 node 使用 `samsung,mdss_dsi_on_tx_cmds_revA` 等字符串脚本，引用 `${DSC_SETTING}`、`${VRR_SETTING}` 和 `$POWER_ON_PRE_SETTING` 等变量。**这些引用不是可直接发送的 DSI 命令**。导入脚本把较长命令脚本和表保存到本地 `artifacts/panel/`，Git 中只记录长度与 SHA256。

本次 vendor 解包已找到 `artifacts/stock-files/vendor/firmware/GTS9_ANA38407_AMSA10FA01.dat`，其中包含上述命令变量定义、面板 revision 条件和 VRR 逻辑。还找到了 `tsp_stm/fts1ba90a_gts9.bin` 与 `wez01_gts9.bin`。这些文件的路径与哈希记录在 `device/stock-assets.json`，内容留在本地。下一步结合 Samsung downstream 解释器还原命令执行顺序、条件、延时和 DSC 参数；不能直接修改 Ultra 的分辨率即启用其驱动。

首个显示里程碑建议固定一个经过核实的模式，完成电源/reset、DCS 初始化、DSC PPS、亮度与休眠恢复；再加入 120 Hz / VRR。触控先做只读 ID/query 和事件协议解析，确认供电和报告格式后再选择改造现有 STM 驱动或新增驱动；不要在初期自动更新控制器固件。

## 推进和验收顺序

1. ABL → 内核 → `/init`：重启回 TWRP 提取 `last_kmsg`，确认进入主线。
2. USB NCM：主机枚举成功，访问 RAM 中的诊断 shell，保存 `dmesg` 和 probe defer 信息。
3. microSD：读出块设备和分区，再只读挂载 ext4 验证；后续建立独立 SD rootfs。
4. 原生显示与 STM 触控；分别验证冷启动、热重启、休眠恢复和坐标。
5. WLAN / Wacom /音频 /电池监测；依实际固件和协议逐项开启。
6. GPU 与桌面、充电控制、相机、指纹；每项以 S9 实机日志和功能测试验收。

当前基线没有移植 Ultra 的 QTEE 指纹、Gunyah 安全 VM、相机和充电管理补丁，也没有将这些功能列为已支持。
