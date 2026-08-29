#!/usr/bin/env python3
"""Validation-first checks for Suicune prototype v3.9.1.

This intentionally distinguishes implementation self-replay from real cross-run
prediction. It imports the v3.9 trace/profile extractor, but uses the corrected
16-frame divider sum (293) for replay.
"""
from __future__ import annotations
import argparse, math
from pathlib import Path
from analyze_suicune_prototype_v39 import analyze, DIV_INC

CYCLE_SUM = sum(DIV_INC)
assert CYCLE_SUM == 293


def div_delta(index: int, k: int) -> int:
    full, rem = divmod(k, 16)
    total = full * CYCLE_SUM
    for t in range(rem):
        total += DIV_INC[(index + t) & 15]
    return total & 0xFF


def side_values(p, side: str, phase: int, upto: int):
    vals = [DIV_INC[phase & 15]]
    f = p['flat']
    off = 0 if side == 'A' else 2
    for j in range(upto):
        i = j * 4
        k = f[i + off]
        residual = f[i + off + 1]
        vals.append((div_delta(phase, k) + residual) & 0xFF)
    return vals


def sum_with_base(vals, base: int) -> int:
    return sum((v + base) & 0xFF for v in vals)


def root_of(p):
    st = int(p['target_state'], 16)
    dv = int(p['target_div'], 16)
    return st >> 8, st & 0xFF, dv >> 8, dv & 0xFF, p['target_adiv'], p['target_sdiv']


def predict(root, p) -> int:
    ra, rs, av, sv, ai, si = root
    a1 = sum_with_base(side_values(p, 'A', ai, p['n1']), av)
    a2 = sum_with_base(side_values(p, 'A', ai, p['n2']), av)
    s1 = sum_with_base(side_values(p, 'S', si, p['n1']), sv)
    s2 = sum_with_base(side_values(p, 'S', si, p['n2']), sv)
    d1 = (rs - s1 - math.floor((ra + a1) / 256)) & 0xFF
    d2 = (rs - s2 - math.floor((ra + a2) / 256)) & 0xFF
    return (d1 << 8) | d2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('traces', nargs='+')
    args = ap.parse_args()

    results = [analyze(Path(x)) for x in args.traces]
    profiles = [r['profile'] for r in results]

    self_hits = sum(predict(root_of(p), p) == int(p['raw_dv'], 16) for p in profiles)
    all_hits = all_n = same_hits = same_n = 0
    for target in profiles:
        root = root_of(target)
        truth = int(target['raw_dv'], 16)
        for donor in profiles:
            if donor is target:
                continue
            ok = predict(root, donor) == truth
            all_n += 1
            all_hits += ok
            if donor['prototype'] == target['prototype']:
                same_n += 1
                same_hits += ok

    exact = len({(p['phase_a'], p['phase_s']) for p in profiles})
    diff = len({(p['phase_a'] - p['phase_s']) & 15 for p in profiles})

    print(f'DIV cycle sum: {CYCLE_SUM}')
    print(f'Self replay sanity: {self_hits}/{len(profiles)}  (circular; not prediction evidence)')
    print(f'Leave-one-out raw DV: {all_hits}/{all_n}')
    print(f'Same-prototype LOO: {same_hits}/{same_n}')
    print(f'Exact phase coverage: {exact}/256 = {100*exact/256:.1f}%')
    print(f'Diff coverage: {diff}/16 = {100*diff/16:.1f}%')


if __name__ == '__main__':
    main()
