#!/usr/bin/env python3
"""
pooltag.py — Windows kernel pool tag snapshot, with tag -> driver attribution.

Read-only: queries NtQuerySystemInformation(SystemPoolTagInformation) and, when
mapping is enabled, only *reads* driver binaries to look for the tag literal.

Usage:
    python pooltag.py                      # top 40, with driver mapping
    python pooltag.py snapshot.json        # also save a JSON snapshot
    python pooltag.py --top 80
    python pooltag.py --no-map             # skip the (slower) driver mapping
    python pooltag.py --map-dir "D:\\extra\\drivers"

Why this exists: poolmon.exe requires a WDK install, and RAMMap needs a GUI.
This needs neither.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys

ntdll = ctypes.WinDLL("ntdll.dll")
SystemPoolTagInformation = 0x16

# Default locations a driver binary may live in.
DEFAULT_MAP_DIRS = [
    r"C:\Windows\System32\drivers",
    r"C:\Windows\System32\DriverStore\FileRepository",
]


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
    """Return {tag: {np, np_alloc, np_free, p, p_alloc, p_free}}."""
    size = 1 << 21  # 2 MiB is plenty (a few thousand entries)
    buf = ctypes.create_string_buffer(size)
    ret = wt.ULONG(0)
    st = ntdll.NtQuerySystemInformation(
        SystemPoolTagInformation, buf, size, ctypes.byref(ret))
    if st != 0:
        raise RuntimeError("NtQuerySystemInformation failed 0x%08X" % (st & 0xFFFFFFFF))

    entry = ctypes.sizeof(SYSTEM_POOLTAG)
    # NOTE: the buffer starts with an 8-byte header (count + padding).
    count = int.from_bytes(buf.raw[0:8], "little")
    n = min(count, (ret.value - 8) // entry)

    tags = {}
    for i in range(n):
        t = SYSTEM_POOLTAG.from_buffer_copy(buf.raw, 8 + i * entry)
        # NOTE: little-endian byte order gives the in-memory char order.
        raw = t.TagUlong.to_bytes(4, "little")
        tag = "".join(chr(c) if 32 <= c < 127 else "?" for c in raw)
        tags[tag] = {
            "np": t.NonPagedUsed,
            "np_alloc": t.NonPagedAllocs,
            "np_free": t.NonPagedFrees,
            "p": t.PagedUsed,
            "p_alloc": t.PagedAllocs,
            "p_free": t.PagedFrees,
        }
    return tags


def count_standalone_tag(data, tag):
    """Count occurrences of `tag` that look like a real 4-byte pool-tag constant.

    Naive substring matching produces false positives: 'Cont' is a substring of
    "Content"/"Control"/"Continue" and would match hundreds of unrelated drivers;
    'ismc' matched a Wi-Fi driver in testing. A real pool tag is a 4-byte
    constant, so its neighbours are code/table bytes, not more letters.

    Heuristic: reject a hit whose immediate neighbour (left or right) is
    alphanumeric — i.e. the tag is embedded inside a longer identifier/string.
    """
    n = len(data)
    taglen = len(tag)
    hits = 0
    start = 0
    while True:
        i = data.find(tag, start)
        if i < 0:
            return hits
        left = data[i - 1] if i > 0 else 0
        right = data[i + taglen] if i + taglen < n else 0

        def alnum(c):
            return (65 <= c <= 90) or (97 <= c <= 122) or (48 <= c <= 57) or c == 95

        if not alnum(left) and not alnum(right):
            hits += 1
        start = i + 1


def scan_file_for_tags(path, wanted):
    """Chunked scan (no size cap) to keep memory flat on 100 MB+ drivers."""
    CHUNK = 8 * 1024 * 1024
    OVERLAP = 16
    found = set()
    try:
        fh = open(path, "rb")
    except OSError:
        return found
    with fh:
        prev = b""
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            buf = prev + chunk
            for w in wanted:
                if w in buf and count_standalone_tag(buf, w) > 0:
                    found.add(w)
            if len(found) == len(wanted):
                break
            prev = buf[-OVERLAP:]
    return found


def tag_to_driver(tags, dirs):
    """Best-effort: find which .sys binaries contain the tag as a standalone constant.

    Returns {tag: [filenames]}. The NUMBER of files is itself the diagnostic:
      * 1 file    -> tag is attributable to that driver
      * many      -> the tag is a generic substring; do NOT attribute it
    """
    wanted = sorted({t.encode("ascii", "ignore") for t in tags if "?" not in t})
    hits = {w.decode(): set() for w in wanted}

    # Expand DriverStore/FileRepository one and two levels deep.
    roots = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        roots.append(d)
        for e1 in os.scandir(d):
            if e1.is_dir():
                roots.append(e1.path)
        for e1 in os.scandir(d):
            if e1.is_dir():
                for e2 in os.scandir(e1.path):
                    if e2.is_dir():
                        roots.append(e2.path)

    seen_roots, seen_files = set(), set()
    for root in roots:
        if root in seen_roots:
            continue
        seen_roots.add(root)
        try:
            entries = list(os.scandir(root))
        except OSError:
            continue
        for e in entries:
            if not e.is_file() or not e.name.lower().endswith(".sys"):
                continue
            if e.name in seen_files:
                continue
            seen_files.add(e.name)
            for w in scan_file_for_tags(e.path, wanted):
                hits[w.decode()].add(e.name)

    return {k: sorted(v) for k, v in hits.items() if v}


def fmt_driver(names, limit=2):
    """Display matches together with the match count.

    The count is the signal: 1 = attributable, 500 = this tag is a common
    substring and cannot be attributed to any single driver.
    """
    if not names:
        return ""
    if len(names) <= limit:
        return "%s  [%d]" % (", ".join(names), len(names))
    return "%s  [+%d more]" % (", ".join(names[:limit]), len(names) - limit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", help="optional JSON snapshot path")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--no-map", action="store_true")
    ap.add_argument("--map-dir", action="append", default=[])
    args = ap.parse_args()

    tags = snapshot()
    np_total = sum(v["np"] for v in tags.values())
    p_total = sum(v["p"] for v in tags.values())

    print("tag entries    : %d" % len(tags))
    print("nonpaged total : %.3f GiB (%d bytes)" % (np_total / 1024 ** 3, np_total))
    print("paged total    : %.3f GiB (%d bytes)" % (p_total / 1024 ** 3, p_total))
    print()

    top = sorted(tags.items(), key=lambda kv: kv[1]["np"], reverse=True)[:args.top]

    mapping = {}
    if not args.no_map:
        dirs = args.map_dir or DEFAULT_MAP_DIRS
        mapping = tag_to_driver([t for t, _ in top], dirs)

    print("%-6s %14s %12s %12s %10s %8s  %s" %
          ("TAG", "NP_BYTES", "ALLOC", "FREE", "FREE%", "PAGED", "DRIVER(s)"))
    for tag, v in top:
        free_pct = (v["np_free"] / v["np_alloc"] * 100) if v["np_alloc"] else 0.0
        print("%-6s %14d %12d %12d %9.1f%% %8d  %s" %
              (tag, v["np"], v["np_alloc"], v["np_free"], free_pct,
               v["p"], fmt_driver(mapping.get(tag, []))))

    print()
    print("Reading the table:")
    print("  FREE%  = nonpaged frees / nonpaged allocs. A LOW value (<90%) means")
    print("           objects were allocated and never returned -> suspected leak.")
    print("           A HIGH value (~100%) with huge ALLOC is normal churn.")
    print("  NP_BYTES alone tells you nothing about leaking; combine with FREE%.")
    print("  Generic tags (File/Thre/Vad/Even/Irp/Mm*) track system activity and")
    print("  must NOT be used as a leak criterion. Watch driver-specific tags only.")
    print("  DRIVER(s) lists EVERY .sys containing the tag literal. A tag that")
    print("  matches many drivers is generic and cannot be attributed to one.")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"np_total": np_total, "p_total": p_total,
                       "tag_count": len(tags), "tags": tags,
                       "mapping": mapping}, fh, ensure_ascii=False)
        print("\nsnapshot written: %s" % args.out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
