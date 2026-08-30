#!/usr/bin/env python3
"""Analyze Japanese VC Blue Mewtwo final-frame RNG microphase.

Input: one or more v7/v7.2/v7.3.1 Mewtwo CSVs.

The ordinary frame trace already gives the state immediately before the DV
write and the state after it. Gen-I Random_ performs two rDIV reads per call:

    hRandomAdd <- hRandomAdd + DIV1 + carry-in
    hRandomSub <- hRandomSub - DIV2 - carry-from-ADC

The last two Random outputs become the two Mewtwo DV bytes in the empirically
observed order low-byte then high-byte. This script enumerates 2/3/4-call
hypotheses inside the final sampled frame, requiring monotonic rDIV reads and a
small first-read -> second-read gap.

It does not patch or hook the emulator. It is an offline consistency solver.
"""

from __future__ import annotations

import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_READ_GAP = 2
MAX_REPRESENTATIVES = 8


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


def hx(v: str) -> int:
    return int(v, 16)


def dec(v: str) -> int:
    return int(v, 10)


def read_section(lines: list[str], header_i: int, end_i: int) -> list[dict[str, str]]:
    text = "\n".join(lines[header_i:end_i])
    return list(csv.DictReader(io.StringIO(text)))


def load_trial(path: Path) -> Trial:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 4 or not lines[0].startswith("meta,"):
        raise ValueError("not a Blue Mewtwo v7-family CSV")

    meta_hdr = next(csv.reader([lines[0]]))
    meta_row = next(csv.reader([lines[1]]))
    meta = dict(zip(meta_hdr, meta_row))

    frame_i = next(i for i, line in enumerate(lines) if line.startswith("seq,rel,rng_add,"))
    gb_i = next((i for i, line in enumerate(lines) if line.startswith("gb_release_meta,")), len(lines))
    frame_rows = read_section(lines, frame_i, gb_i)
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

    return Trial(path, meta, frames, gbrel)


def infer_release_seq(t: Trial) -> int | None:
    if t.gbrel and t.gbrel.get("seq"):
        return dec(t.gbrel["seq"])
    # Backward-compatible v7.2 inference: first hJoyHeld.A 1->0 after trigger.
    trigger = dec(t.meta["trigger_seq"])
    prev = None
    for f in t.frames:
        if f.seq < trigger:
            continue
        held = bool(f.joy_held & 1)
        if prev is True and not held:
            return f.seq
        prev = held
    return None


def frame_by_seq(t: Trial, seq: int) -> Frame | None:
    return next((f for f in t.frames if f.seq == seq), None)


def div_at(base: int, off: int) -> int:
    return (base + off) & 0xFF


def allowed_d1_offsets(base_div: int, last_off: int, span: int, target_div: int | None):
    if target_div is None:
        return range(last_off, span + 1)
    wanted = (target_div - base_div) & 0xFF
    if last_off <= wanted <= span:
        return (wanted,)
    return ()


