#!/usr/bin/env python3
"""Suicune direct-phase experiment analyzer (v3.6).

Consumes one or more PokeReader trace CSVs from v3.5/v3.6.
The direct phase is measured in M-cycle units (4 T-cycles):
    P4 = (DIV_byte << 6) | F604
One legacy A-unit is 4 M-cycles, so P = P4 / 4.

The script intentionally keeps the raw physics separate from the old fitted
ADIV/SDIV tracker values.  It extracts the two repeated-advance stalls,
measures their excess phase directly, summarizes bounded normal-frame jitter,
and compares runs with the same target_asub.
"""

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

MOD_M = 16384
FRAME_M = 1172
PAIR_M = 11
MICRO_JITTER_LIMIT = 10


def h(s):
    return int(s, 16)


def modstep(a, b):
    return (b - a) % MOD_M


def phase_m_from_parts(div_byte, subtick):
    return ((div_byte << 6) | subtick) & 0x3FFF


def fmt_quarter(m):
    return f"{m / 4:.2f}"


def read_sections(path):
    lines = Path(path).read_text(errors="replace").splitlines()
    probe = None
    frames = []

    if lines and lines[0].startswith("probe,") and len(lines) > 1:
        probe = next(csv.DictReader(lines[:2]))

    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("frame,rel_adv,"))
    except StopIteration:
        raise ValueError(f"{path}: frame section not found")
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
    frames = list(csv.DictReader(lines[start:end]))
    return probe, frames


def target_phase(probe, side="a"):
    div = h(probe["target_div"])
    div_byte = (div >> 8) & 0xFF if side == "a" else div & 0xFF
    sub = h(probe["target_asub" if side == "a" else "target_ssub"])
    key = "target_ap4" if side == "a" else "target_sp4"
    if key in probe and probe.get(key):
        return h(probe[key])
    return phase_m_from_parts(div_byte, sub)


def frame_phase(row, side="a"):
    key = "ap4" if side == "a" else "sp4"
    if key in row and row.get(key):
        return h(row[key])
    div = h(row["div"])
    div_byte = (div >> 8) & 0xFF if side == "a" else div & 0xFF
    sub = h(row["asub" if side == "a" else "ssub"])
    return phase_m_from_parts(div_byte, sub)


def collapse_advances(frames):
    groups = []
    i = 0
    while i < len(frames):
        adv = int(frames[i]["advance"])
        j = i + 1
        while j < len(frames) and int(frames[j]["advance"]) == adv:
            j += 1
        groups.append({
            "advance": adv,
            "row": frames[i],
            "repeat": j - i,
            "first_index": i,
            "last_index": j - 1,
        })
        i = j
    return groups


def stop_events(groups):
    out = []
    for left, right in zip(groups, groups[1:]):
        if left["repeat"] <= 1:
            continue
        am0 = frame_phase(left["row"], "a")
        am1 = frame_phase(right["row"], "a")
        sm0 = frame_phase(left["row"], "s")
        sm1 = frame_phase(right["row"], "s")
        da = modstep(am0, am1)
        ds = modstep(sm0, sm1)
        extra_a = da - FRAME_M
        extra_s = ds - FRAME_M
        out.append({
            "advance": left["advance"],
            "repeat": left["repeat"],
            "delta_m_a": da,
            "delta_m_s": ds,
            "extra_m_a": extra_a,
            "extra_m_s": extra_s,
            # Historical fit sign: positive extra time shifts fitted A negative.
            "fit_delta_a": -extra_a / 4.0,
            "fit_delta_s": -extra_s / 4.0,
            "extra_a_mod4096": (extra_a / 4.0) % 4096,
        })
    return out


def normal_jitter(groups, target):
    raw = []
    core = []
    keyed_core = {}
    cumulative = 0
    cmin = 0
    cmax = 0
    for left, right in zip(groups, groups[1:]):
        # Time spent on a repeated advance is the stall; analyze separately.
        if left["repeat"] > 1:
            continue
        am0 = frame_phase(left["row"], "a")
        am1 = frame_phase(right["row"], "a")
        step = modstep(am0, am1)
        jitter = step - FRAME_M
        rel = left["advance"] - target
        raw.append((rel, jitter))
        if abs(jitter) <= MICRO_JITTER_LIMIT:
            core.append((rel, jitter))
            keyed_core[rel] = jitter
            cumulative += jitter
            cmin = min(cmin, cumulative)
            cmax = max(cmax, cumulative)
    return {
        "raw": raw,
        "core": core,
        "keyed_core": keyed_core,
        "cum_min": cmin,
        "cum_max": cmax,
        "cum_final": cumulative,
    }


def pair_gaps(frames):
    vals = []
    for row in frames:
        vals.append(modstep(frame_phase(row, "a"), frame_phase(row, "s")))
    return vals


def analyze_one(path):
    probe, frames = read_sections(path)
    if not probe:
        raise ValueError(f"{path}: no Suicune probe summary; arm with Y+X first")
    target = int(probe["target"])
    target_asub = h(probe["target_asub"])
    target_ssub = h(probe["target_ssub"])
    groups = collapse_advances(frames)
    stops = stop_events(groups)
    jitter = normal_jitter(groups, target)
    gaps = pair_gaps(frames)

    result = {
        "path": str(path),
        "name": Path(path).name,
        "target": target,
        "target_asub": target_asub,
        "target_ssub": target_ssub,
        "bucket": target_asub >> 3,
        "target_ap4": target_phase(probe, "a"),
        "target_sp4": target_phase(probe, "s"),
        "offset": int(probe["offset"]) if probe.get("offset") else None,
        "route": int(probe["route"]) if probe.get("route") else None,
        "raw_dv": probe.get("raw_dv", ""),
        "frames": len(frames),
        "unique_advances": len(groups),
        "stops": stops,
        "jitter": jitter,
        "pair_counts": Counter(gaps),
    }
    return result


