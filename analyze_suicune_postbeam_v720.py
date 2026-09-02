#!/usr/bin/env python3
"""Suicune v7.2 POST-centric held-out validator.

Conservative rules:
- no success probabilities;
- no self-replay counted as prediction accuracy;
- POST discrimination and downstream state transport are tested separately;
- a phase match is NOT treated as an RNG-state prediction match.

Usage:
  python3 analyze_suicune_postbeam_v720.py celebi_trace_*.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

MOD_M = 0x4000
CHECKPOINTS = (136, 200, 217, 230, 256, 400, 600, 716, 717)


def hx(s: str) -> int:
    return int(s, 16)


def signed(s: str) -> int:
    return int(s, 10)


def phase_step(a: int, b: int) -> int:
    return (b - a) & (MOD_M - 1)


def upd(st: int, a: int, s: int) -> int:
    ra, rs = (st >> 8) & 0xFF, st & 0xFF
    z = ra + a
    carry = 1 if z > 0xFF else 0
    return ((z & 0xFF) << 8) | ((rs - s - carry) & 0xFF)


def s8(x: int) -> int:
    x &= 0xFF
    return x - 256 if x >= 128 else x


@dataclass
class Run:
    path: Path
    name: str
    post: tuple[str, int]
    post_d: tuple[int, ...]
    frames: dict[int, tuple[int, int, int, int]]  # rel -> ap4,sp4,state,div

    def cumulative(self, cp: int) -> tuple[int, int] | None:
        if 40 not in self.frames or cp not in self.frames:
            return None
        sa = ss = 0
        for rel in range(41, cp + 1):
            prev = self.frames.get(rel - 1)
            cur = self.frames.get(rel)
            if prev is None or cur is None:
                return None
            sa += phase_step(prev[0], cur[0])
            ss += phase_step(prev[1], cur[1])
        return sa, ss


def section_row(lines: list[str], header_prefix: str, data_prefix: str) -> dict[str, str] | None:
    for i, line in enumerate(lines[:-1]):
        if line.startswith(header_prefix) and lines[i + 1].startswith(data_prefix):
            return next(csv.DictReader([line, lines[i + 1]]))
    return None


def read_run(path: Path) -> Run | None:
    lines = path.read_text(errors='replace').splitlines()
    post = section_row(lines, 'postfingerprint,version,', 'POSTFP,')
    if not post or post.get('valid') != '1':
        return None
    label = (post['proto'], int(post['post_rot']))
    ds = tuple(signed(post[f'd{i}']) for i in range(28, 40))

    try:
        start = next(i for i, x in enumerate(lines) if x.startswith('frame,rel_adv,'))
    except StopIteration:
        return None
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
    rows = csv.DictReader(lines[start:end])
    frames: dict[int, tuple[int, int, int, int]] = {}
    for r in rows:
        try:
            rel = int(r['rel_adv'])
            # Last sample wins for repeated advances so a stall's accumulated
            # phase is represented before the next RNG advance.
            frames[rel] = (hx(r['ap4']), hx(r['sp4']), hx(r['state']), hx(r['div']))
        except (KeyError, ValueError):
            continue
    return Run(path, path.name, label, ds, frames)


def post_prefix_report(runs: list[Run]) -> None:
    print('\n== POST fingerprint prefix discrimination ==')
    for n in range(1, 13):
        groups: dict[tuple[int, ...], set[tuple[str, int]]] = defaultdict(set)
        for r in runs:
            groups[r.post_d[:n]].add(r.post)
        collisions = sum(1 for labels in groups.values() if len(labels) > 1)
        print(f'prefix d28..d{27+n}: cross-label collisions={collisions}')
        if collisions == 0:
            print(f'EARLIEST_ZERO_COLLISION_PREFIX={n}')
            break


def close_pair(x: tuple[int, int], y: tuple[int, int], tol: int) -> bool:
    return abs(x[0] - y[0]) <= tol and abs(x[1] - y[1]) <= tol


def in_envelope(x: tuple[int, int], train: list[tuple[int, int]], tol: int) -> bool:
    if not train:
        return False
    alo, ahi = min(v[0] for v in train) - tol, max(v[0] for v in train) + tol
    slo, shi = min(v[1] for v in train) - tol, max(v[1] for v in train) + tol
    return alo <= x[0] <= ahi and slo <= x[1] <= shi


def transport_state(target: Run, donor: Run, cp: int) -> tuple[int, int] | None:
    """Replay donor POST suffix from target's actual rel40 root.

    Donor DIV bytes are expressed as offsets from donor rel40 and transplanted
    onto target rel40 DIV.  This is intentionally an empirical held-out test,
    not a claim that exact-index cadence correction is solved.
    Returns (predicted_state, actual_state).
    """
    tf, df = target.frames, donor.frames
    if 40 not in tf or 40 not in df or cp not in tf or cp not in df:
        return None
    st = tf[40][2]
    target_div40, donor_div40 = tf[40][3], df[40][3]
    tav, tsv = (target_div40 >> 8) & 0xFF, target_div40 & 0xFF
    dav0, dsv0 = (donor_div40 >> 8) & 0xFF, donor_div40 & 0xFF
    for rel in range(41, cp + 1):
        d = df.get(rel)
        if d is None:
            return None
        dv = d[3]
        da, ds = (dv >> 8) & 0xFF, dv & 0xFF
        a = (tav + ((da - dav0) & 0xFF)) & 0xFF
        s = (tsv + ((ds - dsv0) & 0xFF)) & 0xFF
        st = upd(st, a, s)
    return st, tf[cp][2]


def state_close(pred: int, actual: int, tol: int) -> bool:
    pa, ps = (pred >> 8) & 0xFF, pred & 0xFF
    aa, ass = (actual >> 8) & 0xFF, actual & 0xFF
    return abs(s8(aa - pa)) <= tol and abs(s8(ass - ps)) <= tol


def first_transport_mismatch(target: Run, donor: Run) -> int | None:
    for rel in range(41, 718):
        z = transport_state(target, donor, rel)
        if z is None:
            return None
        if z[0] != z[1]:
            return rel
    return None


def group_report(label: tuple[str, int], group: list[Run]) -> None:
    print(f'\n== POST {label[0]}/r{label[1]} n={len(group)} ==')
    if len(group) < 2:
        print('LOO: insufficient repeats')
        return

    for cp in CHECKPOINTS:
        usable = [r for r in group if r.cumulative(cp) is not None]
        if len(usable) < 2:
            continue
        phase_exact = phase_env = phase_env1 = 0
        state_exact = state_near1 = 0
        total = 0
        for hold in usable:
            phase_truth = hold.cumulative(cp)
            train = [r for r in usable if r is not hold]
            train_phase = [r.cumulative(cp) for r in train]
            train_phase = [x for x in train_phase if x is not None]
            if phase_truth is None or not train_phase:
                continue
            total += 1
            phase_exact += any(close_pair(phase_truth, x, 0) for x in train_phase)
            phase_env += in_envelope(phase_truth, train_phase, 0)
            phase_env1 += in_envelope(phase_truth, train_phase, 1)

            preds = [transport_state(hold, d, cp) for d in train]
            preds = [z for z in preds if z is not None]
            state_exact += any(pred == actual for pred, actual in preds)
            state_near1 += any(state_close(pred, actual, 1) for pred, actual in preds)

        print(
            f'rel{cp}: phase donor-exact {phase_exact}/{total}  '
            f'phase envelope {phase_env}/{total}  envelope±1 {phase_env1}/{total}  '
            f'RNG-state donor-exact {state_exact}/{total}  state±1byte {state_near1}/{total}'
        )

    print('pair first RNG-state transport mismatch:')
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            a, b = group[i], group[j]
            ab = first_transport_mismatch(a, b)
            ba = first_transport_mismatch(b, a)
            print(f'  {a.name} <- {b.name}: {ab if ab is not None else "none<=717"}')
            print(f'  {b.name} <- {a.name}: {ba if ba is not None else "none<=717"}')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('csv', nargs='+')
    args = ap.parse_args()

    runs = []
    for s in args.csv:
        r = read_run(Path(s))
        if r is not None:
            runs.append(r)
    print(f'usable POST traces: {len(runs)}/{len(args.csv)}')
    if not runs:
        raise SystemExit(2)

    post_prefix_report(runs)
    groups: dict[tuple[str, int], list[Run]] = defaultdict(list)
    for r in runs:
        groups[r.post].append(r)
    for label in sorted(groups):
        group_report(label, groups[label])

    print('\nVALIDATION RULE: POSTBEAM is not production-ready until repeated POST classes demonstrate held-out RNG-state coverage at downstream checkpoints. Phase-only agreement and self-replay are not sufficient evidence.')


if __name__ == '__main__':
    main()
