# evidence/ —— 原始证据（脱敏）

| 文件 | 内容 | 支撑 |
|---|---|---|
| pooltag-before.json | 处置前快照节选（NVRM 1.77GB / RTLF 530MB / ismc 317MB / cckT） | 全部案例 |
| pooltag-after.json | 处置后快照节选（RTLF=0 / NVRM≈59MB / ismc 持平） | 02/03/04 |
| rtf64-pdb.txt | PDB 路径原文（WinpkFilter V2 溯源） | 02 |
| rtf64-service.txt | 服务注册表 + 安装信息 | 02 |
| rtf64-inf.txt | oem43.inf 关键段 + 解读（noupper/nolower、StartType=1） | 02 |
| rtf64-no-callers-and-nvml-callers.txt | RTLF 断链 + NVRM 唯一调用方 | 02/03 |
| nvrm-rate-probe.csv.txt | 三阶段处置对照 CSV | 03 |
| tag-to-driver.txt | 标签→驱动映射与假阳性对照 | 01 |

## 证据卫生

- 全部输出经过脱敏（用户目录 / 主机名 → 占位符）
- 未落盘的历史观察（设备 DACL、10 次平坦读数）在正文按【历史观察】等级标注，不在此处伪造文件
- 快照为节选（仅案例标签）；全量约 3900 条含本机全部驱动标签，属机器指纹，不发布
