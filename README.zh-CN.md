# OMEN Gaming Hub 内核池泄漏取证

> **非分页内核内存悄悄涨到数 GB，任务管理器里却找不到是谁干的。这里记录了两次独立泄漏的完整排查：一次是驱动自己在漏，另一次驱动无辜，锅在不停调用它的后台软件；外加一个"看着像泄漏、其实不是"的反例。**

[![License: MIT](https://img.shields.io/badge/License-MIT-0078D4.svg)](LICENSE)

**简体中文** · [English](README.md)

---

## 目录

- [这个仓库是什么](#这个仓库是什么)
- [实测结论摘要](#实测结论摘要)
- [文档](#文档)
- [脚本（全部只读）](#脚本全部只读)
- [证据与表述原则](#证据与表述原则)
- [免责声明](#免责声明)

---

## 这个仓库是什么

一台 OMEN 笔记本（i7 / 32 GB / Win11）出现**非分页池占用 3.9 GB**：任务管理器里没有任何进程能解释，重启后缓慢复发。本仓库记录把这个问题**收敛到具体驱动与具体调用方**的完整过程、判据与原始数据。

两次独立的泄漏，共同入口都是 **OMEN Gaming Hub（OGH，HP 的游戏控制中心）**——但机制**相反**：

| | 案例 B · 锅在调用方 | 案例 A · 锅在驱动 |
|---|---|---|
| 池标签 | `NVRM` | `RTLF` |
| 峰值 | **1.77 GB**（累积 71 小时） | **530 MB** |
| 泄漏主体 | NVIDIA 内核驱动（`nvlddmkm`） | Realtek NDIS 轻量过滤器（`rtf64x64.sys`） |
| **OGH 的角色** | **调用方**：其后台进程是全机唯一轮询方 | **安装者**：作为"网络助推器"依赖装入，且卸载时不带走 |
| 机制 | 驱动按请求服务，请求方高频轮询 → 分配不归还 | **无任何进程调用它**，驱动自身在漏 |
| 处置 | 停掉调用方（或卸载 OGH） | 禁用/删除 `rtf64` 服务（只取消绑定**无效**，见 02） |

> ⚠️ **两者机制相反**：驱动无辜、锅在调用方；锅在驱动本身、OGH 只负责把它带进门。**不要把两者混为一谈。**

第三个标签 `ismc`（317 MB）被证明**不是泄漏**——它作为"大块 ≠ 泄漏"的反例收录（见 04）。

**基础流程不重复造轮子**：池标签排查的标准流程见微软官方文档 [Use PoolMon to find a kernel-mode memory leak](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/using-poolmon-to-find-a-kernel-mode-memory-leak) 与 [PoolMonX](https://github.com/zodiacon/PoolMonX)。本仓库只讲**官方教程没讲的**：什么时候会误判、用什么判据避免。

---

## 实测结论摘要

| # | 结论 | 证据 | 强度 |
|:---:|---|---|:---:|
| 1 | `RTLF` 泄漏 530 MB：62,481 次分配 / 6,050 次释放，**释放率 9.7%** | 池标签快照（evidence/pooltag-before） | ✅ 实测 |
| 2 | `rtf64x64.sys` 是把商用框架 **WinpkFilter V2 改名打包**的产物 | 驱动内嵌 PDB 路径 `...WinpkFilter_V2\kernel\LWF\...` | ✅ 实测 |
| 3 | 处置时**全机没有任何进程在调用**该驱动的通信链（`tasklist /m` 两级 DLL 均无加载者） | 进程模块枚举 | ✅ 实测 |
| 4 | 禁用 rtf64 服务 + 重启后，`RTLF` = **0** | 处置后快照 | ✅ 实测 |
| 5 | OGH 后台进程 `OmenCommandCenterBackground` 是**全机唯一** `nvml.dll` 消费者 | `tasklist /m nvml.dll` | ✅ 实测 |
| 6 | 停掉该进程后，`NVRM` 12 分钟内零增长；其后台服务此后被卸载，泄漏源消失 | 三阶段速率探针 CSV | ✅ 实测 |
| 7 | 处置后 `NVRM` 从 1.77 GB 降至 58.8 MB（重启后），无复发 | 前后快照对比 | ✅ 实测 |
| 8 | `rtf64` 服务不随 OGH 卸载而消失（独立 SCM 服务，`StartType=1` 系统启动即加载） | oem43.inf 服务段 | ✅ 实测 |
| 9 | 设备 `\Device\RTF64` 的 DACL 允许 Everyone 读写 | 处置前会话观察（**未落盘**，复验方法已附） | ⚠️ 历史观察 |
| 10 | `ismc` 317 MB 为静态持有（3 次分配 0 释放，**不随时间增长**），非泄漏 | 双时点快照对比 | ✅ 实测 |

---

## 文档

| 文档 | 内容 |
|---|---|
| [01 · 四条实战判据](docs/01-field-criteria.md) · [EN](docs/01-field-criteria.en.md) | **方法论**：释放率、平坦读数、映射假阳性、调用方归因（官方教程没讲的部分） |
| [02 · 案例 A：孤儿驱动泄漏](docs/02-case-rtlf-orphan-driver.md) · [EN](docs/02-case-rtlf-orphan-driver.en.md) | 改名溯源（PDB）、断链证据、为什么"取消勾选"没用 |
| [03 · 案例 B：调用方触发的泄漏](docs/03-case-nvrm-polling-caller.md) · [EN](docs/03-case-nvrm-polling-caller.en.md) | 一行命令找到轮询者，停掉即归零 |
| [04 · 案例 C：大块 ≠ 泄漏](docs/04-case-ismc-benign.md) · [EN](docs/04-case-ismc-benign.en.md) | 反例：317 MB 的大块为什么放着不动 |
| [evidence/](evidence/) | 脱敏后的原始证据（快照 JSON、速率 CSV、INF 摘录、PDB 提取输出） |
| [scripts/](scripts/) | 只读诊断脚本（免 WDK，Python ctypes 直调内核接口） |
| [DISCLAIMER.md](DISCLAIMER.md) | 使用范围声明 |

每篇文档均有中英两版（中文 `*.md` / 英文 `*.en.md`），页面顶部可互相切换。

---

## 脚本（全部只读）

| 脚本 | 用途 |
|---|---|
| `scripts/pooltag.py` | 池标签快照：按占用排序 Top N，并**把标签映射到驱动**（边界判定 + 匹配计数，拒绝 `Cont` 命中 `Content` 的假阳性） |
| `scripts/alltags.py` | 导出**全部**标签（约 3900 条）到 JSON，做对比基线 |
| `scripts/rate_probe.py` | **速率探针**：固定窗口测 MB/小时，A/B 验证用 |
| `scripts/diffall.py` | 两份快照的增量对比（找"谁在长"） |

```bash
python scripts/pooltag.py snapshot.json         # Top 标签 + 标签→驱动映射
python scripts/alltags.py before.json            # 全量基线
# ……隔一段时间……
python scripts/diffall.py before.json after.json # 增量对比
python scripts/rate_probe.py phase1 30 30 --auto 6   # 自动挑 6 个非通用标签测速率
```

> 四个脚本都只调用 `NtQuerySystemInformation` 查询与**读取**驱动二进制，不修改系统、不联网。

---

## 证据与表述原则

与作者的另一个取证仓库（[alibabaprotect-forensics](https://github.com/deserthouse/alibabaprotect-forensics)）遵循同一套纪律：

1. **结论必须带可复现的证据**——每个判断附命令、原始输出或数据表。
2. **区分三级陈述**：✅ **实测事实**（有落盘原始数据）/ **推断**（由证据合理推出，注明依据）/ ⚠️ **历史观察**（当时见过但未落盘，注明复验方法）。"历史观察"共两处，均已标注：摘要表第 9 条，以及 03 文档内的平坦读数注记。
3. **区分「关联」与「因果」**——时间吻合只是线索。
4. **点名的是事实，不是定性**：本仓库点名 OMEN Gaming Hub 是因为两个泄漏的共同入口都是它（有实证）；Realtek 与 NVIDIA 各自的角色按证据陈述，不做动机推断。

---

## 免责声明

详见 [DISCLAIMER.md](DISCLAIMER.md)。简要版：

- 本文档与脚本仅供**在你自己拥有并管理的设备上**进行诊断与技术研究。
- 作者与文中提及的任何厂商**均无关联**。
- 数据来自**单台机器的实测**；不同机型/驱动版本行为可能不同。
- 处置步骤可能修改系统服务，**执行前请自行评估并创建还原点**。

## License

[MIT](LICENSE)
