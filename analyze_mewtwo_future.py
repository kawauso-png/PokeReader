#!/usr/bin/env python3
"""Offline rolling predictor for Japanese VC Blue Mewtwo research.

Phase-4 prototype.  This does NOT implement the conservative 216-DV envelope.
It works on ordinary no-input frame transitions and asks whether one shared
sub-DIV M-cycle phase can explain all of the observed ambiguities.

If the Blue VC candidate at 0x0022F604 is validated as the same divider M-cycle
subtick already observed in JP VC Crystal, the direct phase is:

    P4 = ((rDIV << 6) | subtick) & 0x3fff

where one P4 unit is one LR35902 M-cycle (4 T-cycles).

Physics used here:
- one GB frame = 70224 T = 17556 M = 274*64 + 20 M
- modulo the visible 8-bit rDIV byte, one frame advances +18 or +19
- current sampled subtick <44  -> next sampled DIV +0x12
- current sampled subtick >=44 -> next sampled DIV +0x13
- Random_ first->second rDIV read = 11 M
- therefore Random gap=1 iff the first-read subtick is >=53
- consecutive BattleRandom first reads = 120 M = 1*64 + 56
- therefore d2-d1 is 1 if d1 subtick <8, otherwise 2

Without direct F604 data the script can fit a small hidden phase model from a
trace.  It enumerates only 64 sample subticks and a bounded sample->Random timing
offset; it does not enumerate final DV branches.  The fit is intended to learn
or validate the normal-frame CURRENT -> +1F predictor before any shiny search
or auto-pause is enabled.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from analyze_mewtwo_d1 import parse_trace, h2

SUB_MOD = 64
FRAME_M = 17556
FRAME_SUB_STEP = FRAME_M % SUB_MOD  # 20 M
FRAME_DIV_BASE = (FRAME_M // SUB_MOD) & 0xFF  # 274 -> 0x12 modulo 256
RANDOM_PAIR_M = 11
BATTLE_PAIR_M = 120
NORMAL_FIRST_HIGH_OFFSET = 0x18  # empirical 37/37 relation supplied by SAFE traces


@dataclass(frozen=True)
class ObsTransition:
    seq: int
    add0: int
    sub0: int
    div0: int
    add1: int
    sub1: int
    div1: int
    first: int
    second: int
    gap: int
    div_step: int


def adc_carry(a: int, b: int, cin: int) -> int:
    return int(a + b + cin > 0xFF)


def infer_vblank(a0: int, s0: int, a1: int, s1: int):
    """Infer the two Random_ rDIV bytes for a normal VBlank call (carry-in 0)."""
    first = (a1 - a0) & 0xFF
    carry = adc_carry(a0, first, 0)
    second = (s0 - s1 - carry) & 0xFF
    gap = (second - first) & 0xFF
    if gap not in (0, 1):
        return None
    return first, second, gap


def direct_phase(div: int, subtick: int) -> int:
    return ((div & 0xFF) << 6 | (subtick & 0x3F)) & 0x3FFF


def next_sample_div_step(subtick: int) -> int:
    # 274 visible-DIV ticks per frame plus one more tick if +20 M crosses 64.
    return (FRAME_DIV_BASE + int((subtick & 0x3F) + FRAME_SUB_STEP >= SUB_MOD)) & 0xFF


def next_sample_subtick(subtick: int) -> int:
    return ((subtick & 0x3F) + FRAME_SUB_STEP) & 0x3F


def random_gap_from_first_subtick(subtick: int) -> int:
    return int((subtick & 0x3F) + RANDOM_PAIR_M >= SUB_MOD)


def battle_first_read_ticks(subtick: int) -> int:
    """Visible rDIV ticks from BattleRandom #1 first read to #2 first read."""
    return ((subtick & 0x3F) + BATTLE_PAIR_M) // SUB_MOD


def clean_normal_transitions(t):
    rows = t.rows
    out: list[ObsTransition] = []
    for a, b in zip(rows, rows[1:]):
        try:
            q0, q1 = int(a['seq']), int(b['seq'])
        except (KeyError, ValueError):
            continue
        if q1 != q0 + 1:
            continue

        # Keep only ordinary no-input, pre-battle transitions.  Older traces may
        # omit some columns, so absent diagnostics do not disqualify the row.
        def z(row, key):
            v = (row.get(key) or '').strip()
            return not v or int(v, 16 if any(c in v.upper() for c in 'ABCDEF') else 10) == 0

        try:
            if not (z(a, 'joy_pressed') and z(b, 'joy_pressed')):
                continue
            if not (z(a, 'joy_held') and z(b, 'joy_held')):
                continue
            if not (z(a, 'phys_a') and z(b, 'phys_a')):
                continue
            if not (z(a, 'battle') and z(b, 'battle')):
                continue

            a0, s0, d0 = h2(a['rng_add']), h2(a['rng_sub']), h2(a['div'])
            a1, s1, d1 = h2(b['rng_add']), h2(b['rng_sub']), h2(b['div'])
        except (KeyError, ValueError):
            continue
        r = infer_vblank(a0, s0, a1, s1)
        if r is None:
            continue
        first, second, gap = r
        step = (d1 - d0) & 0xFF
        if step not in (0x12, 0x13):
            continue
        out.append(ObsTransition(q0, a0, s0, d0, a1, s1, d1,
                                 first, second, gap, step))
    return out


@dataclass(frozen=True)
class PhaseFit:
    start_sub: int
    random_offset_m: int


