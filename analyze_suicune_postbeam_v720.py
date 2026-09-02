#!/usr/bin/env python3
"""Suicune v7.2 POST-centric held-out validator.

This script is deliberately conservative.  It does not estimate success
probabilities and it does not count self-replay as prediction accuracy.
It asks two questions only:

1) How early can the observed POST fingerprint distinguish known POST classes?
2) After POST is known, does a suffix candidate set built WITHOUT the held-out
   run cover that run at downstream checkpoints?

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
CHECKPOINTS = (136, 200, 217, 716, 717)


def hx(s: str) -> int:
    return int(s, 16)


def signed(s: str) -> int:
    return int(s, 10)


def phase_step(a: int, b: int) -> int:
    return (b - a) & (MOD_M - 1)


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
            # Keep the last sample for repeated advance values.  This includes
            # any accumulated stall phase before the next RNG advance.
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


def close(x: tuple[int, int], y: tuple[int, int], tol: int) -> bool:
    return abs(x[0] - y[0]) <= tol and abs(x[1] - y[1]) <= tol


def in_envelope(x: tuple[int, int], train: list[tuple[int, int]], tol: int) -> bool:
    if not train:
        return False
    alo, ahi = min(v[0] for v in train) - tol, max(v[0] for v in train) + tol
    slo, shi = min(v[1] for v in train) - tol, max(v[1] for v in train) + tol
    return alo <= x[0] <= ahi and slo <= x[1] <= shi


def group_report(label: tuple[str, int], group: list[Run]) -> None:
    print(f'\n== POST {label[0]}/r{label[1]} n={len(group)} ==')
    if len(group) < 2:
        print('LOO: insufficient repeats')
        return

    for cp in CHECKPOINTS:
        usable = [r for r in group if r.cumulative(cp) is not None]
        if len(usable) < 2:
            continue
        exact = near1 = env0 = env1 = 0
        total = 0
        for hold in usable:
            truth = hold.cumulative(cp)
            train = [r.cumulative(cp) for r in usable if r is not hold]
            train = [x for x in train if x is not None]
            if truth is None or not train:
                continue
            total += 1
            exact += any(close(truth, x, 0) for x in train)
            near1 += any(close(truth, x, 1) for x in train)
            env0 += in_envelope(truth, train, 0)
            env1 += in_envelope(truth, train, 1)
        print(f'rel{cp}: donor-exact {exact}/{total}  donor±1 {near1}/{total}  envelope {env0}/{total}  envelope±1 {env1}/{total}')

    # Find the first exact local-step divergence for every pair.  This locates
    # candidate branch/slip checkpoints without fitting a probability model.
    print('pair first-divergence rel:')
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            a, b = group[i], group[j]
            first = None
            for rel in range(41, 718):
                a0, a1 = a.frames.get(rel - 1), a.frames.get(rel)
                b0, b1 = b.frames.get(rel - 1), b.frames.get(rel)
                if None in (a0, a1, b0, b1):
                    break
                sa = (phase_step(a0[0], a1[0]), phase_step(a0[1], a1[1]))
                sb = (phase_step(b0[0], b1[0]), phase_step(b0[1], b1[1]))
                if sa != sb:
                    first = rel
                    break
            print(f'  {a.name} vs {b.name}: {first if first is not None else "none<=717"}')


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

    print('\nVALIDATION RULE: do not promote POSTBEAM to production unless held-out coverage is demonstrated on repeated POST classes. Self-replay is not evidence.')


if __name__ == '__main__':
    main()
