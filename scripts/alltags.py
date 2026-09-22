#!/usr/bin/env python3
"""
alltags.py — dump EVERY kernel pool tag to JSON, so you can query any tag later.

pooltag.py only prints the top N. This dumps all ~3900 entries (≈2100 with
non-zero nonpaged usage) so you can grep/aggregate afterwards without needing
to re-sample at the moment of interest.

Read-only.

Usage:
    python alltags.py alltags.json
    python alltags.py alltags.json --prefix-preview NVRM,Nv,sm,FLT
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import sys

ntdll = ctypes.WinDLL("ntdll.dll")
SystemPoolTagInformation = 0x16


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

    tags = {}
    for i in range(n):
        t = SYSTEM_POOLTAG.from_buffer_copy(buf.raw, 8 + i * entry)
        tag = "".join(chr(c) if 32 <= c < 127 else "?"
                      for c in t.TagUlong.to_bytes(4, "little"))
        tags[tag] = {
            "np": t.NonPagedUsed,
            "np_alloc": t.NonPagedAllocs,
            "np_free": t.NonPagedFrees,
            "p": t.PagedUsed,
            "p_alloc": t.PagedAllocs,
            "p_free": t.PagedFrees,
        }
    return tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default="alltags.json")
    ap.add_argument("--prefix-preview", default="",
                    help="comma-separated prefixes to summarise, e.g. NVRM,Nv,sm")
    args = ap.parse_args()

    tags = snapshot()
    np_total = sum(v["np"] for v in tags.values())
    p_total = sum(v["p"] for v in tags.values())

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({
            "np_total": np_total,
            "p_total": p_total,
            "tag_count": len(tags),
            "nonzero_np": sum(1 for v in tags.values() if v["np"] > 0),
            "tags": tags,
        }, fh, ensure_ascii=False)

    print("tag entries      : %d" % len(tags))
    print("nonzero nonpaged : %d" % sum(1 for v in tags.values() if v["np"] > 0))
    print("nonpaged total   : %.3f GiB" % (np_total / 1024 ** 3))
    print("paged total      : %.3f GiB" % (p_total / 1024 ** 3))
    print("written          : %s" % args.out)

    if args.prefix_preview:
        print()
        print("=== aggregate by prefix ===")
        for pref in args.prefix_preview.split(","):
            pref = pref.strip()
            if not pref:
                continue
            members = [(t, v) for t, v in tags.items()
                       if t.startswith(pref) and v["np"] > 0]
            tot = sum(v["np"] for _, v in members)
            pct = (tot / np_total * 100) if np_total else 0
            print("%-8s %14d bytes  %6.2f%%  of nonpaged pool   (%d tags)" %
                  (pref, tot, pct, len(members)))
            for t, v in sorted(members, key=lambda kv: -kv[1]["np"])[:8]:
                print("     %-6s %12d" % (t, v["np"]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
