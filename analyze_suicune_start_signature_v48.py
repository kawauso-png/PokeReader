#!/usr/bin/env python3
"""Analyze Suicune Start Signature v4.8 traces.

The key output is J27: the extra M-cycle phase jump at the first repeated-
advance group, relative to one normal 1172M frame.  The script also extracts
Target, rel40, Endpoint, host timing footer, and the frozen Target CPU context.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

MOD = 0x4000
FRAME_M = 1172


def phase(div_hex: str, sub_hex: str, high: bool) -> int:
    d = int(div_hex, 16)
    byte = (d >> 8) if high else (d & 0xFF)
    return ((byte << 6) | int(sub_hex, 16)) & 0x3FFF


def signed14(v: int) -> int:
    v &= 0x3FFF
    return v - 0x4000 if v >= 0x2000 else v


def section_rows(lines: list[str], header_prefix: str) -> list[dict[str, str]]:
    try:
        i = next(i for i, line in enumerate(lines) if line.startswith(header_prefix))
    except StopIteration:
        return []
    out: list[dict[str, str]] = []
    reader = csv.DictReader(lines[i:])
    first = header_prefix.split(",", 1)[0]
    for row in reader:
        if not row or row.get(first, "") == "":
            break
        out.append(row)
    return out


def one_row_section(lines: list[str], header_prefix: str) -> dict[str, str]:
    rows = section_rows(lines, header_prefix)
    return rows[0] if rows else {}


def analyze(path: Path) -> dict[str, object]:
    lines = path.read_text(errors="replace").splitlines()
    probe = one_row_section(lines, "probe,")
    startsig = one_row_section(lines, "start_signature,")
    endpoint = one_row_section(lines, "endpoint,")
    observe = one_row_section(lines, "observe_version,")
    frames = section_rows(lines, "frame,")

    if not probe or not frames:
        raise ValueError("missing probe/frame section")

    target = int(probe["target"])
    parsed = []
    for r in frames:
        try:
            adv = int(r["advance"])
            parsed.append(
                {
                    "adv": adv,
                    "off": (adv - target) & 0xFFFFFFFF,
                    "state": int(r["state"], 16),
                    "div": int(r["div"], 16),
                    "ap4": int(r["ap4"], 16),
                    "sp4": int(r["sp4"], 16),
                    "asub": int(r["asub"], 16),
                    "ssub": int(r["ssub"], 16),
                    "atick": int(r["atick"]),
                    "stick": int(r["stick"]),
                }
            )
        except (KeyError, ValueError):
            break

    stop_i = None
    for i in range(1, len(parsed)):
        if (
            parsed[i]["adv"] == parsed[i - 1]["adv"]
            and 20 <= parsed[i]["off"] <= 80
        ):
            stop_i = i - 1
            break
    if stop_i is None:
        raise ValueError("early repeated-advance group not found")

    stop_adv = parsed[stop_i]["adv"]
    group_start = stop_i
    while group_start > 0 and parsed[group_start - 1]["adv"] == stop_adv:
        group_start -= 1
    group_end = stop_i
    while group_end + 1 < len(parsed) and parsed[group_end + 1]["adv"] == stop_adv:
        group_end += 1
    if group_end + 1 >= len(parsed):
        raise ValueError("stop1 has no post row")

    stop = parsed[group_start]
    post = parsed[group_end + 1]
    pre = parsed[group_start - 1] if group_start > 0 else None

    da = (post["ap4"] - stop["ap4"]) & 0x3FFF
    ds = (post["sp4"] - stop["sp4"]) & 0x3FFF
    j27_a = signed14(da - FRAME_M)
    j27_s = signed14(ds - FRAME_M)

    rel40 = next((r for r in parsed if r["off"] == 40), None)

    ctx_hex = startsig.get("cpu_ctx_hex", "") if startsig else ""
    ctx = bytes.fromhex(ctx_hex) if len(ctx_hex) == 128 else b""
    ctx_words = [int.from_bytes(ctx[i : i + 2], "little") for i in range(0, len(ctx), 2)]

    result: dict[str, object] = {
        "file": path.name,
        "target": target,
        "target_state": probe.get("target_state", ""),
        "target_div": probe.get("target_div", ""),
        "target_ap4": probe.get("target_ap4", ""),
        "target_sp4": probe.get("target_sp4", ""),
        "target_asub": probe.get("target_asub", ""),
        "target_ssub": probe.get("target_ssub", ""),
        "target_pc": startsig.get("target_pc", "") if startsig else "",
        "stop1_offset": stop["off"],
        "stop1_repeat_rows": group_end - group_start + 1,
        "stop1_state": f"{stop['state']:04X}",
        "stop1_ap4": f"{stop['ap4']:04X}",
        "stop1_sp4": f"{stop['sp4']:04X}",
        "post1_state": f"{post['state']:04X}",
        "post1_ap4": f"{post['ap4']:04X}",
        "post1_sp4": f"{post['sp4']:04X}",
        "j27_a": j27_a,
        "j27_s": j27_s,
        "rel40_state": f"{rel40['state']:04X}" if rel40 else "",
        "rel40_ap4": f"{rel40['ap4']:04X}" if rel40 else "",
        "rel40_sp4": f"{rel40['sp4']:04X}" if rel40 else "",
        "endpoint_state": endpoint.get("state", "") if endpoint else "",
        "endpoint_ap4": endpoint.get("ap4", "") if endpoint else "",
        "endpoint_sp4": endpoint.get("sp4", "") if endpoint else "",
        "raw_dv": probe.get("raw_dv", ""),
        "route": probe.get("route", ""),
        "fixed_to_hook_tick": observe.get("fixed_to_hook_tick", "") if observe else "",
        "resume_to_hook_tick": observe.get("resume_to_hook_tick", "") if observe else "",
        "arm_tick": observe.get("fixed_arm_tick", "") if observe else "",
        "cpu_ctx_hex": ctx_hex,
    }
    if pre:
        result.update(
            {
                "pre1_state": f"{pre['state']:04X}",
                "pre1_ap4": f"{pre['ap4']:04X}",
                "pre1_sp4": f"{pre['sp4']:04X}",
            }
        )
    # Expose 32 little-endian 16-bit views so simple spreadsheets can test
    # context offsets without decoding the hex blob themselves.
    for i, word in enumerate(ctx_words):
        result[f"ctx16_{i*2:02X}"] = f"{word:04X}"
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    rows = [analyze(p) for p in args.files]
    keys: list[str] = []
    for row in rows:
        for k in row:
            if k not in keys:
                keys.append(k)
    writer = csv.DictWriter(__import__("sys").stdout, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)


if __name__ == "__main__":
    main()
