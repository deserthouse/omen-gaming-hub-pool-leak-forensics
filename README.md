# OMEN Gaming Hub Pool-Leak Forensics

> 📌 **Two independent Windows nonpaged-pool leaks that ate gigabytes while Task Manager showed nothing — full evidence chains for a polling-caller leak (🅱️) and an orphan-driver leak (🅰️), plus a big-looking tag that wasn't a leak at all (🅲).**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) · [中文文档](README.zh-CN.md)

---

## Contents

- [What this is](#what-this-is)
- [Findings at a glance](#findings-at-a-glance)
- [Docs](#docs)
- [Scripts (all read-only)](#scripts-all-read-only)
- [Evidence & statement discipline](#evidence--statement-discipline)
- [Disclaimer](#disclaimer)

---

## What this is

An OMEN laptop (i7 / 32 GB / Win11) showed a **3.9 GB nonpaged pool** with no process in Task Manager to explain it, slowly recurring after reboots. This repo documents how the problem was traced to specific drivers **and specific callers**, with the criteria, raw data, and read-only tooling to reproduce the analysis.

Both leaks share one entry point: **OMEN Gaming Hub (OGH, HP's gaming control center)** — but their mechanisms are **opposite**:

| | 🅱️ Case B · polling-caller leak | 🅰️ Case A · orphan-driver leak |
|---|---|---|
| Pool tag | `NVRM` | `RTLF` |
| Peak | **1.77 GB** (accumulated over 71 h) | **530 MB** |
| Leaking component | NVIDIA kernel driver (`nvlddmkm`) | Realtek NDIS lightweight filter (`rtf64x64.sys`) |
| **OGH's role** | 📞 **The caller**: its background process was the *only* `nvml.dll` consumer system-wide | 📦 **The installer**: shipped it as a Network Booster dependency and doesn't remove it on uninstall |
| Mechanism | The driver serves requests; a monitor polling on a fixed cadence makes allocations outpace frees | 👻 **No process was calling it at all** — the driver leaks on its own |
| Fix | Stop the caller (or uninstall OGH) | Disable/delete the `rtf64` service — unchecking the filter is **not** enough (`FilterRunType=1`, `StartType=1`) |

> ⚠️ **Don't conflate the two**: in 🅱️ the driver is innocent and the caller is the problem; in 🅰️ the driver itself is the problem and OGH merely delivered it.

A third tag, `ismc` (317 MB), was proven **not a leak** — kept as the "big blob ≠ leak" counter-example (see doc 04).

**No reinvention of basics**: the standard pool-tag workflow lives in the official docs — [Use PoolMon to find a kernel-mode memory leak](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/using-poolmon-to-find-a-kernel-mode-memory-leak) and [PoolMonX](https://github.com/zodiacon/PoolMonX). This repo covers only what they **don't**: when you're about to misjudge, and which criteria prevent it.

---

## Findings at a glance

| # | Finding | Evidence | Strength |
|:---:|---|---|:---:|
| 1 | `RTLF` leaked 530 MB: 62,481 allocs / 6,050 frees — **9.7% free rate** | pool-tag snapshot (evidence/pooltag-before) | ✅ measured |
| 2 | `rtf64x64.sys` is the commercial **WinpkFilter V2** framework, renamed | embedded PDB path `...WinpkFilter_V2\kernel\LWF\...` | ✅ measured |
| 3 | At remediation time **no process on the system was loading** the driver's call chain (`tasklist /m`, both DLLs) | process-module enumeration | ✅ measured |
| 4 | After disabling `rtf64` + reboot, `RTLF` = **0** | post-remediation snapshot | ✅ measured |
| 5 | OGH's `OmenCommandCenterBackground` was the **sole** `nvml.dll` consumer | `tasklist /m nvml.dll` | ✅ measured |
| 6 | After stopping that process, `NVRM` showed zero growth; its services were later uninstalled and the source vanished | three-phase rate-probe CSV | ✅ measured |
| 7 | `NVRM` dropped from 1.77 GB to 58.8 MB after reboot; no recurrence | before/after snapshots | ✅ measured |
| 8 | The `rtf64` service survives OGH uninstall (standalone SCM service, `StartType=1`) | oem43.inf service section | ✅ measured |
| 9 | Device `\Device\RTF64`'s DACL allowed Everyone read/write | pre-remediation session observation (**not persisted**; re-verification method included) | ⚠️ historical observation |
| 10 | `ismc`'s 317 MB is a static hold (3 allocs / 0 frees, **not growing**) — not a leak | two-point snapshot comparison | ✅ measured |

---

## Docs

| Doc | What's in it |
|---|---|
| [01 · Four field criteria](docs/01-field-criteria.en.md) · [中文](docs/01-field-criteria.md) | 🧭 **Methodology**: free rate, flat readings, mapping false positives, caller attribution — the parts official tutorials skip |
| [02 · Case A: orphan driver](docs/02-case-rtlf-orphan-driver.en.md) · [中文](docs/02-case-rtlf-orphan-driver.md) | 🅰️ renamed-framework tracing (PDB), dead call chain, why "unchecking" fails |
| [03 · Case B: polling caller](docs/03-case-nvrm-polling-caller.en.md) · [中文](docs/03-case-nvrm-polling-caller.md) | 🅱️ one command finds the poller, stop it and the leak stops |
| [04 · Case C: big blob ≠ leak](docs/04-case-ismc-benign.en.md) · [中文](docs/04-case-ismc-benign.md) | 🅲 counter-example: why a 317 MB block was left alone |
| [evidence/](evidence/) | 🗂️ sanitized raw evidence (snapshots, rate CSV, INF excerpts, PDB extraction) |
| [scripts/](scripts/) | 🔧 read-only diagnostic tools (no WDK; Python ctypes straight into the kernel API) |
| [DISCLAIMER.md](DISCLAIMER.md) | 📜 scope statement |

Every doc is available in both English (`*.en.md`) and Chinese (`*.md`) — switch languages via the link at the top of each page.

---

## Scripts (all read-only)

| Script | Purpose |
|---|---|
| `scripts/pooltag.py` | pool-tag snapshot: top-N by usage with **tag→driver mapping** (boundary matching + hit counts — rejects `Cont` matching inside `Content`) |
| `scripts/alltags.py` | export **all** tags (~3,900) to JSON as a comparison baseline |
| `scripts/rate_probe.py` | **rate probe**: MB/hour over a fixed window, for A/B verification |
| `scripts/diffall.py` | diff two snapshots (find "what's growing") |

```bash
python scripts/pooltag.py snapshot.json         # top tags + tag→driver mapping
python scripts/alltags.py before.json            # full baseline
# ... some time later ...
python scripts/diffall.py before.json after.json # incremental diff
python scripts/rate_probe.py phase1 30 30 --auto 6   # auto-pick 6 non-generic tags to watch
```

> 🔒 All four only call `NtQuerySystemInformation` queries and **read** driver binaries — no system modification, no network.

---

## Evidence & statement discipline

Same rules as the author's other forensics repo ([alibabaprotect-forensics](https://github.com/deserthouse/alibabaprotect-forensics)):

1. **Every conclusion ships with reproducible evidence** — command, raw output, or data table.
2. **Three statement grades**: ✅ **measured** (persisted raw data) / 🔎 **inferred** (reasoned from evidence, basis stated) / ⚠️ **historical observation** (seen but not persisted; re-verification method given). There are exactly two historical observations, both labeled: Finding #9 below, plus the flat-reading note inside doc 03.
3. **Correlation ≠ causation** — temporal coincidence is a lead, not a conclusion.
4. **Naming facts, not motives**: OGH is named because it is the proven common entry point of both leaks; Realtek's and NVIDIA's roles are stated per evidence, with no attribution of intent.

---

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md). In short:

- For diagnosis and technical research **on devices you own and administer** only.
- The author is **not affiliated** with any vendor mentioned.
- All data comes from **a single machine**; other models/driver versions may differ.
- Remediation steps modify system services — **assess and create a restore point first**.

## License

[MIT](LICENSE)
