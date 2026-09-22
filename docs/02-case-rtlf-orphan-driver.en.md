# 02 · Case A: The Orphan-Driver Leak (RTLF, 530 MB)

**English** · [简体中文](02-case-rtlf-orphan-driver.md)

> **Key point**: uninstalling the software ≠ removing the driver. This driver kept leaking with **no process calling it at all**, and the software that brought it in doesn't take it away on uninstall.

---

## 1. Symptom

`RTLF` ranked #2 among nonpaged-pool tags: **530 MB**, 62,481 allocations / 6,050 frees — a **9.7% free rate** (Criterion 1, direct hit). 56k kernel objects never returned.

Shape: **one-time bulk allocation + no significant growth over time** (the allocating is long done; it just never gives back).

## 2. Attribution: tag → driver

`RTLF` matches `rtf64x64.sys` in `C:\Windows\System32\drivers` (hit count 1 — attributable).

## 3. What this driver actually is

### 3.1 Identity (INF and service registry)

| Field | Value |
|---|---|
| Service name | `rtf64` |
| Display name | Realtek LightWeight Filter (NDIS6.40) |
| INF | `oem43.inf`, Provider = Realtek, DriverVer = 2025-11-28, 3.15.1128.2025 |
| Start | `StartType=1` (**loaded at system boot**), LoadOrderGroup = NDIS |
| Class | NetService (NDIS lightweight filter, LWF) |

### 3.2 Real identity: a rebranded WinpkFilter V2 (PDB provenance)

The debug-symbol path embedded in the driver binary (ASCII string, extracted from the on-disk file):

```
D:\WorkingSpace\GitServer\Dragon\WinpkFilter_V2\kernel\LWF\sysw10x64\Release\x64\rtf64x64.pdb
```

Linker-written PDB paths are rarely cleaned up. It reveals two things:

1. The driver originates from the **WinpkFilter** V2 kernel LWF project (a commercial NDIS middleware/filter framework common in bandwidth-control products);
2. The vendor rebranded the build but **forgot to change the build path** — the `rtf64x64` name is packaging; the project itself is WinpkFilter.

> Using PDB paths to detect "rebranded something else" works remarkably well — vendors renaming products routinely miss this.

### 3.3 How it got onto the system

`rtf64` ships as a dependency of **OMEN Gaming Hub's "Network Booster"** feature: installing/enabling that feature pulls the filter into the network stack via INF. Multiple independent sources corroborate this (HP support-community threads, community blogs), consistent with this machine's timeline.

**Key point**: the INF Provider is Realtek and the driver is Realtek-signed — **the driver comes from Realtek; OGH merely delivered it**. Two parties, two roles — don't merge them.

## 4. The decisive evidence: the call chain is dead

The normal usage chain for an NDIS filter:

```
User-mode control program
    ↓ loads
Comms-layer DLL (System32\RtFDrvIOCtrl.dll, WinpkFilter's CNdisApi wrapper)
    ↑ loads
Core DLL (System32\RtBWCtrl.dll, bandwidth-control core)
    ↑ loads
OGH's NetworkCap module
```

Measured (at remediation time):

```
tasklist /m RtBWCtrl.dll      → no matches
tasklist /m RtFDrvIOCtrl.dll  → no matches
```

**No process on the system loaded either DLL** — no user-mode program was "using" this driver. It sits in the network stack, auto-loads at boot, holds 530 MB of pool — and **nobody ever calls it**.

> That is what "orphan-driver leak" means: the leak lives in the driver itself (or its binding path), independent of callers. Contrast with Case B (no caller → no leak).

## 5. Why "unchecking" fails for some users (INF topology evidence)

Binding topology of `oem43.inf` (measured excerpt, see evidence/rtf64-inf.txt):

```
UpperRange   = "noupper"      ← offers no interface upward
LowerRange   = "nolower"      ← depends on no interface below
FilterMediaTypes = "ethernet, wan, ppip"
FilterRunType = 1             ← the filter must run before protocol binding
StartType = 1                 ← loaded at system boot (standalone SCM service)
```

Three corollaries:

1. **`noupper`/`nolower` = pure bypass layer**: whether TCP/IP binds to it doesn't affect connectivity ⇒ disabling it **cannot break the network** — low remediation risk;
2. **`FilterRunType=1` + `StartType=1`**: it is a **standalone kernel service** registered with SCM, auto-loaded at boot. Unchecking "Realtek LightWeight Filter" in adapter properties only removes the binding — **the service still loads**. This explains the HP-community reports of "uncheck didn't help";
3. **OGH uninstall leaves it behind**: INF-installed drivers belong to pnputil/the driver store; OGH's uninstaller never touches them.

## 6. Remediation and verification

```powershell
# Admin required; after reboot rtf64 no longer loads
sc.exe config rtf64 start= disabled
# (more thorough: sc delete rtf64; or pnputil /delete-driver oem43.inf /uninstall)
```

Post-remediation reboot, re-measured:

| Metric | Before | After |
|---|---|---|
| `RTLF` usage | 530 MB | **0** |
| Network | — | Normal (bypass layer, as expected) |

## 7. Historical observation (not persisted)

Before remediation, the device object `\Device\RTF64` was observed with a DACL granting **Everyone (WD) read/write** — any local process could talk to the driver directly. The observation happened during the remediation-day session and **was not persisted as an evidence file**; after remediation the driver no longer loads and the device object is gone. Re-verification method (if ever needed): temporarily `sc start rtf64`, then read the SDDL of `\Device\RTF64` via `NtOpenFile + NtQuerySecurityObject`. Cited at the **historical observation** grade per this repo's evidence discipline; not part of the conclusion chain.

## 8. Evidence list

| Evidence | File |
|---|---|
| Leak snapshot (9.7% free rate) | `evidence/pooltag-before.json` (RTLF entry) |
| Post-remediation zero | `evidence/pooltag-after.json` (RTLF absent) |
| PDB path raw string | `evidence/rtf64-pdb.txt` |
| Service registry + Parameters | `evidence/rtf64-service.txt` |
| INF key sections + reading | `evidence/rtf64-inf.txt` |
| Dead call chain (tasklist output) | `evidence/rtf64-no-callers-and-nvml-callers.txt` |

---

Prev: [01 · Four Field Criteria](01-field-criteria.en.md) ｜ Next: [03 · Case B: the polling-caller leak](03-case-nvrm-polling-caller.en.md)
