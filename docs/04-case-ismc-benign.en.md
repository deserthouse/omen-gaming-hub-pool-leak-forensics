# 04 · Case C (counter-example): Big Blob ≠ Leak (ismc, 317 MB)

**English** · [简体中文](04-case-ismc-benign.md)

> **Key point**: a big number in the Top list isn't necessarily leaking. Criterion 1's free rate flags it as "suspicious" (0%), but it may be a **one-time startup allocation held statically** — remediating it gains nothing and risks something.

---

## 1. Symptom

`ismc` held **317 MB**, perennially #3 in the Top list. **3** allocations, **0** frees — by the free-rate criterion (0% < 50%) "near-confirmed"?

**Not yet conclusive.**

## 2. The decisive check: does it grow over time

Two snapshots ~1 hour apart:

| Time | ismc usage | Allocations |
|---|---|---|
| T1 | 316.9 MB | 3 |
| T2 | 321.1 MB | 3 |

**Allocation count unchanged, usage essentially flat** (±4 MB is normal pool-fragmentation wobble). This is not a leak — a leak is *defined* by sustained growth; this is **three one-time startup allocations held ever since**.

> Completing Criterion 1: the free rate is for screening; *"growth over time"* is what confirms. Use them together.

## 3. Attribution and nature

`ismc` → `iaStorAC.sys [1]` (sole hit) — Intel RST (Rapid Storage Technology). Intel's own community has confirmed `ismc` as the Intel Storage Management Component tag, with other users reporting large footprints.

What makes this machine special (and the decision decisive):

> **The RST controller has no physical disks attached** — the system drive is on `stornvme`, everything else is USB storage. Only two RST software components (the management UI) remain running; the 317 MB is their startup working allocation.

## 4. The decision: why leave it alone

| Option | Cost | Gain |
|---|---|---|
| Disable RST services/driver | Controller residue in the device tree; a future SATA disk or config change might not come up; the memory mostly doesn't return to usable pool anyway | 0.3 GB |
| **Leave it** | none | — |

317 MB in exchange for a *possible* storage-stack anomaly is a negative trade. **Verdict: record, monitor, don't touch.**

## 5. Methodology distilled

Together with Cases A and B this forms a complete decision matrix:

| Shape | Free rate | Grows over time | Verdict | Action |
|---|---|---|---|---|
| Case B (NVRM) | 98% | ✅ steady growth | Leak (net-accumulation) | find/stop the caller |
| Case A (RTLF) | 9.7% | ❌ (allocated long ago, held) | Leak (held-allocation) | disable the driver service |
| **Case C (ismc)** | **0%** | **❌** | **Static hold, not a leak** | **none** |

> The reminder from all three: a big Top-list number answers "who holds memory", never "should you touch it". Run all three dimensions — **free rate + growth + remediation payoff** — before acting.

## 6. Evidence list

| Evidence | File |
|---|---|
| T1 snapshot | `evidence/pooltag-before.json` (ismc entry: 316.9 MB / 3 allocs) |
| T2 snapshot | `evidence/pooltag-after.json` (ismc entry: 321.1 MB / 3 allocs) |
| Attribution | `evidence/tag-to-driver.txt` (ismc → iaStorAC.sys [1]) |

---

Prev: [03 · Case B: the polling-caller leak](03-case-nvrm-polling-caller.en.md)
