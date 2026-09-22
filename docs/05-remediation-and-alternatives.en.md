# 05 · Remediation: Uninstall and Alternatives

**English** · [简体中文](05-remediation-and-alternatives.md)

> This is the operational guide for readers who have confirmed the problem described in this repo. Every step cites the measured finding it rests on; the alternatives section is **not verified on this machine** and is labeled as such. If the command line is unfamiliar, hand this repo's link to your AI assistant and have it walk you through, or execute for you — every step carries expected output to verify against.

---

## 1. Confirm before you act

This remediation targets exactly the two confirmed cases (`RTLF` leak / steady `NVRM` growth). If you haven't confirmed yet, go back to the [symptom-check section in the README](../README.md) — one command distinguishes them. **Do not uninstall or disable anything before confirming.**

---

## 2. Step 1: uninstall OMEN Gaming Hub

Settings → Apps → Installed apps → search **OMEN Gaming Hub** → Uninstall.

- **Basis**: the Case-B leak source was OGH's background process polling the GPU at a fixed cadence (measured: the system's sole `nvml.dll` consumer; the leak stopped when it stopped — see doc 03). Uninstalling is the most thorough way to stop it.
- This step assumes you don't need OGH's other features; if you do, review the alternatives in §5 first.

---

## 3. Step 2: remove the leftover rtf64 driver (OGH's uninstaller won't)

**Measured (Finding #8)**: `rtf64` is a standalone SCM service that OGH's uninstaller never touches — **with Step 1 alone, the 530 MB of RTLF stays**. As admin:

```powershell
sc.exe config rtf64 start= disabled
```

Then **reboot**. After reboot the driver no longer loads (measured: `RTLF` at zero — see doc 02 §6).

- Unchecking "Realtek LightWeight Filter" in adapter properties does **not** work (it only removes the binding; the service still loads) — mechanism in doc 02 §5.
- To also remove the driver file (optional, more thorough):
  ```powershell
  sc.exe delete rtf64
  pnputil /delete-driver oem43.inf /uninstall
  ```
  (oem43.inf is this machine's number and may differ on yours: find the Realtek-provider entry with `pnputil /enum-drivers` first.)

---

## 4. Step 3: verify it worked

After reboot, re-measure with this repo's script (read-only, admin):

```bash
python scripts/pooltag.py after.json
```

| What to check | Expected |
|---|---|
| `RTLF` | **absent or 0** (measured contrast: 530 MB before → 0 after) |
| `NVRM` | present but **no longer growing** (stable at ~59 MB after remediation; re-measure an hour later and compare) |
| Network | normal (`rtf64` is a bypass layer — disabling it cannot break connectivity — see doc 02 §5 corollary 1) |

---

## 5. Alternatives

⚠️ **This section is not verified on this machine** — generic replacements by function slot; for items marked "check first", confirm support for your model.

| OGH feature | Replacement | Notes |
|---|---|---|
| Performance-mode switching | **Windows power plans** (Balanced / High performance / Ultimate Performance) | built in, zero install; switchable via `powercfg -setactive` |
| Fan curves | **[FanControl](https://github.com/Rem0o/FanControl.Releases)** (open source) | check first: depends on whether your board's sensors are detected |
| Hardware monitoring | Task Manager / LibreHardwareMonitor (open source) | **read the warning below** |
| RGB lighting | **OpenRGB** (open source) / Windows 11 Dynamic Lighting | check first: [OpenRGB supported devices](https://openrgb.org) |
| Remote game streaming | Steam Link / Moonlight (open source) | unrelated to the kernel; not implicated in these cases |

> ⚠️ **Read before installing any replacement monitoring panel (this repo's core lesson)**: Case B's mechanism was "a monitor polls the GPU at a fixed cadence → driver allocations outpace frees". **Any** software that queries the GPU on a fixed schedule (RGB effects, FPS overlays, game assistants) can become the next such caller. Prefer tools with an adjustable polling interval, set it long, or simply install fewer panels.

---

Prev: [04 · Case C: big blob ≠ leak](04-case-ismc-benign.en.md)
