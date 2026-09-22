# 使用范围声明 / Intended Use Statement

## 中文

### 用途

本项目记录**在作者自己的 OMEN 笔记本上**对 Windows 内核池（非分页池）泄漏的取证分析，
目标读者是**在自己拥有并管理的设备上**进行排障的技术人员。

### 与厂商的关系

- 作者与 HP / OMEN / Realtek / NVIDIA / Intel **均无关联**，也未获其授权、赞助或认可。
- 点名 OMEN Gaming Hub 是因为**两个泄漏的共同入口都是它**（有实证，见各案例）；
  Realtek（驱动作者）、NVIDIA（驱动作者）、Intel（案例 C）各自的角色按证据陈述。
  本项目**不主张**任何厂商存在主观过错。

### 脚本

`scripts/` 下全部脚本**只读**：调用 `NtQuerySystemInformation` 查询、读取驱动二进制做标签映射。
不修改系统、不联网。

### 处置步骤

文档中的处置步骤（禁用服务等）**会修改系统配置**，基于单机实测，
不同机型/驱动版本可能不同。执行前请自行评估并创建还原点。

### 表述纪律

| 等级 | 含义 |
|---|---|
| **实测** | 有落盘的原始数据支撑 |
| **推断** | 由证据合理推出，注明依据 |
| **历史观察** | 当时见过但未落盘，注明复验方法（本仓库共 2 处，正文已标注） |

### 免责

MIT 许可，不提供任何担保。使用后果自负。

---

## English

Forensic analysis of Windows kernel pool (nonpaged pool) leaks on the author's own
OMEN laptop. OMEN Gaming Hub is named because it is the common entry point of both
leaks (with evidence); the roles of Realtek / NVIDIA / Intel are stated per evidence.
No vendor affiliation or endorsement. All scripts are read-only. MIT licensed, no warranty.
