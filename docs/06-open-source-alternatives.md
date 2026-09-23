# 06 · 附录：OMEN 开源替代项目现状与边界

**简体中文** · [English](06-open-source-alternatives.en.md)

> 本文承接 [05 修复篇](05-remediation-and-alternatives.md)第 5 节：那边只说"有替代、去看附录"，本文回答"**装什么、这些项目是什么现状、适配哪些机器、边界在哪、有什么坑**"。
> ⚠️ 本文为**调研记录**（2026-09，基于各项目 README/发布说明与官方支持列表，未在本机逐一实测），时效性有限——装之前请到各项目仓库核实最新状态。

---

## 0. 按功能位选：装什么

⚠️ **以下均未在本机实证**。它们只能部分实现 OGH 的功能，且可能不支持你的机型（见第 3 节边界）。

| 功能位 | 项目 |
|---|---|
| 性能模式 / 风扇 / 背光（OMEN 专属） | [OmenMon](https://github.com/OmenMon/OmenMon)（或下表的 OmenSuperHub / OmenXHub） |
| 风扇曲线（通用） | [FanControl](https://github.com/Rem0o/FanControl.Releases) |
| 硬件监控（通用） | [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)（**先看文末警告**） |
| RGB 灯光 | [OpenRGB](https://openrgb.org) / Windows 11"动态光效" |
| 远程游戏串流 | Steam Link / Moonlight |

## 1. 项目现状一览

| 项目 | 关系 | 现状 | 定位 |
|---|---|---|---|
| **[OmenSuperHub](https://github.com/breadeding/OmenSuperHub)** | 原创项目（C#/WinForms，~500 star） | 2026-07 后更新放缓 | 风扇 / 性能模式 / CPU PL1/PL2 / GPU 功率 / 温度监控 |
| **[OmenXHub](https://github.com/MasonDye/OmenXHub)** | OmenSuperHub 的二开分支（WPF-UI） | 维护更活跃（2026-09 仍在更新） | 功能大幅扩展：超频、自动化、宏、灯光分区动画等 |
| **OmenMon / OmenHwCtl** | 更早期的逆向研究（GeographicCone 系列） | 停更/研究性质 | 被上述两者列为灵感来源 |
| [FanControl](https://github.com/Rem0o/FanControl.Releases) / [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) / [OpenRGB](https://openrgb.org) | 通用工具（非 OMEN 专用） | 均活跃 | 通用风扇 / 监控 / 灯光，OMEN 专属功能有限 |

**License 注意**：OmenXHub 于 2026-08-30 由 MIT 改为 **GPL v3**——二次分发/集成需注意。

## 2. 它们怎么工作（决定了很多边界）

技术路线与官方 OGH **同源**：通过 **WMI 直连 HP BIOS**（`SendOmenBiosWmi`）下发风扇/功率/灯光指令，传感器读数来自 LibreHardwareMonitorLib，底层 MSR 访问依赖 **PawnIO** 内核驱动（取代老的 WinRing0）。

由此得出三个关键认知：

1. **它们是"OGH 应用层替代品"，不是"驱动替代品"**——不替换、也不移除 HP 的 cap 内核驱动（那几个驱动的池开销实测只有 ~360 KB，本来也不是问题）；
2. **反而会新增一个内核驱动（PawnIO）**——比 rtf64x64 干净，但确实是多一个；
3. **与 OGH 互斥**——两者抢同一套 WMI/BIOS 接口，设置互相覆盖。必须先结束/卸载 OGH。

## 3. 机型适配边界（重点）

**OMEN 开源工具普遍只支持较新的机型**。以 OmenXHub 官方支持列表为例（**2026-09 快照，会过时**，以各项目仓库为准）：

- ✅ 已确认：暗影精灵 8 / 8 Plus / 8 Plus Plus / 9 / 9 Plus / 10、光影精灵 10（Victus）、OMEN 16 (Ryzen)、OMEN 15、OMEN Phantom Gaming
- ❌ 明确不支持：暗影精灵 6 等老款（**第 6 代及更早整体没有成熟开源替代**——这些机器上对应功能要么继续用官方工具，要么放弃）
- ⚠️ 作者原话："主要针对 OMEN 10 Intel（i7-13650HX + RTX 4070）开发，兼容性不保证适用于所有平台"——**非主开发平台的机型（如 10 代 Comet Lake 的老 OMEN 15）属"需实测"区间**

**结论不变（与 05 篇一致）：装之前先到各项目 issue 区搜自己的具体型号。**

另一个具体功能边界：OmenXHub 的 **Dynamic Boost 解锁要求 NVIDIA 驱动 ≥ 537.42 且 < 610.47**——超出窗口的驱动版本用不了该功能；且 20 系显卡通常本身不支持 DB 解锁。

## 4. 收益与风险对照

| 维度 | 说明 |
|---|---|
| 🟢 用户态内存 | 官方全家桶常驻 ~888 MB 工作集（OGH 292 / HP Cap 140 / 遥测 54 / Light Studio 57…），开源自述 15–25 MB（注意：工作集可换页，非硬性占用） |
| 🟢 遥测/广告/联网 | 开源方案完全离线 |
| 🟢 控制粒度 | PL1/PL2 步进、IccMax、风扇曲线拖拽、灯光分区动画等，深度远超官方预设 |
| 🔴 官方独有 | BIOS/驱动更新推送、HP 诊断、保修支持、全系机型兼容 |
| 🟡 维护 | 社区项目，人有失联的可能（OmenSuperHub 已放缓） |
| 🟡 硬件风险 | 绕过官方 API 直写 MSR/WMI/EC，有保护与校验但参数异常仍有风险，作者免责"风险自负" |
| 🟡 网络加速语义不同 | OmenXHub 的"Network Boost"是 **TUN 代理分流**（WinTUN + sing-box），**不是**官方"网络助推器"（内核包拦截调 TCP 优先级）的功能等价物——如果你的目的就是要回官方那个功能，它给不了 |

## 5. 建议的切换步骤（如果你决定换）

1. **先修完泄漏**（按 05 篇操作），不要与换 OGH 混在一件事里做——排查期引入新变量会污染归因；
2. **保留退路**：OGH 安装包备好；OmenXHub 是绿色版单文件，删目录即回退；
3. **先试运行不卸载**：只结束 `OmenCommandCenterBackground.exe`，用 OmenXHub 跑 3–5 天，重点验证风扇曲线真的生效、性能模式、灯光、OMEN 键、休眠唤醒后恢复；
4. 全部正常再卸载 OGH；顺手评估是否停用 `HpTouchpointAnalyticsService`（遥测）；
5. **不要**为了省那 ~360 KB 去动 HP 的 cap 内核驱动——性价比为零。

---

> ⚠️ **装任何替代监控面板之前必读（本仓库的核心教训）**：案例 B 的机制是"监控进程高频轮询 GPU → 驱动的分配跟不上释放"。**任何**以固定频率查询 GPU 的软件（灯效、帧率悬浮窗、游戏助手，包括上面这些开源面板）都可能成为下一个同样的泄漏源。优先选轮询间隔可调的工具、把间隔调长，或者干脆少装监控面板。详见[案例 B](03-case-nvrm-polling-caller.md)。

上一篇：[05 · 修复：卸载与替代方案](05-remediation-and-alternatives.md)
