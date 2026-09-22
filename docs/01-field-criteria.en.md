# 01 · Four Field Criteria: What the Official Tutorials Skip

**English** · [简体中文](01-field-criteria.md)

> **Scope**: the standard workflow (pull tags → watch what grows → findstr the driver) is fully covered by Microsoft docs and community articles — but following it verbatim **makes misjudgment easy**. This doc collects four criteria derived from real misjudgments; each one maps to a genuine misdiagnosis risk.

---

## Criterion 1: Ignore allocation counts — look at the **free rate**

This is the easiest trap. The `Alloc` column is meaningless on its own — normal system churn reaches **billions** of allocations.

Measured contrast (same machine, same snapshot):

| Tag | Allocations | Frees | **Free rate** | Usage | Verdict |
|---|---|---|---|---|---|
| `cckT` | **2,757,245,939** | 2,757,042,505 | **100.0%** | ~40 MB | High churn, **not a leak** |
| `RTLF` | 62,481 | 6,050 | **9.7%** | 530 MB | **Real leak** (56k objects never returned) |

> Judging by "huge allocation count" alone would falsely identify `cckT` as the leak source — 2.75 billion allocations, but 2.757 billion frees.

**Rule of thumb**: free rate < 90% is highly suspicious; < 50% is near-confirmation. But it **must** be combined with "is it growing over time" (see Case C: 3 allocs / 0 frees can still be a static hold).

---

## Criterion 2: The strongest post-remediation evidence is a **flat reading**, not "the average rate dropped"

Everyone does before/after comparisons (15 min vs 15 min). But "rate dropped from X to Y" can still be explained away by workload changes. **The stronger evidence form is perfect flatness**:

> Ten consecutive post-remediation readings (~1 min apart) **byte-identical** (58.8 MB, unmoved) — while no such flat interval ever appeared in the pre-remediation history.

Byte-identical means **allocation activity for that tag has stopped entirely** — much harder than "average growth declined", because averages can be explained by any fluctuation.

> Evidence-discipline note: the ten flat readings occurred during the remediation session and **the per-reading raw log was not persisted** (the saved CSV holds only three phase summaries). This repo cites it at the *historical observation* grade; the verdict rests on the persisted three-phase data (see doc 03).

---

## Criterion 3: Tag→driver mapping needs **boundary matching + hit counts**

The community-standard approach is `findstr /m "TAG" *.sys`. It has two traps, both stepped in for real:

### Trap 1: substring false positives

`findstr "Cont"` matches every driver containing `Content`, `Control`, … — measured: **579 files**. Four-character tags are too short; naive substring matching guarantees mass false positives.

### Trap 2: first match wins

`findstr /m` stops at the first hit. Measured: `NVRM` was once attributed to `nvpcf.sys` — the correct owner is `nvlddmkm.sys` (the 108 MB main driver was skipped).

### The fix (built into `scripts/pooltag.py`)

```text
Boundary matching: if the bytes adjacent to a hit are alphanumeric → reject
                   (the tag is part of a longer identifier)
Hit count:        report how many files matched
                   1 file   → attributable
                   dozens+  → the tag is a generic substring, not attributable
Chunked scanning: no size cap (do not skip the 108 MB nvlddmkm.sys),
                   8 MiB chunks + 16-byte overlap
```

Measured results: `ismc` → `iaStorAC.sys [1]` (attributable); `NVRM` → `nvlddmkm.sys, nvpcf.sys [2]`; `Cont` → `dxgkrnl.sys [1]` (false positives gone once boundary matching is on).

---

## Criterion 4: For steady-rate leaks, find the **caller** before blaming the driver

With steady growth (MB/h scale), the driver is usually just the **executor** — the real variable is **who is calling it on a fixed cadence**.

The one-liner that works:

```powershell
# Who loads the user-mode interface DLL the driver exposes?
tasklist /m nvml.dll
```

In Case B, exactly **one** process system-wide had `nvml.dll` (NVIDIA's user-mode query library) loaded — OGH's background monitor. Stopping it stopped the leak; the driver itself was fine.

**Reasoning chain**: a third-party panel polls GPU status at a fixed cadence → every query makes the driver allocate kernel objects → the caller's query pattern outpaces frees. **Treat the caller; the driver needs no change** — reinstalling the GPU driver any number of times won't help.

---

## Appendix: two measurement disciplines

| Discipline | Why |
|---|---|
| **≥ 15-minute windows per phase** | An 8-minute window on a 6 MB/h rate yields ~0.8 MB of delta — near noise, easy to conclude wrongly |
| **No disk scans / heavy I/O while rate-probing** | File-I/O tags (`File`/`cckT`/`FMsl`) get inflated and pollute the data; scanning for the leak is itself an interference source |
| Watch only **driver-unique tags** | Generic tags (`File`/`Thre`/`Even`/`Etw*`) are hypersensitive to system activity — never use them as leak indicators |
| **Re-measure post-remediation with identical methodology** | Same script, same window, same time of day — otherwise not comparable |

---

Next: [02 · Case A: the orphan-driver leak (RTLF)](02-case-rtlf-orphan-driver.en.md)
