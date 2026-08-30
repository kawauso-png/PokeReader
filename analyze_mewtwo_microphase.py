#!/usr/bin/env python3
"""Japanese VC Blue Mewtwo final-frame microphase analyzer.

This is deliberately OFFLINE. It does not hook, patch, thread, scan, or alter
3DS/VC execution.

Established source/trace structure used here:

* One sampled GB frame advances the high rDIV byte about 274/275 ticks, so the
  visible pre->battle DIV delta (normally +18/+19 mod 256) contains one wrap.
* Gen-I Random_ reads rDIV twice, ADCs the first value into hRandomAdd, then SBCs
  the second value from hRandomSub.
* Wild enemy DVs use two consecutive BattleRandom calls. The first result is
  stored as the raw-DV LOW byte and the second as the raw-DV HIGH byte.
* The final sampled frame also contains the ordinary VBlank Random update.

Accordingly the source-backed final-frame model is:

    VBlank Random -> BattleRandom(DV low) -> BattleRandom(DV high)

The solver keeps the small sub-DIV ambiguities visible instead of pretending we
already know the exact sub-256-cycle phase.
"""

from __future__ import annotations

import argparse
import csv
import io
from dataclasses import dataclass
from pathlib import Path

# A Random_ first->second rDIV read is well below one DIV-byte period. Across a
# byte boundary the visible second read can therefore be the same byte or +1.
SECOND_READ_GAPS = (0, 1)

# Consecutive BattleRandom first reads are close enough that current traces
# admit +1 or +2 visible DIV-byte increments. +2 gives the tight representative
# profile seen repeatedly, but both remain candidates until a direct subphase
# marker is validated.
BATTLE_FIRST_GAPS = (1, 2)


@dataclass(frozen=True)
class Frame:
    seq: int
    add: int
    sub: int
    frame: int
    div: int
    raw_dv: int
    joy_held: int


@dataclass
class Trial:
    path: Path
    meta: dict[str, str]
    frames: list[Frame]
    gbrel: dict[str, str] | None


@dataclass(frozen=True)
class Call:
    first_off: int
    second_off: int
    carry_in: int
    add_out: int
    sub_out: int


@dataclass(frozen=True)
class Solution:
    vblank: Call
    dv_low: Call
    dv_high: Call

    @property
    def first_profile(self) -> tuple[int, int, int]:
        return (self.vblank.first_off, self.dv_low.first_off, self.dv_high.first_off)


def hx(v: str) -> int:
    return int(v, 16)


def dec(v: str) -> int:
    return int(v, 10)


def load_trial(path: Path) -> Trial:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 4 or not lines[0].startswith("meta,"):
        raise ValueError("not a Blue Mewtwo v7-family CSV")

    meta_hdr = next(csv.reader([lines[0]]))
    meta_row = next(csv.reader([lines[1]]))
    meta = dict(zip(meta_hdr, meta_row))

    frame_i = next(i for i, line in enumerate(lines) if line.startswith("seq,rel,rng_add,"))
    gb_i = next((i for i, line in enumerate(lines) if line.startswith("gb_release_meta,")), len(lines))
    frame_text = "\n".join(lines[frame_i:gb_i])
    frame_rows = list(csv.DictReader(io.StringIO(frame_text)))
    frames = [
        Frame(
            seq=dec(r["seq"]),
            add=hx(r["rng_add"]),
            sub=hx(r["rng_sub"]),
            frame=hx(r["frame"]),
            div=hx(r["div"]),
            raw_dv=hx(r["raw_dv"]),
            joy_held=hx(r["joy_held"]),
        )
        for r in frame_rows
        if r.get("seq")
    ]

    gbrel = None
    if gb_i < len(lines) - 1:
        hdr = next(csv.reader([lines[gb_i]]))
        row = next(csv.reader([lines[gb_i + 1]]))
        gbrel = dict(zip(hdr, row))

    return Trial(path=path, meta=meta, frames=frames, gbrel=gbrel)


