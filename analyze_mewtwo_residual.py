#!/usr/bin/env python3
"""Analyze Japanese VC Blue Mewtwo PRED -> ACT raw-DV residuals.

The hardware validation data shows the two DV bytes moving by nearly the same
mod-256 amount.  This script treats that common additive residual as the first
hypothesis to test before introducing a discrete RNG-call shift.

Examples:
  python3 analyze_mewtwo_residual.py
  python3 analyze_mewtwo_residual.py --pair BAAA:4939
  python3 analyze_mewtwo_residual.py --delta 8F
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

SHINY_ATK = {2, 3, 6, 7, 10, 11, 14, 15}

# Recovered from real-hardware Mewtwo HUNT validation screens.
# The third ACT was BEC8 on the screen: residual +1F / +1E.
KNOWN = [
    (0x0575, 0x1281, "validation A"),
    (0x1AF9, 0x5B3B, "validation B"),
    (0x9FAA, 0xBEC8, "validation C"),
    (0xBAAA, 0x4939, "shiny-target miss"),
]


@dataclass(frozen=True)
class Residual:
    pred: int
    act: int
    d1: int
    d2: int
    common: int
    spread: int
    label: str


def parse_raw(text: str) -> int:
    s = text.strip().upper().replace("0X", "").replace("$", "")
    if len(s) != 4 or any(c not in "0123456789ABCDEF" for c in s):
        raise argparse.ArgumentTypeError("raw DV must be 4 hex digits")
    return int(s, 16)


def signed8(x: int) -> int:
    x &= 0xFF
    return x - 256 if x >= 128 else x


def circular_distance(a: int, b: int) -> int:
    return abs(signed8((a - b) & 0xFF))


def residual(pred: int, act: int, label: str = "") -> Residual:
    p1, p2 = (pred >> 8) & 0xFF, pred & 0xFF
    a1, a2 = (act >> 8) & 0xFF, act & 0xFF
    d1, d2 = (a1 - p1) & 0xFF, (a2 - p2) & 0xFF
    spread = circular_distance(d1, d2)
    # If the two bytes are adjacent around the u8 ring, use d1 as the canonical
    # residual.  Otherwise retain d1 but mark the pair non-uniform via spread.
    return Residual(pred, act, d1, d2, d1, spread, label)


def add_delta(raw: int, delta: int) -> int:
    hi = (((raw >> 8) & 0xFF) + delta) & 0xFF
    lo = ((raw & 0xFF) + delta) & 0xFF
    return (hi << 8) | lo


def sub_delta(raw: int, delta: int) -> int:
    return add_delta(raw, (-delta) & 0xFF)


def shiny(raw: int) -> bool:
    atk = (raw >> 12) & 0xF
    de = (raw >> 8) & 0xF
    spe = (raw >> 4) & 0xF
    spc = raw & 0xF
    return de == 10 and spe == 10 and spc == 10 and atk in SHINY_ATK


def shiny_raws() -> list[int]:
    return [(atk << 12) | 0x0AAA for atk in sorted(SHINY_ATK)]


def fmt(raw: int) -> str:
    return f"{raw & 0xFFFF:04X}"


def report_pair(pred: int, act: int, label: str = "") -> Residual:
    r = residual(pred, act, label)
    status = "COMMON" if r.spread == 0 else ("COMMON±1" if r.spread == 1 else "NON-UNIFORM")
    print(
        f"{label or 'pair':18s} {fmt(pred)} -> {fmt(act)}  "
        f"delta={r.d1:02X}/{r.d2:02X}  spread={r.spread}  {status}"
    )
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--pair",
        action="append",
        default=[],
        metavar="PRED:ACT",
        help="additional 4-hex-digit raw DV pair; may be repeated",
    )
    ap.add_argument(
        "--delta",
        type=lambda s: int(s, 16) & 0xFF,
        help="calibrated common residual; list model-predicted preimages that would become shiny",
    )
    args = ap.parse_args()

    rows = [report_pair(p, a, label) for p, a, label in KNOWN]
    for i, text in enumerate(args.pair, 1):
        try:
            p, a = text.split(":", 1)
        except ValueError as exc:
            raise SystemExit("--pair must be PRED:ACT") from exc
        rows.append(report_pair(parse_raw(p), parse_raw(a), f"user {i}"))

    tight = [r for r in rows if r.spread <= 1]
    print()
    print(f"common-residual evidence: {len(tight)}/{len(rows)} pairs have byte spread <= 1")
    if len(tight) == len(rows):
        print("primary hypothesis: shared DIV/phase timing offset; do not call this random model failure")
    else:
        print("at least one pair is not explained by a single shared byte residual")

    if args.delta is not None:
        d = args.delta
        print()
        print(f"For calibrated delta {d:02X}, search the old predictor for these PREIMAGE raw DVs:")
        for actual in shiny_raws():
            pred = sub_delta(actual, d)
            check = add_delta(pred, d)
            assert check == actual and shiny(actual)
            print(f"  predictor {fmt(pred)}  -> corrected ACT {fmt(actual)} SHINY")


if __name__ == "__main__":
    main()
