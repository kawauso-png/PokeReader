#!/usr/bin/env python3
"""Offline omnibus analyzer for Japanese VC Blue Mewtwo traces.

Consumes v7.5 BOOT rows plus the ordinary Exact2F event section.  It deliberately
tries several model families from one capture so hardware iteration is not
needed for every hypothesis:
  * periodic support, P=1..80, trained on the first half and tested on second
  * K Markov support, order 1 and 2
  * period + previous-K hybrid support
  * +1..+16F exact support-envelope propagation for the best periodic model
  * aggregate Exact2F rel1..11 support and final microphase statistics
No result is used for runtime control.
"""
from __future__ import annotations

import argparse
import collections
import statistics
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BootRow:
    seq: int
    add: int
    sub: int
    frame: int
    div: int
    status: int
    valid: int
    first: int
    second: int
    k: int
    step: int
    gap: int

    @property
    def tup(self):
        return self.k, self.step, self.gap

    @property
    def state(self):
        return self.add, self.sub, self.div


def hx(s: str) -> int:
    return int(s, 16)


def parse_boot(path: Path) -> list[BootRow]:
    out = []
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("BOOT,"):
            continue
        p = line.split(",")
        if len(p) != 13:
            continue
        out.append(BootRow(
            seq=int(p[1]), add=hx(p[2]), sub=hx(p[3]), frame=hx(p[4]),
            div=hx(p[5]), status=hx(p[6]), valid=int(p[7]), first=hx(p[8]),
            second=hx(p[9]), k=hx(p[10]), step=hx(p[11]), gap=int(p[12]),
        ))
    return out


def valid_contiguous(rows: list[BootRow]) -> list[BootRow]:
    if not rows:
        return []
    # Keep the longest consecutive run; avoids silently gluing resets/gaps.
    blocks = []
    cur = [rows[0]]
    for r in rows[1:]:
        if r.seq == cur[-1].seq + 1:
            cur.append(r)
        else:
            blocks.append(cur)
            cur = [r]
    blocks.append(cur)
    block = max(blocks, key=len)
    return [r for r in block if r.valid]


def split_train_test(rows, frac=0.5):
    cut = max(1, min(len(rows) - 1, int(len(rows) * frac)))
    return rows[:cut], rows[cut:]


def periodic_support(train: list[BootRow], period: int):
    m = collections.defaultdict(set)
    for r in train:
        m[r.seq % period].add(r.tup)
    return m


def support_score(model, test: list[BootRow], key_fn):
    total = hits = 0
    sizes = []
    for i, r in enumerate(test):
        key = key_fn(i, r)
        s = model.get(key, set())
        if not s:
            continue
        total += 1
        hits += int(r.tup in s)
        sizes.append(len(s))
    return {
        "total": total,
        "hits": hits,
        "coverage": hits / total if total else 0.0,
        "mean_size": statistics.mean(sizes) if sizes else 999.0,
        "max_size": max(sizes) if sizes else 0,
    }


def rank_periods(rows: list[BootRow], max_period=80):
    train, test = split_train_test(rows)
    scored = []
    for p in range(1, max_period + 1):
        m = periodic_support(train, p)
        s = support_score(m, test, lambda _i, r, p=p: r.seq % p)
        scored.append((p, s, m))
    scored.sort(key=lambda x: (-x[1]["coverage"], x[1]["mean_size"], x[0]))
    return scored


def markov_model(train: list[BootRow], order: int):
    m = collections.defaultdict(set)
    for i in range(order, len(train)):
        hist = tuple(train[j].k for j in range(i - order, i))
        m[hist].add(train[i].tup)
    return m


def markov_score(train: list[BootRow], test: list[BootRow], order: int):
    m = markov_model(train, order)
    combined = train[-order:] + test
    total = hits = 0
    sizes = []
    for i in range(order, len(combined)):
        if i < order:
            continue
        hist = tuple(combined[j].k for j in range(i - order, i))
        s = m.get(hist, set())
        if not s:
            continue
        r = combined[i]
        total += 1
        hits += int(r.tup in s)
        sizes.append(len(s))
    return hits, total, statistics.mean(sizes) if sizes else 999.0, max(sizes) if sizes else 0


def hybrid_model(train: list[BootRow], period: int):
    m = collections.defaultdict(set)
    for i in range(1, len(train)):
        r = train[i]
        m[(r.seq % period, train[i - 1].k)].add(r.tup)
    return m


def hybrid_score(train: list[BootRow], test: list[BootRow], period: int):
    m = hybrid_model(train, period)
    combined = train[-1:] + test
    total = hits = 0
    sizes = []
    for i in range(1, len(combined)):
        r = combined[i]
        s = m.get((r.seq % period, combined[i - 1].k), set())
        if not s:
            continue
        total += 1
        hits += int(r.tup in s)
        sizes.append(len(s))
    return hits, total, statistics.mean(sizes) if sizes else 999.0, max(sizes) if sizes else 0


def step_state(state, tup):
    add, sub, div = state
    k, div_step, gap = tup
    nd = (div + div_step) & 0xFF
    first = (nd + k) & 0xFF
    second = (first + gap) & 0xFF
    total = add + first
    na = total & 0xFF
    carry = int(total > 0xFF)
    ns = (sub - second - carry) & 0xFF
    return na, ns, nd


