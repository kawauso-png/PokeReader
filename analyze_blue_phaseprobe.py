#!/usr/bin/env python3
"""Rank candidates from the bounded Blue VC phase-probe section.

Input is a mewtwo_trace CSV produced by the v9/v7.3.7 discovery build.
The runtime probe is deliberately dumb/read-only; this script does all ranking
offline so no prediction or control decision is added to the 3GX.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Candidate:
    address: int
    transitions: int
    step20: int
    divrule: int
    range0_63: int
    changes: int
    values: list[int]

    @property
    def exact(self) -> bool:
        return self.transitions > 0 and self.step20 == self.transitions and self.divrule == self.transitions

    @property
    def score(self) -> tuple[int, int, int, int, int]:
        # Exact timing physics first; changing/range are supporting evidence.
        return (self.step20 + self.divrule, self.step20, self.divrule, self.changes, self.range0_63)


def parse(path: Path) -> list[Candidate]:
    rows = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[Candidate] = []
    for line in rows:
        if not line.startswith("PHASE,"):
            continue
        p = next(csv.reader([line]))
        if len(p) < 7:
            continue
        try:
            vals = [int(x, 16) for x in p[7:] if x != ""]
            out.append(Candidate(
                address=int(p[1], 16),
                transitions=int(p[2]),
                step20=int(p[3]),
                divrule=int(p[4]),
                range0_63=int(p[5]),
                changes=int(p[6]),
                values=vals,
            ))
        except ValueError:
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    path = Path(args.trace)
    cands = parse(path)
    if not cands:
        raise SystemExit("No PHASE rows found; use a v7.3.7/v9 phase-probe trace")

    exact = [c for c in cands if c.exact and c.changes > 0]
    ranked = sorted(cands, key=lambda c: c.score, reverse=True)

    print(f"{path.name}: {len(cands)} addresses")
    print(f"exact changing candidates: {len(exact)}")
    for c in sorted(exact, key=lambda c: (c.range0_63, c.changes), reverse=True):
        values = " ".join(f"{v:02X}" for v in c.values)
        print(f"EXACT 0x{c.address:08X} step={c.step20}/{c.transitions} "
              f"div={c.divrule}/{c.transitions} range={c.range0_63} change={c.changes} :: {values}")

    print(f"\nTop {min(args.top, len(ranked))}:")
    for c in ranked[:args.top]:
        values = " ".join(f"{v:02X}" for v in c.values)
        print(f"0x{c.address:08X} step={c.step20}/{c.transitions} "
              f"div={c.divrule}/{c.transitions} range={c.range0_63} change={c.changes} :: {values}")


if __name__ == "__main__":
    main()