def fit_phase(transitions: list[ObsTransition], high_offset: int = NORMAL_FIRST_HIGH_OFFSET):
    """Fit sample subtick and sample(next-row)->Random first-read M-cycle offset.

    The offset search spans one visible-DIV tick around the empirical +0x18
    relation.  A candidate must reproduce every observed +12/+13 step, the
    inferred Random first DIV byte, and the inferred Random gap0/+1.
    """
    if not transitions:
        return []
    fits: list[PhaseFit] = []
    base = high_offset * SUB_MOD
    # Allow the low timing component to be represented on either side of the
    # nominal +0x18 boundary; the observed first DIV itself selects the valid side.
    for start_sub in range(SUB_MOD):
        for offset_m in range(base - 63, base + 64):
            sub = start_sub
            ok = True
            for tr in transitions:
                if next_sample_div_step(sub) != tr.div_step:
                    ok = False
                    break
                next_sub = next_sample_subtick(sub)
                total = next_sub + offset_m
                predicted_first = (tr.div1 + total // SUB_MOD) & 0xFF
                first_sub = total % SUB_MOD
                if predicted_first != tr.first:
                    ok = False
                    break
                if random_gap_from_first_subtick(first_sub) != tr.gap:
                    ok = False
                    break
                sub = next_sub
            if ok:
                fits.append(PhaseFit(start_sub, offset_m))
    return fits


def apply_random(add: int, sub: int, first: int, first_sub: int):
    second = (first + random_gap_from_first_subtick(first_sub)) & 0xFF
    total = add + first
    add2 = total & 0xFF
    carry = int(total > 0xFF)
    sub2 = (sub - second - carry) & 0xFF
    return add2, sub2, second


def roll_from_last(last: ObsTransition, fit: PhaseFit, n_transitions: int, horizon: int):
    """Roll forward from the final observed row using one fitted phase state."""
    # start_sub belongs to the first transition's row0.  After N transitions,
    # the current last row has advanced N sample-subtick steps.
    current_sub = fit.start_sub
    for _ in range(n_transitions):
        current_sub = next_sample_subtick(current_sub)

    add, sub, div = last.add1, last.sub1, last.div1
    out = []
    for off in range(1, horizon + 1):
        div_step = next_sample_div_step(current_sub)
        next_div = (div + div_step) & 0xFF
        next_sub = next_sample_subtick(current_sub)
        total = next_sub + fit.random_offset_m
        first = (next_div + total // SUB_MOD) & 0xFF
        first_sub = total % SUB_MOD
        add2, sub2, second = apply_random(add, sub, first, first_sub)
        out.append({
            'offset': off,
            'add': add2,
            'sub': sub2,
            'div': next_div,
            'sample_sub': next_sub,
            'random_first': first,
            'random_second': second,
            'gap': (second - first) & 0xFF,
        })
        add, sub, div, current_sub = add2, sub2, next_div, next_sub
    return out


def report(path: Path, horizon: int):
    t = parse_trace(path)
    trans = clean_normal_transitions(t)
    print(f'\n== {path.name} ==')
    print(f'clean normal transitions: {len(trans)}')
    if not trans:
        print('no usable normal transitions')
        return

    rel = sum(int(x.first == ((x.div1 + NORMAL_FIRST_HIGH_OFFSET) & 0xFF)) for x in trans)
    print(f'first-rDIV == next-sample DIV +18h: {rel}/{len(trans)}')
    combos = sorted({(x.div_step, x.gap) for x in trans})
    print('observed (DIV step, gap):', ' '.join(f'(+{s:02X},{g})' for s, g in combos))

    fits = fit_phase(trans)
    print(f'hidden phase fits: {len(fits)}')
    if fits:
        starts = sorted({f.start_sub for f in fits})
        offsets = sorted({f.random_offset_m for f in fits})
        print('sample subtick starts:', ' '.join(f'{x:02d}' for x in starts))
        print('sample->Random offsets M:', ' '.join(str(x) for x in offsets))

        predictions = {}
        for fit in fits:
            rows = roll_from_last(trans[-1], fit, len(trans), horizon)
            key = tuple((r['add'], r['sub'], r['div']) for r in rows)
            predictions.setdefault(key, []).append(fit)
        print(f'unique future RNG paths (+1..+{horizon}F): {len(predictions)}')
        if len(predictions) == 1:
            rows = roll_from_last(trans[-1], fits[0], len(trans), horizon)
            print('DIRECT/TRACKED future:')
            for r in rows:
                print(f"  +{r['offset']:2d}F ADD={r['add']:02X} SUB={r['sub']:02X} "
                      f"DIV={r['div']:02X} sub={r['sample_sub']:02d} "
                      f"R={r['random_first']:02X}/{r['random_second']:02X} g{r['gap']}")
        else:
            print('not unique yet; keep phase states instead of expanding DV branches')


def self_test():
    # Full-frame DIV carry thresholds.
    assert next_sample_div_step(43) == 0x12
    assert next_sample_div_step(44) == 0x13
    assert next_sample_subtick(63) == 19
    # Random_ 11-M pair threshold.
    assert random_gap_from_first_subtick(52) == 0
    assert random_gap_from_first_subtick(53) == 1
    # BattleRandom first-read spacing: 120 M = 64+56.
    assert battle_first_read_ticks(7) == 1
    assert battle_first_read_ticks(8) == 2


def main():
    self_test()
    ap = argparse.ArgumentParser()
    ap.add_argument('traces', nargs='+')
    ap.add_argument('--horizon', type=int, default=16)
    args = ap.parse_args()
    if not 1 <= args.horizon <= 64:
        raise SystemExit('--horizon must be 1..64')
    for p in args.traces:
        report(Path(p), args.horizon)


if __name__ == '__main__':
    main()
