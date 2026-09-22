# 05 · 修复:卸载与替代方案

**简体中文** · [English](05-remediation-and-alternatives.en.md)

> 本篇是操作指引,给确认遇到本文档所述问题的读者。每一步都标注了依据的实测条目;替代方案部分**未在本机实证**,已单独标注。看不懂命令行可把本仓库链接交给你的 AI 助手,按文档逐步讲解或代为执行——每步都有预期输出可核对。

---

## 1. 先确认你再动手

修复只针对本文档确认的两种情况(`RTLF` 泄漏 / `NVRM` 匀速增长)。没做确认的先回 [README 的症状对照节](../README.zh-CN.md):一条命令即可分辨。**不要在未确认前卸载或禁用任何东西。**

---

## 2. 第一步:卸载 OMEN Gaming Hub

设置 → 应用 → 安装的应用 → 搜索 **OMEN Gaming Hub** → 卸载。

- **依据**:案例 B 的泄漏源是 OGH 后台进程对 GPU 的高频轮询(实测:全机唯一 `nvml.dll` 消费者,停掉后泄漏停止,见 03)。卸载是最彻底的"停掉"。
- 不需要 OGH 的其他功能才能走这一步;需要保留的,见第 5 节替代方案后再决定。

---

## 3. 第二步:清除残留的 rtf64 驱动(卸载 OGH 不会带走它)

**实测结论(Finding #8)**:`rtf64` 是独立注册的 SCM 服务,OGH 卸载器不管它——**只做第一步,RTLF 的 530 MB 还在**。以管理员执行:

```powershell
sc.exe config rtf64 start= disabled
```

然后**重启**。重启后该驱动不再加载(实测:`RTLF` 归零,见 02 第 6 节)。

- 在网卡属性里"取消勾选 Realtek LightWeight Filter"**无效**(只断绑定,服务照样加载)——机制见 02 第 5 节。
- 想连驱动文件一并移除(可选,更彻底):
  ```powershell
  sc.exe delete rtf64
  pnputil /delete-driver oem43.inf /uninstall
  ```
  (oem43.inf 是本机的编号,不同机器可能不同:先 `pnputil /enum-drivers` 找 Provider 为 Realtek 的那条。)

---

## 4. 第三步:验证修好了

重启后用仓库脚本复测(只读,需管理员):

```bash
python scripts/pooltag.py after.json
```

| 看什么 | 预期 |
|---|---|
| `RTLF` | **消失或为 0**(实测对照:处置前 530 MB → 处置后 0) |
| `NVRM` | 出现在列表但**不再增长**(处置后稳定在 ~59 MB;隔一小时再测一次对比) |
| 网络 | 正常(`rtf64` 是旁路层,禁用不断网——见 02 第 5 节推论 1) |

---

## 5. 替代方案

⚠️ **本节未在本机实证**,是按功能位给出的通用替代;标注"需自查"的项目请先确认对你的机型有效。

| OGH 功能 | 替代 | 说明 |
|---|---|---|
| 性能模式切换 | **Windows 电源计划**(平衡 / 高性能 / 卓越性能) | 系统自带,零安装;`powercfg -setactive` 可命令行切换 |
| 风扇曲线 | **[FanControl](https://github.com/Rem0o/FanControl.Releases)**(开源) | 需自查:取决于主板传感器是否被识别 |
| 硬件监控面板 | 任务管理器 / LibreHardwareMonitor(开源) | **见下方警告** |
| RGB 灯光 | **OpenRGB**(开源)/ Windows 11 动态光效 | 需自查:[OpenRGB 支持列表](https://openrgb.org) |
| 远程游戏串流 | Steam Link / Moonlight(开源) | 与内核无关,不涉及本案例机制 |

> ⚠️ **装替代监控面板前必读(本仓库的核心教训)**:案例 B 的机制是"监控进程高频轮询 GPU → 驱动分配跟不上释放"。**任何**以固定频率查询 GPU 的软件(灯效、帧率显示、游戏助手)都可能成为下一个同样的调用方。选择轮询频率可调的工具、把间隔调长,或者干脆少装面板。

---

上一篇:[04 · 案例 C:大块 ≠ 泄漏](04-case-ismc-benign.md)
