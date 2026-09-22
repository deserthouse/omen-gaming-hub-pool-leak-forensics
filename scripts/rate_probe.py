#!/usr/bin/env python3
"""
rate_probe.py — measure the *rate of change* of kernel pool tags over a fixed window.

A single snapshot tells you "how big"; it cannot tell you "is it growing".
This tool samples repeatedly and reports MB/hour, which is what you need for
A/B verification of a suspected leak source.

Read-only.

Usage:
    # watch specific tags, 15 minutes (30 rounds x 30 s)
    python rate_probe.py baseline 30 30 --tags NVRM,NvLH,NvKP

    # auto-pick the top 6 non-generic tags
    python rate_probe.py baseline 30 30 --auto 6

    # short smoke test
    python rate_probe.py smoke 3 5 --tags NVRM

Notes on window length (learned the hard way):
    A leak running at ~6 MB/h only produces ~0.8 MB in 8 minutes, which is close
    to reading noise. Use >= 15 minutes per phase.
    Also keep the workload comparable between phases: idle vs busy can differ by
    ~4x. And do not run disk-heavy work during a phase -- that inflates generic
    tags (File / ccm* / FMsl) and pollutes the comparison.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import csv
import os
import time
from datetime import datetime

ntdll = ctypes.WinDLL("ntdll.dll")
SystemPoolTagInformation = 0x16

# Tags that reflect general system activity, not a single driver.
# They must not be used as a leak criterion.
GENERIC_PREFIXES = (
    "File", "Thre", "Vad", "Even", "Irp", "Pool", "Cont", "Mm", "Etw", "Hal",
    "Tcp", "Udp", "ND", "Afd", "Nt", "Sc", "Se", "Ob", "Ke", "Ps", "Cc", "Cc",
    "Ntf", "Lfs", "Clf", "Flt", "sm", "Vi", "Al", "Io", "Re", "Tc", "Tdx",
    "Wf", "Wm", "Wn", "Wr", "Xh", "St", "Sp", "R", "V", "Dx", "Ac", "Ar",
)
GENERIC_EXACT = {
    "Pool", "Irp ", "File", "Thre", "Even", "Vad ", "Cont", "ConT", "HalD",
    "EtwB", "EtwR", "EtwS", "dump", "hash", "pool", "Wait", "Time", "Proc",
}


class SYSTEM_POOLTAG(ctypes.Structure):
    _fields_ = [
        ("TagUlong", wt.ULONG),
        ("PagedAllocs", wt.ULONG),
        ("PagedFrees", wt.ULONG),
        ("PagedUsed", ctypes.c_size_t),
        ("NonPagedAllocs", wt.ULONG),
        ("NonPagedFrees", wt.ULONG),
        ("NonPagedUsed", ctypes.c_size_t),
    ]


def snapshot():
    size = 1 << 21
    buf = ctypes.create_string_buffer(size)
    ret = wt.ULONG(0)
    st = ntdll.NtQuerySystemInformation(
        SystemPoolTagInformation, buf, size, ctypes.byref(ret))
    if st != 0:
        raise RuntimeError("NtQuerySystemInformation failed 0x%08X" % (st & 0xFFFFFFFF))

    entry = ctypes.sizeof(SYSTEM_POOLTAG)
    n = min(int.from_bytes(buf.raw[0:8], "little"), (ret.value - 8) // entry)
    tags, total = {}, 0
    for i in range(n):
        t = SYSTEM_POOLTAG.from_buffer_copy(buf.raw, 8 + i * entry)
        tag = "".join(chr(c) if 32 <= c < 127 else "?"
                      for c in t.TagUlong.to_bytes(4, "little"))
        tags[tag] = t.NonPagedUsed
        total += t.NonPagedUsed
    return tags, total


def is_generic(tag):
    if tag in GENERIC_EXACT:
        return True
    return any(tag.startswith(p) for p in GENERIC_PREFIXES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label", help="phase label, e.g. before / after / phase_A")
    ap.add_argument("rounds", nargs="?", type=int, default=30)
    ap.add_argument("interval", nargs="?", type=int, default=30, help="seconds between rounds")
    ap.add_argument("--tags", default="", help="comma-separated pool tags to watch")
    ap.add_argument("--auto", type=int, default=0,
                    help="auto-pick the top N non-generic tags")
    ap.add_argument("--log", default="rate_probe_log.csv")
    args = ap.parse_args()

    watch = [t.strip() for t in args.tags.split(",") if t.strip()]

    first = last = None
    t0 = t1 = None
    picked = None

    for r in range(args.rounds):
        tags, total = snapshot()
        if first is None:
            first, t0 = (dict(tags), total), time.time()
            if not watch and args.auto:
                cand = sorted(((v, k) for k, v in tags.items()
                               if v > 0 and not is_generic(k)), reverse=True)
                picked = [k for _, k in cand[:args.auto]]
                watch = picked
                print("auto-picked tags: %s" % ", ".join(watch))
        last, t1 = (dict(tags), total), time.time()

        show = "  ".join("%s=%.2fMB" % (t, tags.get(t, 0) / 1048576) for t in watch)
        print("[%s] %2d/%d  %s  %s  total=%.3fGB" %
              (args.label, r + 1, args.rounds, datetime.now().strftime("%H:%M:%S"),
               show, total / 1073741824), flush=True)

        if r < args.rounds - 1:
            time.sleep(args.interval)

    hours = (t1 - t0) / 3600.0
    assert hours > 0

    def rate(a, b):
        return (b - a) / 1048576 / hours

    print()
    print("=" * 84)
    print("phase %s   duration %.1f min" % (args.label, hours * 60))
    print("%-8s %12s %12s %14s %10s" % ("TAG", "START_MB", "END_MB", "MB_PER_HOUR", "FREE%"))
    for t in watch:
        a, b = first[0].get(t, 0), last[0].get(t, 0)
        print("%-8s %12.2f %12.2f %14.1f" % (t, a / 1048576, b / 1048576, rate(a, b)))
    print("-" * 84)
    print("%-8s %12.2f %12.2f %14.1f" %
          ("TOTAL", first[1] / 1048576, last[1] / 1048576, rate(first[1], last[1])))
    print()
    print("Interpretation: a phase that drops the rate to <1 MB/h while the")
    print("previous phase showed a steady climb identifies the source.")
    print("A FLAT reading (identical bytes across many consecutive samples) is")
    print("stronger evidence than a merely lower average.")

    newfile = not os.path.exists(args.log)
    with open(args.log, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if newfile:
            w.writerow(["timestamp", "phase", "tag", "start_mb", "end_mb", "mb_per_hour",
                        "total_start_mb", "total_end_mb", "total_mb_per_hour", "minutes"])
        for t in watch:
            w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), args.label, t,
                        round(first[0].get(t, 0) / 1048576, 2),
                        round(last[0].get(t, 0) / 1048576, 2),
                        round(rate(first[0].get(t, 0), last[0].get(t, 0)), 1),
                        round(first[1] / 1048576, 2), round(last[1] / 1048576, 2),
                        round(rate(first[1], last[1]), 1), round(hours * 60, 1)])
    print("appended to %s" % args.log)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\ninterrupted")
    except Exception as e:
        import sys
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