def print_one(r):
    print(f"== {r['name']} ==")
    print(
        f"target={r['target']}  target_asub=0x{r['target_asub']:02X} ({r['target_asub']}) "
        f"bucket=B{r['bucket']}  P_A={fmt_quarter(r['target_ap4'])}  "
        f"offset={r['offset']} route={r['route']} DV={r['raw_dv']}"
    )
    print("pair gap M:", r["pair_counts"].most_common(8))
    print(f"pair==11: {r['pair_counts'][PAIR_M]}/{sum(r['pair_counts'].values())}")
    for i, stop in enumerate(r["stops"], 1):
        label = "stop1 / Δ1" if i == 1 else "stop2 / Δ2" if i == 2 else f"stop{i}"
        print(
            f"{label}: adv={stop['advance']} repeat={stop['repeat']} "
            f"step={stop['delta_m_a']}M extra={stop['extra_m_a']}M "
            f"fit-sign Δ={stop['fit_delta_a']:.2f} A "
            f"extra mod4096={stop['extra_a_mod4096']:.2f} A"
        )
    raw = r["jitter"]["raw"]
    core = r["jitter"]["core"]
    print(
        f"normal transitions: raw={len(raw)}  micro(|j|<={MICRO_JITTER_LIMIT})={len(core)}  "
        f"excluded structural/outlier={len(raw)-len(core)}"
    )
    if core:
        vals = [x[1] for x in core]
        print("micro jitter M:", Counter(vals).most_common(15))
        print(
            "micro cumulative M: "
            f"min={r['jitter']['cum_min']} max={r['jitter']['cum_max']} final={r['jitter']['cum_final']}"
        )
    print()


def collection_rows(results):
    rows = []
    for r in results:
        s1 = r["stops"][0] if len(r["stops"]) >= 1 else None
        s2 = r["stops"][1] if len(r["stops"]) >= 2 else None
        rows.append({
            "file": r["name"],
            "target": r["target"],
            "target_asub": r["target_asub"],
            "target_asub_hex": f"{r['target_asub']:02X}",
            "bucket": r["bucket"],
            "target_ssub": r["target_ssub"],
            "target_ap4": r["target_ap4"],
            "target_p_a": r["target_ap4"] / 4.0,
            "offset": r["offset"],
            "route": r["route"],
            "raw_dv": r["raw_dv"],
            "delta1_extra_m": s1["extra_m_a"] if s1 else "",
            "delta1_fit_a": s1["fit_delta_a"] if s1 else "",
            "delta2_extra_m": s2["extra_m_a"] if s2 else "",
            "delta2_mod_a": s2["extra_a_mod4096"] if s2 else "",
            "micro_cum_min_m": r["jitter"]["cum_min"],
            "micro_cum_max_m": r["jitter"]["cum_max"],
            "micro_cum_final_m": r["jitter"]["cum_final"],
        })
    return rows


def write_collection(path, rows):
    fields = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def compare_same_asub(results):
    by = defaultdict(list)
    for r in results:
        by[r["target_asub"]].append(r)
    found = False
    for asub, rs in sorted(by.items()):
        if len(rs) < 2:
            continue
        found = True
        print(f"== deterministic comparison: target_asub=0x{asub:02X} ==")
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a = rs[i]["jitter"]["keyed_core"]
                b = rs[j]["jitter"]["keyed_core"]
                common = sorted(set(a) & set(b))
                same = sum(a[k] == b[k] for k in common)
                pct = (100.0 * same / len(common)) if common else 0.0
                print(
                    f"{rs[i]['name']} vs {rs[j]['name']}: "
                    f"micro jitter exact {same}/{len(common)} = {pct:.2f}%"
                )
                mismatches = [(k, a[k], b[k]) for k in common if a[k] != b[k]]
                if mismatches:
                    print("  first mismatches:", mismatches[:12])
        print()
    if not found and len(results) >= 2:
        print("No exact target_asub duplicate yet. Collect a second run with the same live Sub value.\n")


def print_collection(results):
    if len(results) < 2:
        return
    print("== Δ1 collection (sort by target_asub) ==")
    print("file,target_asub,bucket,delta1_extra_m,delta1_fit_A,offset,route")
    for r in sorted(results, key=lambda x: (x["target_asub"], x["name"])):
        s1 = r["stops"][0] if r["stops"] else None
        print(
            f"{r['name']},0x{r['target_asub']:02X},B{r['bucket']},"
            f"{s1['extra_m_a'] if s1 else ''},"
            f"{s1['fit_delta_a'] if s1 else ''},"
            f"{r['offset']},{r['route']}"
        )
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traces", nargs="+", help="v3.5/v3.6 trace CSVs")
    ap.add_argument("--out", help="write collection summary CSV")
    args = ap.parse_args()

    results = []
    for path in args.traces:
        try:
            r = analyze_one(path)
        except Exception as e:
            print(f"ERROR {path}: {e}")
            continue
        results.append(r)
        print_one(r)

    if not results:
        raise SystemExit(2)

    print_collection(results)
    compare_same_asub(results)

    if args.out:
        rows = collection_rows(results)
        write_collection(args.out, rows)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