def infer_release_seq(t: Trial) -> int | None:
    if t.gbrel and t.gbrel.get("seq"):
        return dec(t.gbrel["seq"])

    # Backward compatibility for stable v7.2: infer the first GB-side
    # hJoyHeld.A 1->0 transition after the Final-A trigger.
    trigger = dec(t.meta["trigger_seq"])
    prev_held: bool | None = None
    for f in t.frames:
        if f.seq < trigger:
            continue
        held = bool(f.joy_held & 1)
        if prev_held is True and not held:
            return f.seq
        prev_held = held
    return None


def frame_by_seq(t: Trial, seq: int) -> Frame | None:
    return next((f for f in t.frames if f.seq == seq), None)


def apply_random(add0: int, sub0: int, d1: int, d2: int, carry_in: int) -> tuple[int, int]:
    total = add0 + d1 + carry_in
    add1 = total & 0xFF
    adc_carry = 1 if total > 0xFF else 0
    sub1 = (sub0 - d2 - adc_carry) & 0xFF
    return add1, sub1


def unfolded_span(pre_div: int, battle_div: int) -> int:
    """Unfold one GB frame of the visible high DIV byte.

    70224 T-cycles/frame / 256 cycles per high-DIV increment = 274.3125. The
    observed final-frame modular delta is therefore normally 18 or 19, which is
    274 or 275 after restoring the one full wrap.
    """
    mod = (battle_div - pre_div) & 0xFF
    if mod <= 64:
        return mod + 256
    # Defensive fallback for an unusual trace. Keep the smallest positive span;
    # the caller will visibly flag it as non-standard.
    return mod


def offsets_for_value(base_div: int, value: int, span: int) -> list[int]:
    return [off for off in range(span + 1) if ((base_div + off) & 0xFF) == value]


def solve_source_three_call(pre: Frame, battle: Frame, raw: int, vblank_carry: int = 0) -> list[Solution]:
    """Enumerate source-backed VBlank + two BattleRandom solutions.

    BattleRandom's two output bytes constrain the first rDIV read strongly:
      DV-low first DIV = low - AddAfterVBlank - 1
      DV-high first DIV = high - low - 1

    The `+1` is the carry entering the battle Random_ path. We retain the
    second-read 0/+1 ambiguity and the consecutive battle first-read +1/+2
    ambiguity.
    """
    low = raw & 0xFF
    high = (raw >> 8) & 0xFF
    span = unfolded_span(pre.div, battle.div)
    if not (250 <= span <= 300):
        return []

    # The second BattleRandom starts with hRandomAdd == low.
    dv_high_d1 = (high - low - 1) & 0xFF
    high_first_offsets = offsets_for_value(pre.div, dv_high_d1, span)

    out: list[Solution] = []

    # VBlank first rDIV read can occur anywhere before the two DV calls. The
    # eventual low/high bytes reduce this to only a few surviving offsets.
    for v1_off in range(span + 1):
        v1 = (pre.div + v1_off) & 0xFF
        for vg in SECOND_READ_GAPS:
            v2_off = v1_off + vg
            if v2_off > span:
                continue
            v2 = (pre.div + v2_off) & 0xFF
            va, vs = apply_random(pre.add, pre.sub, v1, v2, vblank_carry)

            # First BattleRandom must output raw low byte. Carry-in is 1 on the
            # normal non-link battle path immediately entering Random_.
            low_d1 = (low - va - 1) & 0xFF
            for low1_off in offsets_for_value(pre.div, low_d1, span):
                if low1_off < v2_off:
                    continue

                for high1_off in high_first_offsets:
                    if high1_off < low1_off:
                        continue
                    if high1_off - low1_off not in BATTLE_FIRST_GAPS:
                        continue

                    for lg in SECOND_READ_GAPS:
                        low2_off = low1_off + lg
                        if low2_off > high1_off:
                            continue
                        la, ls = apply_random(
                            va,
                            vs,
                            (pre.div + low1_off) & 0xFF,
                            (pre.div + low2_off) & 0xFF,
                            1,
                        )
                        if la != low:
                            continue

                        for hg in SECOND_READ_GAPS:
                            high2_off = high1_off + hg
                            if high2_off > span:
                                continue
                        
                            ha, hs = apply_random(
                                la,
                                ls,
                                (pre.div + high1_off) & 0xFF,
                                (pre.div + high2_off) & 0xFF,
                                1,
                            )
                            if ha != high or hs != battle.sub:
                                continue

                            out.append(
                                Solution(
                                    vblank=Call(v1_off, v2_off, vblank_carry, va, vs),
                                    dv_low=Call(low1_off, low2_off, 1, la, ls),
                                    dv_high=Call(high1_off, high2_off, 1, ha, hs),
                                )
                            )
    return out