def future_envelope(rows: list[BootRow], period: int, max_h=16, cap=65536):
    train, test = split_train_test(rows, 0.6)
    model = periodic_support(train, period)
    by_seq = {r.seq: r for r in test}
    # Sample many anchors, but keep runtime bounded.
    anchors = test[::max(1, len(test) // 64)]
    stats = {h: {"checks": 0, "hits": 0, "branches": [], "capped": 0} for h in range(1, max_h + 1)}
    for a in anchors:
        states = {a.state}
        for h in range(1, max_h + 1):
            seq = a.seq + h
            support = model.get(seq % period, set())
            nxt = set()
            for st in states:
                for tup in support:
                    nxt.add(step_state(st, tup))
                    if len(nxt) > cap:
                        break
                if len(nxt) > cap:
                    break
            if len(nxt) > cap:
                stats[h]["capped"] += 1
                break
            states = nxt
            actual = by_seq.get(seq)
            if actual is None:
                continue
            stats[h]["checks"] += 1
            stats[h]["hits"] += int(actual.state in states)
            stats[h]["branches"].append(len(states))
    return stats


def parse_main_event(path: Path):
    lines = path.read_text(errors="replace").splitlines()
    try:
        idx = next(i for i, l in enumerate(lines) if l.startswith("seq,rel,"))
    except StopIteration:
        return {}, None
    header = lines[idx].split(",")
    rows = {}
    for l in lines[idx + 1:]:
        if l.startswith(("phase_probe,", "PHASE,", "gb_release", "GBREL", "phase_tracker", "DIVPHASE", "k_observer", "KOBS", "BOOT")):
            break
        v = l.split(",")
        if len(v) != len(header):
            continue
        d = dict(zip(header, v))
        try:
            rows[int(d["rel"])] = d
        except Exception:
            pass
    gb = next((l.split(",") for l in lines if l.startswith("GBREL,")), None)
    return rows, gb


def infer_event(a, b):
    a0, s0, d0 = hx(a["rng_add"]), hx(a["rng_sub"]), hx(a["div"])
    a1, s1, d1 = hx(b["rng_add"]), hx(b["rng_sub"]), hx(b["div"])
    first = (a1 - a0) & 0xFF
    carry = int(a0 + first > 0xFF)
    second = (s0 - s1 - carry) & 0xFF
    gap = (second - first) & 0xFF
    return ((first - d1) & 0xFF, (d1 - d0) & 0xFF, gap)


def event_report(paths: list[Path]):
    support = collections.defaultdict(set)
    phase_offsets = []
    rel9 = []
    used = 0
    for p in paths:
        rows, gb = parse_main_event(p)
        if not rows:
            continue
        used += 1
        for rel in range(1, 12):
            if rel - 1 in rows and rel in rows:
                support[rel].add(infer_event(rows[rel - 1], rows[rel]))
        if gb and len(gb) >= 16:
            try:
                rel9.append(int(gb[3]))
                phase_offsets.append(int(gb[14]))
            except Exception:
                pass
    if not used:
        return
    print("\nExact2F aggregate event support")
    print("traces:", used)
    for rel in range(1, 12):
        vals = sorted(support[rel])
        txt = " ".join(f"({k:02X},+{s:02X},g{g})" for k, s, g in vals)
        print(f"  rel{rel-1:02d}->{rel:02d}: {len(vals)} branches {txt}")
    if rel9:
        print("  GB release -> DV:", sorted(set(rel9)), "frames")
    if phase_offsets:
        print("  final phase offsets:", sorted(set(phase_offsets)))


def boot_report(path: Path, max_period=80):
    raw = parse_boot(path)
    rows = valid_contiguous(raw)
    print(f"\n== {path.name} ==")
    print(f"BOOT rows={len(raw)} longest-valid-run={len(rows)}")
    if len(rows) < 100:
        print("not enough BOOT rows for omnibus model comparison")
        return
    train, test = split_train_test(rows)
    ranking = rank_periods(rows, max_period)
    print("top periodic support models (train first half -> test second half):")
    for p, s, _m in ranking[:10]:
        print(f"  P={p:2d} hit={s['hits']}/{s['total']} {s['coverage']*100:6.2f}% "
              f"meanBranches={s['mean_size']:.2f} max={s['max_size']}")

    for order in (1, 2):
        h, n, meanb, maxb = markov_score(train, test, order)
        print(f"Markov K order{order}: {h}/{n} {(100*h/n if n else 0):.2f}% meanBranches={meanb:.2f} max={maxb}")

    best_p = ranking[0][0]
    h, n, meanb, maxb = hybrid_score(train, test, best_p)
    print(f"Hybrid P{best_p}+prevK: {h}/{n} {(100*h/n if n else 0):.2f}% meanBranches={meanb:.2f} max={maxb}")

    env = future_envelope(rows, best_p)
    print(f"future exact envelope using P={best_p} support:")
    for horizon in range(1, 17):
        s = env[horizon]
        if not s["checks"]:
            continue
        br = s["branches"]
        med = statistics.median(br) if br else 0
        mx = max(br) if br else 0
        print(f"  +{horizon:2d}F {s['hits']}/{s['checks']} "
              f"{100*s['hits']/s['checks']:.2f}% branches median={med:g} max={mx} capped={s['capped']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("traces", nargs="+")
    ap.add_argument("--max-period", type=int, default=80)
    args = ap.parse_args()
    paths = [Path(x) for x in args.traces]
    for p in paths:
        boot_report(p, args.max_period)
    event_report(paths)


if __name__ == "__main__":
    main()
