#!/usr/bin/env python3
"""
diffall.py — compare two pool tag snapshots (from alltags.py / pooltag.py).

Answers: between snapshot A and snapshot B, which tags grew, which shrank,
which are brand new, which disappeared.

Read-only.

Usage:
    python diffall.py before.json after.json                 # summary + top deltas
    python diffall.py before.json after.json --top 20
    python diffall.py before.json after.json --tag NVRM      # one tag, detailed
"""
import argparse
import json
import sys


def load(p):
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh)
    return d["tags"], d.get("np_total", sum(v["np"] for v in d["tags"].values())), d


def fmt_mb(b):
    return "%+.2f MB" % (b / 1048576)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    A, np_a, _ = load(args.a)
    B, np_b, _ = load(args.b)

    print("=== totals ===")
    print("  %-14s nonpaged %.3f GiB   tags %d" % (args.a, np_a / 1024 ** 3, len(A)))
    print("  %-14s nonpaged %.3f GiB   tags %d" % (args.b, np_b / 1024 ** 3, len(B)))
    print("  delta          %s" % fmt_mb(np_b - np_a))
    print()

    if args.tag:
        print("=== tag %s ===" % args.tag)
        for name, D in ((args.a, A), (args.b, B)):
            v = D.get(args.tag)
            if not v:
                print("  %-14s (absent)" % name)
                continue
            free_pct = (v["np_free"] / v["np_alloc"] * 100) if v["np_alloc"] else 0.0
            print("  %-14s np=%d  alloc=%d  free=%d  free%%=%.1f%%  gap=%d" %
                  (name, v["np"], v["np_alloc"], v["np_free"], free_pct,
                   v["np_alloc"] - v["np_free"]))
        return

    rows = []
    for t in set(A) | set(B):
        x = A.get(t, {}).get("np", 0)
        y = B.get(t, {}).get("np", 0)
        rows.append((y - x, t, x, y))

    print("=== biggest increases ===")
    for d, t, x, y in sorted(rows, reverse=True)[:args.top]:
        fa = A.get(t, {}).get("np_alloc", 0)
        ff = A.get(t, {}).get("np_free", 0)
        fb = B.get(t, {}).get("np_alloc", 0)
        ffb = B.get(t, {}).get("np_free", 0)
        da, df = fb - fa, ffb - ff
        print("  %-6s %12d -> %12d  %14s   alloc +%d  free +%d" %
              (t, x, y, fmt_mb(d), da, df))

    print()
    print("=== biggest decreases ===")
    for d, t, x, y in sorted(rows)[:args.top]:
        print("  %-6s %12d -> %12d  %14s" % (t, x, y, fmt_mb(d)))

    new = sorted((t for t in B if t not in A and B[t]["np"] > 0),
                 key=lambda t: -B[t]["np"])
    gone = sorted((t for t in A if A[t]["np"] > 0 and B.get(t, {}).get("np", 0) == 0),
                  key=lambda t: -A[t]["np"])

    print()
    print("=== new tags: %d ===" % len(new))
    for t in new[:10]:
        print("  %-6s %12d" % (t, B[t]["np"]))
    print("=== vanished tags: %d ===" % len(gone))
    for t in gone[:10]:
        print("  %-6s was %12d" % (t, A[t]["np"]))

    print()
    print("Reminder: only driver-specific tags are meaningful for leak analysis.")
    print("Generic tags (File/Thre/Vad/Even/Etw*/FM*/ccm*) track file/thread/ETW")
    print("activity -- if you ran disk-heavy work between the snapshots, they will")
    print("show up here as 'growth' and it means nothing.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