def solve_two_battle_only(pre: Frame, battle: Frame, raw: int) -> int:
    """Control model: pretend the final frame had only the two DV calls."""
    low = raw & 0xFF
    high = (raw >> 8) & 0xFF
    span = unfolded_span(pre.div, battle.div)
    if not (250 <= span <= 300):
        return 0

    low_d1 = (low - pre.add - 1) & 0xFF
    high_d1 = (high - low - 1) & 0xFF
    count = 0
    for l1 in offsets_for_value(pre.div, low_d1, span):
        for h1 in offsets_for_value(pre.div, high_d1, span):
            if h1 - l1 not in BATTLE_FIRST_GAPS:
                continue
            for lg in SECOND_READ_GAPS:
                l2 = l1 + lg
                if l2 > h1:
                    continue
                la, ls = apply_random(pre.add, pre.sub, (pre.div + l1) & 0xFF, (pre.div + l2) & 0xFF, 1)
                if la != low:
                    continue
                for hg in SECOND_READ_GAPS:
                    h2 = h1 + hg
                    if h2 > span:
                        continue
                    ha, hs = apply_random(la, ls, (pre.div + h1) & 0xFF, (pre.div + h2) & 0xFF, 1)
                    if ha == high and hs == battle.sub:
                        count += 1
    return count


def unique_profiles(solutions: list[Solution]) -> list[tuple[int, int, int]]:
    return sorted({s.first_profile for s in solutions})


def preferred_two_tick_profiles(solutions: list[Solution]) -> list[tuple[int, int, int]]:
    # Useful representative: retain solutions where consecutive BattleRandom
    # first reads are two visible DIV ticks apart. This is an empirical/profile
    # label, not yet a claim of unique subphase truth.
    return sorted({s.first_profile for s in solutions if s.dv_high.first_off - s.dv_low.first_off == 2})


def analyze_trial(t: Trial) -> bool:
    raw = hx(t.meta["raw_dv"])
    battle_seq = dec(t.meta["battle_seq"])
    dvwrite_seq = dec(t.meta["dvwrite_seq"])
    pre = frame_by_seq(t, dvwrite_seq - 1)
    battle = frame_by_seq(t, battle_seq)
    release_seq = infer_release_seq(t)

    print(f"\n== {t.path.name} ==")
    print(f"RAW {raw:04X}  release Q{release_seq or 0}  DV Q{battle_seq}")
    if release_seq is not None:
        print(f"GBREL->DV {battle_seq - release_seq}F")

    if pre is None or battle is None:
        print("ERROR: final pre/battle rows unavailable")
        return False

    span = unfolded_span(pre.div, battle.div)
    print(
        f"FINAL pre {pre.add:02X}/{pre.sub:02X} D{pre.div:02X}"
        f" -> battle {battle.add:02X}/{battle.sub:02X} D{battle.div:02X}"
        f" | unfolded DIV +{span}"
    )
    print(f"battle Add == raw high: {'YES' if battle.add == (raw >> 8) else 'NO'}")

    sols0 = solve_source_three_call(pre, battle, raw, vblank_carry=0)
    sols1 = solve_source_three_call(pre, battle, raw, vblank_carry=1)
    two = solve_two_battle_only(pre, battle, raw)

    profiles0 = unique_profiles(sols0)
    pref0 = preferred_two_tick_profiles(sols0)
    print(f"2-call control: {two} solution(s)")
    print(f"3-call source model, VBlank carry0: {len(sols0)} solution(s)")
    print("  first-read profiles: " + (", ".join(f"V+{v}/L+{l}/H+{h}" for v, l, h in profiles0) or "none"))
    if pref0:
        print("  2-tick representatives: " + ", ".join(f"V+{v}/L+{l}/H+{h}" for v, l, h in pref0))
    if not sols0 and sols1:
        profiles1 = unique_profiles(sols1)
        print("  carry1 alternative survives: " + ", ".join(f"V+{v}/L+{l}/H+{h}" for v, l, h in profiles1))

    # Direct, carry-independent constraint from the second BattleRandom.
    low = raw & 0xFF
    high = (raw >> 8) & 0xFF
    d2_first = (high - low - 1) & 0xFF
    d2_offs = offsets_for_value(pre.div, d2_first, span)
    print(f"DV-high BattleRandom first DIV = {d2_first:02X} => offset(s) {d2_offs}")

    ok = bool(sols0) and battle.add == high
    print("VERDICT: " + ("3-call microphase CONSISTENT" if ok else "needs review"))
    return ok


