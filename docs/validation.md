# 本机验证记录

日期：2026-09-18。目标为 SM-X710、board04 系列，采集设备 revision 6。下面为初始构建阶段的主机侧验证；之后的实机写入及重启结果见 [首次启动记录](boot-test-20260918.md)。

| 检查 | 结果 |
|---|---|
| 固定 Linux tag/commit | `v7.2-rc3` / `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` |
| ARM64 内核与 DTB 编译 | `make bundle` 通过，Clang/LLVM 21.1.8 |
| 关键内置 Kconfig | 39 项验证通过 |
| 四个补丁在干净固定源码上顺序应用 | 通过；应用后文件与实际编译源码逐字节一致 |
| DTB 型号、board ID、S9 USB 初始化 | 通过 |
| stock 有效固定 carveout 覆盖 | 39 个全部覆盖，输入 DTB 保留区无重叠；首次实机发现 ABL 添加重复节点，后续诊断版已调整节点名称 |
| Ultra 专用面板 / Goodix 误导入 | 未发现 |
| generic / vendor ramdisk | 静态 ARM64 BusyBox；newc 目录验证；两个 legacy LZ4 流解压通过 |
| 四份 Android v4 启动镜像 | 实机地址与大小匹配，附加 DTB 与 vendor DTB 完全相同 |
| AVB | AOSP avbtool 验证四份无签名哈希 footer 通过 |
| Python / shell 检查 | 5 个损坏镜像拒绝测试、构建与 init shell 语法检查通过 |
| 固件与 vendor 解包 | 3753 个本地文件生成哈希清单；76 个相关资产建立索引 |
| 设备身份数据进入 Git | 序列号、EFS、persist、完整镜像、日志与固件内容排除 |

构建镜像的输入哈希和结果哈希见 `artifacts/boot-bundle/manifest.json` 与 `SHA256SUMS`；解包文件的哈希见 `artifacts/stock-files/manifest.json`。这些产物均被 Git 忽略，不作为源码分发。

首次重启已验证 SM-X710 ABL 交接主线内核、8 个 CPU 启动、initramfs 解包、持久日志跨重启读取，以及四个启动分区恢复与回读。内核约 31 毫秒后发生固件 NoC 致命错误，用户态和 USB 枚举未通过。保留区节点名称修正及 `initcall_debug` 诊断版随后已进行 [第二次实机测试](boot-test-20260918-second.md)：ABL 报告三处添加／保留失败，没有本次主线 printk 或 initcall 输出，仍未枚举 USB。原四个启动分区已再次恢复并回读校验。

未完成的验证：新版 ABL 修补后的有效 DTB、完整主线启动、USB 枚举、microSD 读卡、完整 dt-schema 校验。原生显示、触控、S Pen、WLAN、音频、充电及桌面功能仍需移植和实机验证。

第三版移除三个预建的 ABL 保留区节点；默认 DTB 检查要求这些节点及范围不存在，仍覆盖 stock 的 39 个固定保留区。`--abl-updated` 模式要求三个 ABL 节点存在且地址正确，模拟添加后无重叠；两个模式的错误输入均被拒绝。重新构建、四镜像检查和 `make check` 通过。[第三次实机测试](boot-test-20260918-third.md)不再出现第二次的三个 ABL 添加／保留错误，但没有本次主线 printk 或 initcall 跟踪，仍未枚举 USB；原四个启动分区已恢复并回读校验。

第四版新增本地 `register-sec-log-before-smp.patch`，在 `console_initcall` 注册静态持久 console，读取并校验 DT 保留区，写入独立到达标记。全部五个补丁在干净固定源码上应用通过，与实际编译文件逐字节一致；重新构建、四镜像验证器和 `make check` 通过。链接表确认注册函数位于 console initcall 区间；[第四次实机测试](boot-test-20260918-fourth.md)未枚举 USB，持久日志没有新增到达标记、主线 printk 或 initcall 输出，停止位置仍未确认。日志已归档，原四个启动分区已恢复并回读校验。

第五版新增 `clean-sec-log-cache-before-reset.patch`，先清理日志正文到 PoC，再发布 index / previous_index 并清理头部，保留 WB 映射和注册时机。全部六个补丁在干净固定源码上应用通过，与实际编译源码逐字节一致；`make bundle`、四镜像检查和 `make check` 通过，目标文件包含正文首段、回绕第二段及头部的三处缓存清理调用重定位。[第五次实机测试](boot-test-20260918-fifth.md)已写入重启，未枚举 USB，日志及恢复待完成。
