#!/usr/bin/env python3
"""Analyze the v3.4 same-VBlank 02B6 -> 02BE differential section.

The script intentionally does not assume that the VC stores the Game Boy
internal divider as a literal little-endian u16.  It ranks changed addresses by:
  * a u16 view whose visible byte agrees with start_div/end_div,
  * increments close to plausible 48 T-cycle / 12 M-cycle scales,
  * small monotonic counter-like changes,
  * adjacency with other changed bytes.

Usage:
    python3 analyze_div_diff.py celebi_trace_0060.csv
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

EXPECTED = (48, 24, 12, 6, 3, 1)


def hx(v: int, width: int) -> str:
    return f"{v & ((1 << (width*4))-1):0{width}X}"


def wrap_distance(value: int, expected: int, bits: int) -> int:
    mod = 1 << bits
    value %= mod
    expected %= mod
    return min((value - expected) % mod, (expected - value) % mod)


def parse_int(s: str, base=10) -> int:
    return int(s.strip(), base)


@dataclass
class Meta:
    base: int
    length: int
    valid: int
    completed: int
    pair_ok: int
    start_pc: int
    end_pc: int
    start_adv: int
    end_adv: int
    start_div: int
    end_div: int
    start_tick: int
    end_tick: int
    total: int
    stored: int
    overflow: int


@dataclass
class Row:
    index: int
    address: int
    offset: int
    before: int
    after: int
    d8: int
    b16: int
    a16: int
    d16: int
    b32: int
    a32: int
    d32: int

    @property
    def b16be(self) -> int:
        return ((self.b16 & 0xFF) << 8) | (self.b16 >> 8)

    @property
    def a16be(self) -> int:
        return ((self.a16 & 0xFF) << 8) | (self.a16 >> 8)

    @property
    def d16be(self) -> int:
        return (self.a16be - self.b16be) & 0xFFFF


def load(path: Path) -> tuple[Meta, list[Row]]:
    lines = path.read_text(errors="replace").splitlines()
    try:
        mh = next(i for i, l in enumerate(lines) if l.startswith("diff_region,"))
    except StopIteration:
        raise SystemExit("diff_region section not found: this is not a v3.4 CSV")
    if mh + 1 >= len(lines):
        raise SystemExit("diff metadata row missing")

    m = next(csv.reader([lines[mh + 1]]))
    if not m or m[0] != "DIFF":
        raise SystemExit("invalid diff metadata row")
    meta = Meta(
        base=parse_int(m[1], 16), length=parse_int(m[2]), valid=parse_int(m[3]),
        completed=parse_int(m[4]), pair_ok=parse_int(m[5]),
        start_pc=parse_int(m[6], 16), end_pc=parse_int(m[7], 16),
        start_adv=parse_int(m[8]), end_adv=parse_int(m[9]),
        start_div=parse_int(m[10], 16), end_div=parse_int(m[11], 16),
        start_tick=parse_int(m[12]), end_tick=parse_int(m[13]),
        total=parse_int(m[14]), stored=parse_int(m[15]), overflow=parse_int(m[16]),
    )

    try:
        rh = next(i for i in range(mh + 2, len(lines)) if lines[i].startswith("diff_index,"))
    except StopIteration:
        raise SystemExit("diff row header missing")

    rows: list[Row] = []
    for line in lines[rh + 1:]:
        if not line.strip() or not line[0].isdigit():
            break
        c = next(csv.reader([line]))
        if len(c) < 12:
            continue
        rows.append(Row(
            index=parse_int(c[0]), address=parse_int(c[1], 16), offset=parse_int(c[2], 16),
            before=parse_int(c[3], 16), after=parse_int(c[4], 16), d8=parse_int(c[5], 16),
            b16=parse_int(c[6], 16), a16=parse_int(c[7], 16), d16=parse_int(c[8], 16),
            b32=parse_int(c[9], 16), a32=parse_int(c[10], 16), d32=parse_int(c[11], 16),
        ))
    return meta, rows


def score(row: Row, meta: Meta, changed: set[int]) -> tuple[int, list[str]]:
    score = 0
    why: list[str] = []

    # Strongest test: a literal internal 16-bit divider beginning here.
    if (row.b16 >> 8) == meta.start_div and (row.a16 >> 8) == meta.end_div:
        score += 120
        why.append("LE16 high=DIV")
    if (row.b16be >> 8) == meta.start_div and (row.a16be >> 8) == meta.end_div:
        score += 120
        why.append("BE16 high=DIV")

    # 48 T-cycles is the primary hypothesis; 12 is the same interval in M-cycles.
    for exp in EXPECTED:
        d = wrap_distance(row.d8, exp, 8)
        if d == 0:
            score += 35 if exp in (48, 12) else 18
            why.append(f"d8~{exp}")
            break
        if d <= 2:
            score += 12
            why.append(f"d8 near {exp}")
            break

    for name, delta, bits in (("d16", row.d16, 16), ("d16be", row.d16be, 16), ("d32", row.d32, 32)):
        for exp in EXPECTED:
            d = wrap_distance(delta, exp, bits)
            if d == 0:
                score += 28 if exp in (48, 12) else 12
                why.append(f"{name}={exp}")
                break
            if d <= 2:
                score += 8
                why.append(f"{name} near {exp}")
                break

    # Counters tend to change in compact clusters rather than isolated pointers.
    neighbours = sum((row.address + d) in changed for d in (-2, -1, 1, 2))
    if neighbours:
        score += min(neighbours * 4, 12)
        why.append(f"adj{neighbours}")

    # Tiny toggles and flags are useful diagnostics but weak counter candidates.
    signed8 = row.d8 if row.d8 < 0x80 else row.d8 - 0x100
    if abs(signed8) <= 2:
        score -= 4

    return score, why


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_div_diff.py <trace.csv>")
    path = Path(sys.argv[1])
    meta, rows = load(path)

    print(f"file: {path.name}")
    print(
        f"region=0x{meta.base:08X}-0x{meta.base + meta.length - 1:08X} "
        f"valid={meta.valid} completed={meta.completed} pair_ok={meta.pair_ok}"
    )
    print(
        f"pair: pc {meta.start_pc:04X}->{meta.end_pc:04X}, "
        f"advance {meta.start_adv}->{meta.end_adv}, DIV {meta.start_div:02X}->{meta.end_div:02X}, "
        f"host_tick_delta={meta.end_tick-meta.start_tick}"
    )
    print(f"changes: total={meta.total}, stored={meta.stored}, overflow={meta.overflow}")

    if not meta.valid:
        print("RESULT: region was not fully mapped; do not interpret this run.")
        return
    if not meta.completed or not meta.pair_ok:
        print("RESULT: no clean same-VBlank pair was completed; retry before interpreting candidates.")
        return
    if meta.total == 0:
        print("RESULT: no persistent byte in this 64 KiB region changed between 02B6 and 02BE.")
        return
    if meta.overflow:
        print("WARNING: changed-byte list overflowed; candidates after the stored prefix may be missing.")

    changed = {r.address for r in rows}
    ranked = []
    for r in rows:
        sc, why = score(r, meta, changed)
        ranked.append((sc, r, why))
    ranked.sort(key=lambda x: (-x[0], x[1].address))

    print("\nTop candidates")
    print("score address    byte    d8  LE16->LE16 d16   LE32->LE32         d32       reasons")
    for sc, r, why in ranked[:40]:
        print(
            f"{sc:5d} 0x{r.address:08X} {r.before:02X}->{r.after:02X} {r.d8:02X}  "
            f"{r.b16:04X}->{r.a16:04X} {r.d16:04X}  "
            f"{r.b32:08X}->{r.a32:08X} {r.d32:08X}  {'; '.join(why) or '-'}"
        )

    literal = [x for x in ranked if "LE16 high=DIV" in x[2] or "BE16 high=DIV" in x[2]]
    print("\nLiteral DIV-shaped candidates:", len(literal))
    for sc, r, why in literal[:20]:
        print(f"  0x{r.address:08X} score={sc} {', '.join(why)}")

    print("\nInterpretation:")
    if literal:
        print("  At least one changed location has a 16-bit view whose high byte follows rDIV.")
        print("  Verify the best address with a lightweight targeted probe before using it as ASUB/SSUB.")
    else:
        print("  No literal 16-bit divider begins at a stored changed byte in this region.")
        print("  Inspect the ranked small-delta counters; if none are convincing, move to the next region.")


if __name__ == "__main__":
    main()
