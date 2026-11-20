# OMEN Gaming Hub Pool-Leak Forensics

One Windows 11 OMEN laptop reached a 3.9 GB nonpaged pool. This casebook compares the NVRM and RTLF pool tags, the candidate drivers and the readings after mitigation. The proposed polling mechanism remains unconfirmed.

[Symptom check](#is-this-the-problem-youre-seeing) · [Findings](#findings-at-a-glance) · [Case documents](#docs)

**English** · [简体中文](README.zh-CN.md) · [![License: MIT](https://img.shields.io/badge/License-MIT-0078D4.svg)](LICENSE)

## Contents

<details>
<summary>Show all sections</summary>

- [What this is](#what-this-is)
- [Is this the problem you're seeing?](#is-this-the-problem-youre-seeing)
- [Findings at a glance](#findings-at-a-glance)
- [Docs](#docs)
- [Scripts (all read-only)](#scripts-all-read-only)
- [Evidence & statement discipline](#evidence--statement-discipline)
- [Disclaimer](#disclaimer)

</details>

---

## What this is

For mitigation steps and follow-up measurements, see the [case guide](docs/05-remediation-and-alternatives.en.md).

Task Manager showed no process that explained the pool growth. Rebooting reduced the total temporarily.

The table compares the two pool tags and the current working hypotheses.

| | Case B · NVRM growth | Case A · RTLF growth |
|---|---|---|
| Pool tag | `NVRM` | `RTLF` |
| Peak | **1.77 GB** (accumulated over 71 h) | **530 MB** |
| Candidate component | NVIDIA kernel driver (`nvlddmkm`) | Realtek NDIS lightweight filter (`rtf64x64.sys`) |
| **OGH's role** | **The caller**: its background process was the *only* `nvml.dll` consumer system-wide | **The installer**: shipped it as a Network Booster dependency and doesn't remove it on uninstall |
| Working hypothesis | The driver serves requests; a monitor polling on a fixed cadence makes allocations outpace frees (inferred from the only-consumer observation plus the stop-contrast; driver-side allocation paths were not traced) | No matching user-mode caller was observed in the sampling window. The allocation path inside the driver remains untraced. |
| Fix | Stop the caller (or uninstall OGH) | Disable/delete the `rtf64` service — unchecking the filter is **not** enough (`FilterRunType=1`, `StartType=1`) |

> ⚠️ **Don't conflate the two**: in Case B the stop-contrast ties the growth to the caller's polling (driver-side responsibility was not separately assessed); in Case A the driver itself leaks with no caller at all and OGH merely delivered it.

A third tag, `ismc` (317 MB), was proven **not a leak** — yet it is documented too (see doc 04): its free rate is 0%, making it look *more* like a leak than the real ones. Without this counter-example, the free-rate criterion alone would misidentify it.

**The standard workflow is not repeated here**: see the official docs — [Use PoolMon to find a kernel-mode memory leak](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/using-poolmon-to-find-a-kernel-mode-memory-leak) and [PoolMonX](https://github.com/zodiacon/PoolMonX). This repo covers only what they **don't**: when you're about to misjudge, and which criteria prevent it.

---

## Is this the problem you're seeing?

If both of these match, it probably is:

1. Task Manager → Performance → Memory shows a **nonpaged pool** in the GB range — resets on reboot, then slowly climbs back;
2. OMEN Gaming Hub is (or was) installed.

One command tells you which case you have (the [scripts](scripts/) are read-only; Python as admin):

```bash
python scripts/pooltag.py snapshot.json
```

In the top list: `RTLF`, or `NVRM` that is growing → follow the [remediation guide](docs/05-remediation-and-alternatives.en.md) (uninstall OGH, remove the leftover driver, verify); for why, see [doc 02](docs/02-case-rtlf-orphan-driver.en.md) / [doc 03](docs/03-case-nvrm-polling-caller.en.md). A big tag that is *not* growing — check [doc 04](docs/04-case-ismc-benign.en.md) first: a large allocation is not necessarily a leak.

> The findings table below is for readers who want to verify the evidence — skip it if you just want the fix.

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

 both leak sources were located and remediated — `RTLF` (530 MB) is a network-filter driver OGH bundles, leaves behind on uninstall, and leaks with no caller at all; `NVRM` (1.77 GB over 71 hours) tracked OGH's background monitor polling the NVIDIA driver at a fixed cadence (stop-contrast proven; the driver-side mechanism is inferred). The fix = uninstall OGH + manually disable the rtf64 driver + reboot — see the [remediation guide](docs/05-remediation-and-alternatives.en.md); the third big block, `ismc` (317 MB), is not a leak — leave it alone.

---

## Docs

| Doc | What's in it |
|---|---|
| [01 · Four field criteria](docs/01-field-criteria.en.md) · [中文](docs/01-field-criteria.md) | **Methodology**: free rate, flat readings, mapping false positives, caller attribution — the parts official tutorials skip |
| [02 · Case A: orphan driver](docs/02-case-rtlf-orphan-driver.en.md) · [中文](docs/02-case-rtlf-orphan-driver.md) | renamed-framework tracing (PDB), dead call chain, why "unchecking" fails |
| [03 · Case B: polling caller](docs/03-case-nvrm-polling-caller.en.md) · [中文](docs/03-case-nvrm-polling-caller.md) | one command finds the poller, stop it and the leak stops |
| [04 · Case C: big blob ≠ leak](docs/04-case-ismc-benign.en.md) · [中文](docs/04-case-ismc-benign.md) | counter-example: why a 317 MB block was left alone |
| [05 · Remediation](docs/05-remediation-and-alternatives.en.md) · [中文](docs/05-remediation-and-alternatives.md) | operational guide: uninstall OGH, remove the leftover rtf64 driver, verify, alternatives to OGH features |
| [06 · Appendix: open-source alternatives](docs/06-open-source-alternatives.en.md) · [中文](docs/06-open-source-alternatives.md) | status, model-support boundaries, benefits and risks of each alternative |
| [evidence/](evidence/) | sanitized raw evidence (snapshots, rate CSV, INF excerpts, PDB extraction) |
| [scripts/](scripts/) | read-only diagnostic tools (no WDK; Python ctypes straight into the kernel API) |
| [DISCLAIMER.md](DISCLAIMER.md) | scope statement |

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

> All four only call `NtQuerySystemInformation` queries and **read** driver binaries — no system modification, no network.

---

## Evidence & statement discipline

The writing of this repo follows four constraints:

1. **Every conclusion ships with reproducible evidence** — command, raw output, or data table.
2. **Three statement grades**: ✅ **measured** (persisted raw data) / **inferred** (reasoned from evidence, basis stated) / ⚠️ **historical observation** (seen but not persisted; re-verification method given). There are exactly two historical observations, both labeled: Finding #9 below, plus the flat-reading note inside doc 03.
3. **Correlation ≠ causation** — temporal coincidence is a lead, not a conclusion.
4. **Naming facts, not motives**: OGH is named because it is the proven common entry point of both leaks; Realtek's and NVIDIA's roles are stated per evidence, with no attribution of intent.

---

## Disclaimer

See [DISCLAIMER.md](DISCLAIMER.md). In short:

- For diagnosis and technical research **on devices you own and administer** only.
- The author is **not affiliated** with any vendor mentioned.
- All data comes from **a single machine**; other models/driver versions may differ.
- Remediation steps modify system services — **assess and create a restore point first**.

## AI disclosure

This project contains no human ingredients. AI assisted with analysis and drafting. The maintainer supplied the device evidence, reviewed the findings and approved publication. [Full disclosure](DISCLAIMER.md#on-ai-assistance).

## License

[MIT](LICENSE)
