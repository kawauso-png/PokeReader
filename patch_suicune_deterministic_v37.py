#!/usr/bin/env python3
"""Patch PokeReader v3.6 into Suicune Deterministic Execute v3.7.

This intentionally touches only 3gx/sources/main.c.

Goal:
- Hold UP at a paused Suicune Target.
- Tap Y+X once.
- The plugin arms Deep Probe and schedules an exact 2-frame run.
- Y/X must be physically released before either game frame is allowed through.
- UP must remain held for both frames; releasing it early aborts safely while paused.
- After the exact 2 frames, the game stays paused until UP is released.
- Once UP is released, the plugin resumes automatically. No human R press is used.

This is the repeatability baseline before adding host-phase slots / Early Gate.
"""
from __future__ import annotations

from pathlib import Path
import sys

TARGET = Path("3gx/sources/main.c")
MARKER = "suicune_auto_resume_pending"


def replace_once(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {n}")
    return src.replace(old, new, 1)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else TARGET
    src = path.read_text(encoding="utf-8")

    if MARKER in src:
        print(f"Already patched: {path}")
        return 0

    src = replace_once(
        src,
        "static bool fixed_run_pending = false;\nstatic u32 fixed_run_id = 0;\n",
        "static bool fixed_run_pending = false;\nstatic u32 fixed_run_id = 0;\n\n"
        "// Suicune Deterministic Execute v3.7.  The user still supplies the real\n"
        "// UP input, but the exact 2-frame window and resume are controlled by the\n"
        "// plugin.  This removes the human R press from the timing path.\n"
        "static bool suicune_auto_resume_pending = false;\n"
        "static bool suicune_auto_input_ok = true;\n"
        "static u32 suicune_auto_run_id = 0;\n",
        "insert v3.7 state",
    )

    # Y+X is the v3.7 trigger.  Include X in the release gate so no modifier can
    # leak into either of the two exact game frames.  This is harmless for the
    # legacy Y+L path because X is normally not held there.
    src = replace_once(
        src,
        "if ((held & (KEY_Y | KEY_L | KEY_R)) == 0)",
        "if ((held & (KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)",
        "extend fixed-run release mask",
    )

    old_fixed = '''        // A fixed run is in progress: let exactly one frame through and stay\n        // paused. This reuses the existing single frame advance path.\n        if (fixed_frames_remaining > 0)\n        {\n            fixed_frames_remaining--;\n            break;\n        }\n\n        // Y + right / Y + left adjusts the frame count. The horizontal axis is\n'''
    new_fixed = '''        // A fixed run is in progress: let exactly one frame through and stay\n        // paused. This reuses the existing single frame advance path.\n        if (fixed_frames_remaining > 0)\n        {\n            // v3.7 safety gate: UP must be physically present for every exact\n            // Suicune frame. If it disappeared too early, do not allow another\n            // frame through. Stay paused so the trial cannot silently continue\n            // with a contaminated input window.\n            if (suicune_auto_resume_pending && !(held & KEY_DUP))\n            {\n                suicune_auto_input_ok = false;\n                suicune_auto_resume_pending = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                continue;\n            }\n\n            fixed_frames_remaining--;\n            break;\n        }\n\n        // The exact 2 frames have completed. The emulated game is still frozen,\n        // so the user can release UP at any comfortable human timing. Resume is\n        // automatic once all trigger/input keys are physically clear; R is not\n        // part of the timing path anymore. Poll quickly only in this short gate.\n        if (suicune_auto_resume_pending)\n        {\n            if ((held & (KEY_DUP | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)\n            {\n                suicune_auto_resume_pending = false;\n                suicune_auto_input_ok = true;\n                fixed_armed = false;\n                fixed_run_pending = false;\n                fixed_frames_remaining = 0;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }\n\n        // Y + right / Y + left adjusts the frame count. The horizontal axis is\n'''
    src = replace_once(src, old_fixed, new_fixed, "insert auto-resume gate")

    old_yx = '''            // Y + X arms Suicune Deep Probe at the exact frozen Target.\n            // No frame is allowed through, so X never reaches the VC as GB START.\n            if (just_pressed & KEY_X)\n            {\n                arm_suicune_probe();\n            }\n'''
    new_yx = '''            // Suicune Deterministic Execute v3.7:\n            //   Hold UP, then tap Y+X once at the frozen Target.\n            // We arm the probe and schedule the exact two-frame window in one\n            // action.  No game frame is released until Y/X are physically gone.\n            // Without UP held this keeps the old behavior and only arms Probe.\n            if (just_pressed & KEY_X)\n            {\n                arm_suicune_probe();\n                if (held & KEY_DUP)\n                {\n                    fixed_a_frames = 2;\n                    fixed_armed = true;\n                    fixed_run_pending = true;\n                    suicune_auto_resume_pending = true;\n                    suicune_auto_input_ok = true;\n                    suicune_auto_run_id++;\n                }\n            }\n'''
    src = replace_once(src, old_yx, new_yx, "replace Y+X with deterministic trigger")

    old_manual = '''        if (just_pressed & resume_keys)\n        {\n            is_paused = false;\n            fixed_frames_remaining = 0;\n            fixed_run_pending = false;\n            break;\n        }\n'''
    new_manual = '''        if (just_pressed & resume_keys)\n        {\n            is_paused = false;\n            fixed_frames_remaining = 0;\n            fixed_run_pending = false;\n            suicune_auto_resume_pending = false;\n            break;\n        }\n'''
    src = replace_once(src, old_manual, new_manual, "cancel auto state on manual resume")

    path.write_text(src, encoding="utf-8")
    print(f"Patched: {path}")
    print("Suicune v3.7 operation: pause -> hold UP -> tap Y+X -> release Y/X -> keep UP briefly -> release UP -> auto resume")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
