#!/usr/bin/env python3
"""Prepare the relocated JP VC Blue phase-probe build.

This intentionally changes only three compile-time literals in blue_dvtrace.c:
- legacy Crystal-style candidate 0x0022F604 -> translated Blue candidate 0x0021B608
- probe window 0x0022F400 -> 0x0021B500 (1 KiB, ending at 0x0021B8FF)
- CSV probe version 9 -> 10

The script is idempotent so repeated `make` invocations are safe.
"""
from pathlib import Path

PATH = Path("3gx/sources/blue_dvtrace.c")

REPLACEMENTS = (
    ("#define F604_CANDIDATE_ADDR 0x0022F604u", "#define F604_CANDIDATE_ADDR 0x0021B608u"),
    ("#define PHASE_PROBE_BASE       0x0022F400u", "#define PHASE_PROBE_BASE       0x0021B500u"),
    ('"MEWTWO,9,', '"MEWTWO,10,'),
)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new, 1)
        elif new not in text:
            raise SystemExit(f"expected probe literal not found: {old}")
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