# Known v7/v7.2 final-frame states from traces 0011-0020. This is a regression
# test for the unfolded-DIV/source-structure model, not training data for a
# future shiny predictor.
SELFTEST = [
    # name, pre_add, pre_sub, pre_div, battle_add, battle_sub, battle_div, raw
    ("0011", 0x4E, 0x58, 0xDC, 0xB6, 0xF0, 0xEE, 0xB67F),
    ("0012", 0x83, 0xE8, 0x15, 0x98, 0xD4, 0x27, 0x9827),
    ("0013", 0xA0, 0x52, 0xA7, 0x74, 0x7E, 0xBA, 0x746E),
    ("0014", 0x85, 0x27, 0xBE, 0x93, 0x19, 0xD0, 0x937A),
    ("0015", 0x30, 0x16, 0x5D, 0x1C, 0x29, 0x6F, 0x1C64),
    ("0016", 0x4A, 0x69, 0xD6, 0xA0, 0x13, 0xE8, 0xA06F),
    ("0017", 0x99, 0x32, 0x14, 0xA9, 0x23, 0x26, 0xA93A),
    ("0018", 0x6B, 0x45, 0x37, 0xE4, 0xCD, 0x49, 0xE452),
    ("0019", 0x9D, 0xE8, 0x01, 0x7F, 0x06, 0x14, 0x7F1F),
    ("0020", 0xFA, 0xC9, 0xF4, 0xAD, 0x17, 0x07, 0xAD5D),
]


def selftest() -> bool:
    three_ok = 0
    two_ok = 0
    representatives: dict[str, list[tuple[int, int, int]]] = {}
    for name, pa, ps, pd, ba, bs, bd, raw in SELFTEST:
        pre = Frame(0, pa, ps, 0, pd, 0, 0)
        battle = Frame(1, ba, bs, 0, bd, raw, 0)
        sols = solve_source_three_call(pre, battle, raw, 0)
        two = solve_two_battle_only(pre, battle, raw)
        three_ok += bool(sols)
        two_ok += bool(two)
        representatives[name] = preferred_two_tick_profiles(sols)

    print(f"selftest 3-call carry0: {three_ok}/{len(SELFTEST)}")
    print(f"selftest 2-call control: {two_ok}/{len(SELFTEST)}")
    for name in sorted(representatives):
        p = representatives[name]
        print(name + " " + (",".join(f"{v}/{l}/{h}" for v, l, h in p) or "no-2tick-rep"))
    return three_ok == len(SELFTEST) and two_ok == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="*", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest() else 1
    if not args.csv:
        ap.error("provide one or more mewtwo_trace CSVs, or --selftest")

    ok = True
    for path in args.csv:
        try:
            ok &= analyze_trial(load_trial(path))
        except Exception as e:
            print(f"{path}: ERROR {e}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