def solve_calls(pre: Frame, battle: Frame, raw: int, calls: int):
    """Return (solution_count, representative_paths).

    A state is (add, sub, last_div_offset). For constrained final calls, the
    required Add output lets us derive DIV1 directly instead of brute-forcing it.
    Each representative call tuple is:
      (DIV1, DIV2, carry_in, add_out, sub_out)
    """
    lo = raw & 0xFF
    hi = (raw >> 8) & 0xFF
    span = (battle.div - pre.div) & 0xFF
    if span > 64:
        # One host-frame rDIV advance should be small. A huge modular span means
        # this trial is not suitable for the simple final-frame model.
        return 0, [], span

    # key -> (number of ways, one representative path)
    states: dict[tuple[int, int, int], tuple[int, tuple]] = {
        (pre.add, pre.sub, 0): (1, ())
    }

    for ci in range(calls):
        next_states: dict[tuple[int, int, int], tuple[int, tuple]] = {}
        target_add = None
        if ci == calls - 2:
            target_add = lo
        elif ci == calls - 1:
            target_add = hi

        for (add0, sub0, last_off), (ways, path) in states.items():
            for carry_in in (0, 1):
                if target_add is None:
                    d1_offsets = allowed_d1_offsets(pre.div, last_off, span, None)
                else:
                    required_d1 = (target_add - add0 - carry_in) & 0xFF
                    d1_offsets = allowed_d1_offsets(pre.div, last_off, span, required_d1)

                for o1 in d1_offsets:
                    d1 = div_at(pre.div, o1)
                    total = add0 + d1 + carry_in
                    add1 = total & 0xFF
                    carry_adc = 1 if total > 0xFF else 0
                    if target_add is not None and add1 != target_add:
                        continue

                    for o2 in range(o1, min(span, o1 + MAX_READ_GAP) + 1):
                        d2 = div_at(pre.div, o2)
                        sub1 = (sub0 - d2 - carry_adc) & 0xFF
                        key = (add1, sub1, o2)
                        call = (d1, d2, carry_in, add1, sub1)
                        old = next_states.get(key)
                        if old is None:
                            next_states[key] = (ways, path + (call,))
                        else:
                            next_states[key] = (old[0] + ways, old[1])
        states = next_states
        if not states:
            break

    total_solutions = 0
    reps: list[tuple] = []
    for (add, sub, _last), (ways, path) in states.items():
        if add == battle.add and sub == battle.sub:
            total_solutions += ways
            if len(reps) < MAX_REPRESENTATIVES:
                reps.append(path)
    return total_solutions, reps, span


def fmt_path(path: tuple) -> str:
    chunks = []
    for i, (d1, d2, cin, a, s) in enumerate(path, 1):
        chunks.append(f"C{i}:D{d1:02X}/{d2:02X} c{cin} -> {a:02X}/{s:02X}")
    return " | ".join(chunks)


def analyze(t: Trial) -> int:
    raw = hx(t.meta["raw_dv"])
    battle_seq = dec(t.meta["battle_seq"])
    dvwrite_seq = dec(t.meta["dvwrite_seq"])
    pre_seq = dvwrite_seq - 1
    pre = frame_by_seq(t, pre_seq)
    battle = frame_by_seq(t, battle_seq)
    release_seq = infer_release_seq(t)

    print(f"\n== {t.path.name} ==")
    print(f"RAW {raw:04X}  release Q{release_seq if release_seq else 0}  DV Q{battle_seq}")
    if release_seq:
        print(f"GBREL->DV {battle_seq - release_seq}F")

    if pre is None or battle is None:
        print("ERROR: pre/battle frame rows unavailable")
        return 1

    print(
        f"FINAL FRAME pre Q{pre.seq} {pre.add:02X}/{pre.sub:02X} F{pre.frame:02X} D{pre.div:02X}"
        f" -> battle Q{battle.seq} {battle.add:02X}/{battle.sub:02X} F{battle.frame:02X} D{battle.div:02X}"
    )
    print(f"final Add == DV high: {'YES' if battle.add == (raw >> 8) else 'NO'}")

    found = []
    for calls in (2, 3, 4):
        count, reps, span = solve_calls(pre, battle, raw, calls)
        print(f"{calls}-call hypothesis: {count} candidate(s), DIV span +{span}")
        for p in reps[:3]:
            print("  " + fmt_path(p))
        if count:
            found.append(calls)

    if found == [3]:
        print("VERDICT: final-frame 3-call model uniquely survives this trial")
    elif found:
        print("VERDICT: surviving call counts = " + ",".join(map(str, found)))
    else:
        print("VERDICT: no 2/3/4-call solution under current DIV-gap assumptions")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: analyze_mewtwo_microphase.py mewtwo_trace_XXXX.csv [...]", file=sys.stderr)
        return 2
    rc = 0
    for arg in sys.argv[1:]:
        try:
            rc |= analyze(load_trial(Path(arg)))
        except Exception as e:
            print(f"{arg}: ERROR {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
