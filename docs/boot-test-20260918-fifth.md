# SM-X710 第五次启动测试

日期：2026-09-18；SM-X710，revision 6，启动固件 X710ZCU5CYH4。基于 `990651a`，新增第六个补丁 `clean-sec-log-cache-before-reset.patch`，检查第四次未取得日志是否涉及手动复位前未完成缓存清理。

## 改动与主机验证

日志正文写入后，对实际片段执行 ARM64 同步 `dcache_clean_poc`（回绕时清理两段）；随后更新 index / previous_index 并清理头部。保留 WB 映射、console_initcall 注册时机、S9 / 保留区检查、到达标记和环形格式；Kconfig 限制为 ARM64。PoC 清理不保证数据经过固件及强制复位后仍保留，测试未通过也不能单独排除缓存因素。

全部六个补丁在干净固定源码上按顺序应用通过，与编译源码逐字节一致。`make bundle`、四镜像验证器和 `make check` 均通过。目标文件反汇编包含三处 `dcache_clean_poc` 调用重定位，覆盖首段、回绕第二段及头部。

镜像 SHA256：

```text
c2003b4d783c6a58a26936edd5b051dcc1c2090f8d473f5f14df5c0da0a79f3c  boot.img
718c389ebf7cf89cdb9712b9c58b7b2929ca4121da99c495c0eb463c064bc930  init_boot.img
c23fff2ebadab9ecd9e8eef73587e39d7bed48694f9f7a703dbe1a0c6ec5bcbc  vendor_boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
```

## 实机状态

TWRP 预检通过：身份、解锁状态、AVB flags 2、当前原分区及恢复备份哈希匹配。四个镜像已写入并逐个回读通过，recovery / vbmeta 未改变，随后请求正常重启。

Windows 未观察到 Linux / Samsung USB 设备、新网卡或 ADB。当前等待返回 TWRP，采集持久日志、核对 console 标记，再恢复原启动分区；当前四个启动分区仍为第五版实验镜像。

完整本地归档位于 `artifacts/boot-tests/fifth-sm-x710/`；实际镜像保存在 `tested-bundle/`，设备日志及二进制被 Git 忽略。
