# 02 · 案例 A：孤儿驱动泄漏（RTLF，530 MB）

[English version](02-case-rtlf-orphan-driver.en.md)

> **要点**：卸载了软件 ≠ 清除了驱动。这个驱动在**没有任何进程调用**的情况下持续泄漏，而把它带进系统的软件卸载时根本不会带走它。

**目录**：[1. 现象](#1-现象) · [2. 归属](#2-归属标签--驱动) · [3. 这个驱动到底是什么](#3-这个驱动到底是什么) · [4. 调用链是断的](#4-关键证据调用链是断的) · [5. 为什么"取消勾选"无效](#5-为什么取消勾选对部分用户无效inf-拓扑证据) · [6. 处置与验证](#6-处置与验证) · [7. 历史观察](#7-历史观察未落盘) · [8. 证据清单](#8-证据清单)

---

## 1. 现象

非分页池 Top 标签中 `RTLF` 排第二：**530 MB**，62,481 次分配 / 6,050 次释放——**释放率 9.7%**（判据一直接命中）。5.6 万个内核对象从未归还。

形态：**一次性大块 + 不随时间显著增长**（分配早已完成，只是不还）。

## 2. 归属：标签 → 驱动

`RTLF` 在 `C:\Windows\System32\drivers` 中命中 `rtf64x64.sys`（匹配数 1，可归属）。

## 3. 这个驱动到底是什么

### 3.1 身份（INF 与服务注册表）

| 项 | 值 |
|---|---|
| 服务名 | `rtf64` |
| 显示名 | Realtek LightWeight Filter (NDIS6.40) |
| INF | `oem43.inf`，Provider = Realtek，DriverVer = 2025-11-28, 3.15.1128.2025 |
| 启动 | `StartType=1`（**系统启动即加载**），LoadOrderGroup = NDIS |
| 类别 | NetService（NDIS 轻量过滤器，LWF） |

### 3.2 真实身份：改名打包的 WinpkFilter V2（PDB 溯源）

驱动二进制内嵌的调试符号路径（ASCII 字符串，提取自系统现存文件）：

```
D:\WorkingSpace\GitServer\Dragon\WinpkFilter_V2\kernel\LWF\sysw10x64\Release\x64\rtf64x64.pdb
```

链接器写入的 PDB 路径通常不会被清理。它暴露了两件事：

1. 这个驱动源自 **WinpkFilter**（一个商用的 NDIS 中间层/过滤框架，常用于带宽控制类产品）的 V2 版本内核 LWF 工程；
2. 厂商改名打包时**忘了改构建路径**——`rtf64x64` 的名字是包装层给的，工程本体是 WinpkFilter。

> 用 PDB 路径判断"它其实是别的东西改名"非常有效，厂商换产品名时经常忘了改这个。

### 3.3 它是怎么进系统的

`rtf64` 是 **OMEN Gaming Hub 的"网络助推器（Network Booster）"功能的依赖组件**：OGH 安装/启用该功能时通过 INF 把过滤器装进网络栈。这一点有多个独立来源印证（HP 支持社区多个帖子、社区博客），与本机时间线一致。

**关键**：INF 的 Provider 是 Realtek、驱动签名也是 Realtek——**驱动来自 Realtek，OGH 负责把它带进门**。责任主体有两个，别混。

## 4. 关键证据：调用链是断的

NDIS 过滤器的正常使用链：

```
用户态控制程序
    ↓ 加载
通信层 DLL（System32\RtFDrvIOCtrl.dll，WinpkFilter 的 CNdisApi 封装）
    ↑ 加载
核心库 DLL（System32\RtBWCtrl.dll，带宽控制核心）
    ↑ 加载
OGH 的 NetworkCap 模块
```

实测（处置时）：

```
tasklist /m RtBWCtrl.dll      → 无匹配
tasklist /m RtFDrvIOCtrl.dll  → 无匹配
```

**全机没有任何进程加载这两级 DLL** ——即没有用户态程序在"使用"这个驱动。它在网络栈里挂着、开机自动加载、530 MB 池内存拿在手里，但**是个没人用的孤儿**。

> 这就是"孤儿驱动型"的含义：泄漏在驱动自身（或其绑定路径），与是否有调用方无关。对照案例 B（没人调用就不漏）。

## 5. 为什么"取消勾选"对部分用户无效（INF 拓扑证据）

`oem43.inf` 的绑定拓扑（实测摘录，见 evidence/rtf64-inf.txt）：

```
UpperRange   = "noupper"      ← 不向上提供接口
LowerRange   = "nolower"      ← 不向下依赖接口
FilterMediaTypes = "ethernet, wan, ppip"
FilterRunType = 1             ← 过滤器必须在协议绑定前运行
StartType = 1                 ← 系统启动即加载（SCM 独立服务）
```

三个推论：

1. **`noupper`/`nolower` = 纯旁路层**：对 TCP/IP 的绑定与否不影响连通性 ⇒ 禁用它**不会断网**，处置风险低；
2. **`FilterRunType=1` + `StartType=1`**：它是注册在 SCM 的**独立内核服务**，开机自动加载。在网络适配器属性里"取消勾选 Realtek LightWeight Filter"只断绑定，**服务本身照样加载**——这解释了 HP 社区里"取消勾选后仍复发"的用户反馈；
3. **OGH 卸载不带走它**：INF 安装的驱动归 pnputil/驱动仓库管，OGH 的卸载器不管它。

## 6. 处置与验证

```powershell
# 需要管理员；重启后 rtf64 不再加载
sc.exe config rtf64 start= disabled
# （更彻底：sc delete rtf64；或 pnputil /delete-driver oem43.inf /uninstall）
```

处置后重启，复测：

| 指标 | 处置前 | 处置后 |
|---|---|---|
| `RTLF` 占用 | 530 MB | **0** |
| 网络 | — | 正常（旁路层，预期之内） |

## 7. 历史观察（未落盘）

处置前曾观察到设备对象 `\Device\RTF64` 的 DACL 允许 **Everyone (WD) 可读写**——任何本地进程都能直接与该驱动通信。该观察发生在处置当日的会话中，**未落盘为证据文件**；处置后驱动不再加载、设备对象不存在。复验方法（如需核实）：临时 `sc start rtf64` 拉起服务后，以 `NtOpenFile + NtQuerySecurityObject` 读取 `\Device\RTF64` 的 SDDL 即可。本仓库按证据纪律将其标为**历史观察**，不参与结论链。

## 8. 证据清单

| 证据 | 文件 |
|---|---|
| 泄漏快照（释放率 9.7%） | `evidence/pooltag-before.json`（RTLF 条目） |
| 处置后归零 | `evidence/pooltag-after.json`（RTLF 缺失） |
| PDB 路径原文 | `evidence/rtf64-pdb.txt` |
| 服务注册表 + Parameters | `evidence/rtf64-service.txt` |
| INF 全关键段 + 解读 | `evidence/rtf64-inf.txt` |
| 调用链断裂（tasklist 输出） | `evidence/rtf64-no-callers-and-nvml-callers.txt` |

---

上一篇：[01 · 四条实战判据](01-field-criteria.md) ｜ 下一篇：[03 · 案例 B：调用方触发的泄漏](03-case-nvrm-polling-caller.md)
