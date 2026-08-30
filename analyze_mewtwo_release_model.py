#!/usr/bin/env python3
"""Learn and validate a finite-branch GB-release -> Mewtwo DV model.

Uses only SAFE trace CSVs.  The model is learned from the supplied traces:
- per-frame VBlank first-rDIV phase sets from GB release through final-pre,
- per-frame sampled DIV step sets,
- per-frame first->second rDIV gap sets,
- observed final d2 phase classes.

It then replays each supplied release snapshot through the branch envelope and
checks whether the actual PRE state and actual raw DV remain reachable.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from analyze_mewtwo_d1 import parse_trace, release_phases, final_model, h2, h4

SHINY_ATK = {2, 3, 6, 7, 10, 11, 14, 15}


def shiny(raw: int) -> bool:
    return (((raw >> 8) & 0xF) == 10 and ((raw >> 4) & 0xF) == 10
            and (raw & 0xF) == 10 and ((raw >> 12) & 0xF) in SHINY_ATK)


def learn(traces):
    phase, gap, step = defaultdict(set), defaultdict(set), defaultdict(set)
    d2_phase, final_vb_phase = set(), set()
    for t in traces:
        for i, r in enumerate(release_phases(t)):
            phase[i].add(r['phase'])
            gap[i].add(r['gap'])
            step[i].add(r['step'])
        _raw, d2, candidates = final_model(t)
        pre_div = h2(t.gb['pre_div'])
        d2_phase.add((d2 - pre_div) & 0xFF)
        for c in candidates:
            if c['valid']:
                final_vb_phase.add(c['phase'])
    n = max(phase.keys(), default=-1) + 1
    return {
        'phase': [phase[i] for i in range(n)],
        'gap': [gap[i] for i in range(n)],
        'step': [step[i] for i in range(n)],
        'd2_phase': d2_phase,
        'final_vb_phase': final_vb_phase,
    }


def advance_release(t, model):
    states = {(h2(t.gb['rng_add']), h2(t.gb['rng_sub']), h2(t.gb['div']))}
    for phases, gaps, steps in zip(model['phase'], model['gap'], model['step']):
        nxt = set()
        for a, s, d in states:
            for ph in phases:
                r1 = (d + ph) & 0xFF
                total = a + r1
                a2, carry = total & 0xFF, int(total > 0xFF)
                for g in gaps:
                    r2 = (r1 + g) & 0xFF
                    s2 = (s - r2 - carry) & 0xFF
                    for st in steps:
                        nxt.add((a2, s2, (d + st) & 0xFF))
        states = nxt
    return states


def final_raws(pre_states, model):
    raws = set()
    for a, _s, d in pre_states:
        for d2ph in model['d2_phase']:
            d2 = (d + d2ph) & 0xFF
            for delta in (1, 2):
                d1 = (d2 - delta) & 0xFF
                for vbph in model['final_vb_phase']:
                    vb1 = (d + vbph) & 0xFF
                    a1 = (a + vb1) & 0xFF  # normal VBlank Random carry-in=0
                    lo = (a1 + d1 + 1) & 0xFF
                    hi = (lo + d2 + 1) & 0xFF
                    raws.add((hi << 8) | lo)
    return raws


def fmtset(xs):
    return '{' + ','.join(str(x) for x in sorted(xs)) + '}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('traces', nargs='+')
    args = ap.parse_args()
    traces = [parse_trace(Path(p)) for p in args.traces]
    model = learn(traces)

    print('== learned SAFE release model ==')
    for i, (ph, gp, st) in enumerate(zip(model['phase'], model['gap'], model['step']), 1):
        print(f'F{i}: phase={fmtset(ph)} gap={fmtset(gp)} step={fmtset(st)}')
    print('d2 phase classes:', fmtset(model['d2_phase']))
    print('final-VBlank phase envelope:', fmtset(model['final_vb_phase']))

    ok_pre = ok_raw = 0
    for t in traces:
        states = advance_release(t, model)
        actual_pre = (h2(t.gb['pre_rng_add']), h2(t.gb['pre_rng_sub']), h2(t.gb['pre_div']))
        pre_ok = actual_pre in states
        raws = final_raws(states, model)
        actual_raw = h4(t.meta['raw_dv'])
        raw_ok = actual_raw in raws
        shinies = sorted(r for r in raws if shiny(r))
        ok_pre += pre_ok
        ok_raw += raw_ok
        print(f'\n{t.path.name}: pre={"PASS" if pre_ok else "FAIL"} ({len(states)} states) '
              f'raw={"PASS" if raw_ok else "FAIL"} ({len(raws)} raws) '
              f'shiny_candidates={len(shinies)}')
        if shinies:
            print('  shiny raw:', ' '.join(f'{x:04X}' for x in shinies))

    print(f'\nregression PRE {ok_pre}/{len(traces)}  RAW {ok_raw}/{len(traces)}')


if __name__ == '__main__':
    main()
