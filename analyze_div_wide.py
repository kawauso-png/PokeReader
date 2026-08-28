#!/usr/bin/env python3
"""Locate candidate internal DIV-counter bytes from a Deep Probe v3.2 CSV.

The CSV is a concatenation of several tables.  v3.2 appends a `wide_index,...`
section containing eight first-VBlank samples.  This script searches both the
1 KiB emulator-context window and the 512-byte neighbourhood around the host
rDIV byte pointer for a 16-bit value whose high byte equals the observed DIV
and whose frame-to-frame delta matches 0x1250 per RNG advance.

Usage:
    python3 analyze_div_wide.py celebi_trace_XXXX.csv
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Sample:
    index: int
    pc: int
    advance: int
    div: int
    host_tick: int
    div_ptr: int
    ctx_base: int
    ctx_valid: bool
    ctx: bytes
    near_base: int
    near_valid: bool
    near: bytes
    cyc_hook_word: int
    cyc_hook_ret: int


def _parse_hex_int(s: str) -> int:
    s = s.strip()
    if not s:
        return 0
    return int(s, 16)


def load_wide(path: Path) -> list[Sample]:
    lines = path.read_text(errors="replace").splitlines()
    header_idx = next((i for i, line in enumerate(lines) if line.startswith("wide_index,")), None)
    if header_idx is None:
        raise SystemExit("wide section not found: build/run Deep Probe v3.2 first")

    reader = csv.DictReader(lines[header_idx:])
    out: list[Sample] = []
    for row in reader:
        if not row.get("wide_index"):
            break
        try:
            ctx = bytes.fromhex(row.get("ctx_bytes", ""))
            near = bytes.fromhex(row.get("near_bytes", ""))
            out.append(
                Sample(
                    index=int(row["wide_index"]),
                    pc=_parse_hex_int(row["pc"]),
                    advance=int(row["advance"]),
                    div=_parse_hex_int(row["div"]),
                    host_tick=int(row.get("host_tick") or 0),
                    div_ptr=_parse_hex_int(row.get("div_ptr") or "0"),
                    ctx_base=_parse_hex_int(row.get("ctx_base") or "0"),
                    ctx_valid=(row.get("ctx_valid") == "1"),
                    ctx=ctx,
                    near_base=_parse_hex_int(row.get("near_base") or "0"),
                    near_valid=(row.get("near_valid") == "1"),
                    near=near,
                    cyc_hook_word=_parse_hex_int(row.get("cyc_hook_word") or "0"),
                    cyc_hook_ret=_parse_hex_int(row.get("cyc_hook_ret") or "0"),
                )
            )
        except (KeyError, ValueError) as exc:
            raise SystemExit(f"bad wide row {row!r}: {exc}") from exc
    return out


def expected_delta(a: Sample, b: Sample) -> int:
    # One Crystal frame advances the internal 16-bit divider by 70224 cycles.
    # 70224 mod 65536 = 0x1250.  Use advance distance so skipped samples still
    # compare correctly.
    d = (b.advance - a.advance) & 0xFFFFFFFF
    return (0x1250 * d) & 0xFFFF


def all_deltas_match(values: list[int], samples: list[Sample]) -> bool:
    return all(((values[i + 1] - values[i]) & 0xFFFF) == expected_delta(samples[i], samples[i + 1])
               for i in range(len(values) - 1))


def low_deltas_match(values: list[int], samples: list[Sample]) -> bool:
    return all(((values[i + 1] - values[i]) & 0xFF) == (expected_delta(samples[i], samples[i + 1]) & 0xFF)
               for i in range(len(values) - 1))


def search_window(name: str, samples: list[Sample], base: int, blobs: list[bytes]) -> None:
    if not blobs or any(not b for b in blobs):
        print(f"[{name}] no valid bytes")
        return
    n = min(map(len, blobs))
    exact: list[tuple[str, int, int, int]] = []
    relaxed: list[tuple[str, int, int, int]] = []

    for off in range(n - 1):
        # Little-endian: low byte at off, visible DIV/high byte at off+1.
        if all(blobs[i][off + 1] == samples[i].div for i in range(len(samples))):
            vals = [b[off] | (b[off + 1] << 8) for b in blobs]
            item = ("LE", off, base + off, base + off + 1)
            if all_deltas_match(vals, samples):
                exact.append(item)
            elif low_deltas_match([b[off] for b in blobs], samples):
                relaxed.append(item)

        # Big-endian storage possibility: visible DIV at off, low byte off+1.
        if all(blobs[i][off] == samples[i].div for i in range(len(samples))):
            vals = [(b[off] << 8) | b[off + 1] for b in blobs]
            item = ("BE", off, base + off + 1, base + off)
            if all_deltas_match(vals, samples):
                exact.append(item)
            elif low_deltas_match([b[off + 1] for b in blobs], samples):
                relaxed.append(item)

    print(f"\n[{name}] base=0x{base:08X} len={n}")
    if exact:
        print("exact 16-bit candidates (expected delta 0x1250 per advance):")
        for endian, off, low_addr, div_addr in exact:
            print(
                f"  {endian} off=0x{off:03X} counter_low=0x{low_addr:08X} "
                f"div/high=0x{div_addr:08X}"
            )
    else:
        print("exact 16-bit candidates: none")

    if relaxed:
        print("low-byte-only candidates (+0x50 per advance, relaxed):")
        for endian, off, low_addr, div_addr in relaxed[:32]:
            print(
                f"  {endian} off=0x{off:03X} low=0x{low_addr:08X} div=0x{div_addr:08X}"
            )
        if len(relaxed) > 32:
            print(f"  ... {len(relaxed) - 32} more")

    # Split-field fallback: a DIV mirror at one byte and a nearby byte whose
    # low-8 progression is correct, even if the emulator does not store a u16.
    div_offsets = [off for off in range(n) if all(blobs[i][off] == samples[i].div for i in range(len(samples)))]
    low_offsets = []
    for off in range(n):
        vals = [b[off] for b in blobs]
        if low_deltas_match(vals, samples):
            low_offsets.append(off)

    split = []
    for d in div_offsets:
        for lo in low_offsets:
            dist = abs(lo - d)
            if dist <= 16 and lo != d:
                split.append((dist, d, lo))
    split.sort()
    if split:
        print("nearby split-field candidates (distance <= 16 bytes):")
        for dist, d, lo in split[:24]:
            print(
                f"  dist={dist:2d} div=0x{base+d:08X} low=0x{base+lo:08X}"
            )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze_div_wide.py celebi_trace_XXXX.csv")
    path = Path(sys.argv[1])
    samples = load_wide(path)
    if len(samples) < 3:
        raise SystemExit(f"need at least 3 wide samples, got {len(samples)}")

    print(f"samples: {len(samples)}")
    for s in samples:
        print(
            f"  #{s.index} pc={s.pc:04X} adv={s.advance} div={s.div:02X} "
            f"div_ptr=0x{s.div_ptr:08X} tick={s.host_tick}"
        )

    w = samples[0].cyc_hook_word
    r = samples[0].cyc_hook_ret
    print(f"\ncycle hook: word=0x{w:08X} ret=0x{r:08X} top=0x{w>>24:02X}")
    if (w >> 24) != 0xEB:
        print("  diagnosis: 0x1A8360 is not an ARM BL at runtime; legacy cycle hook was not patched")
    elif r == 0:
        print("  diagnosis: BL-looking word but hook return is zero; investigate hook setup")
    else:
        print("  diagnosis: hook site patched/resolved; zero cycle count would mean the call path did not fire")

    ctx_samples = [s for s in samples if s.ctx_valid and s.ctx]
    if len(ctx_samples) == len(samples):
        search_window("context", samples, samples[0].ctx_base, [s.ctx for s in samples])
    else:
        print("\n[context] one or more snapshots invalid")

    near_samples = [s for s in samples if s.near_valid and s.near]
    same_near_base = len({s.near_base for s in samples if s.near_valid}) == 1
    if len(near_samples) == len(samples) and same_near_base:
        search_window("div-pointer-neighbourhood", samples, samples[0].near_base, [s.near for s in samples])
        ptr_off = samples[0].div_ptr - samples[0].near_base
        print(f"\nknown rDIV host pointer sits at near offset 0x{ptr_off:X}")
    else:
        print("\n[div-pointer-neighbourhood] invalid or base changed between samples")


if __name__ == "__main__":
    main()
