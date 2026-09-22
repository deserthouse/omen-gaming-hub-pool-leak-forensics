# 03 · Case B: The Polling-Caller Leak (NVRM, 1.77 GB)

[中文版](03-case-nvrm-polling-caller.md)

**Key point**: in a steady-rate leak the driver is often an innocent executor. Spend 10 seconds finding *who calls it* — it may save you a pointless driver reinstall.

---

## 1. Symptom

The `NVRM` tag grew steadily: **6–8 MB/h idle, up to 29 MB/h under use**, reaching **1.77 GB** over 71 hours. 272M allocations / 267M frees (98% free rate — the classic shape of a steady-accumulation leak: almost everything is returned; **the net rate is the problem**).

> Contrast with Case A: A is "allocated, never returned" (9.7% free rate); B is "returned, but allocated faster" (98% free rate, sustained net growth). Two shapes, two investigation strategies: for the former ask "who holds"; for the latter ask "who drives the traffic".

## 2. Attribution

`NVRM` matches two drivers: `nvlddmkm.sys` (primary) and `nvpcf.sys` — the NVIDIA GPU kernel drivers (hit count 2, no false positives after boundary matching).

## 3. The key move: find the caller, not the driver

The GPU driver doesn't load itself down for no reason. NVIDIA exposes a user-mode query interface, `nvml.dll` (NVML — the same library nvidia-smi is built on). **Whoever loads it is querying the GPU at some cadence**:

```powershell
tasklist /m nvml.dll
```

Measured output (remediation day):

```
Image Name                   PID    Modules
=========================================
OmenCommandCenterBackgrou    44468  nvml.dll
```

**Exactly one process system-wide**: OMEN Gaming Hub's background process (331 MB working set, resident since boot). Hardware-monitor panels poll GPU utilization/temperature/clocks on a fixed cadence — every query goes through NVML into the driver and produces kernel-pool allocations.

## 4. Remediation and verification (A/B contrast)

Remediation: terminate that process (its background services were later uninstalled along with OGH — the user didn't need OGH anyway).

Three-phase rate probe (`scripts/rate_probe.py`, CSV persisted):

| Phase | NVRM usage | Note |
|---|---|---|
| Baseline (probe self-check) | 59.09 MB | post-remediation |
| 12.3-minute window | 59.99 MB | after killing the process |
| Follow-up | 59.25 MB | stable at ~59 MB |

Post-remediation `NVRM` held at **~59 MB with no growth**; after reboot it started from a clean baseline with no recurrence (contrast the pre-remediation slope: 1.77 GB over 71 hours).

### ⚠️ Historical observation (not persisted)

During the remediation session, **ten consecutive byte-identical readings** were observed (59.25 MB unchanged, ~1 min apart) — the "flat reading" strongest-evidence form described in Criterion 2. The per-reading log was not persisted (the saved CSV holds only the three phase summaries above); cited at the **historical observation** grade. The "growth stopped" verdict rests on the persisted three-phase data.

## 5. Conclusions and boundaries

| Statement | Grade |
|---|---|
| OGH's background process was the system's only nvml.dll consumer | **measured** |
| NVRM stopped growing after that process was terminated | **measured** (three-phase data) |
| The leak was polling-driven (call cadence → allocation rate) | **inferred** (no stack sampling done; "to nail the mechanism you'd want a WPR stack sample", see 01 appendix) |
| Is the NVIDIA driver "at fault" here? | The driver serves requests; **treat the caller**, leave the driver alone |

## 6. Differences from prior community reports

Existing NVRM leak reports (WSL nvidia-smi triggers, certain Game Ready driver builds) all attribute the leak to **the driver itself or a specific trigger tool**, with "change driver version" as the fix. This case's increment: **in an ordinary desktop environment, a third-party monitoring panel's polling alone can accumulate a leak** — and a single `tasklist /m` locates the caller. Check the caller before touching the driver.

## 7. Evidence list

| Evidence | File |
|---|---|
| Leak accumulation (1.77 GB) | `evidence/pooltag-before.json` (NVRM entry) |
| Sole caller (tasklist /m nvml.dll) | `evidence/rtf64-no-callers-and-nvml-callers.txt` |
| Three-phase remediation contrast | `evidence/nvrm-rate-probe.csv.txt` |
| Post-remediation stability (59 MB) | `evidence/pooltag-after.json` (NVRM entry) |

---

Prev: [02 · Case A: the orphan-driver leak](02-case-rtlf-orphan-driver.en.md) ｜ Next: [04 · Case C: big blob ≠ leak](04-case-ismc-benign.en.md)
