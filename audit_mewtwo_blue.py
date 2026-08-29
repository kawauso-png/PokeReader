#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
main = (ROOT / "3gx/sources/main.c").read_text()
gen1 = (ROOT / "reader_core/src/gen1/mod.rs").read_text()
title = (ROOT / "reader_core/src/title.rs").read_text()
pnp_c = (ROOT / "3gx/sources/pnp.c").read_text()
plg = (ROOT / "3gx/PokeReader.plgInfo").read_text()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"AUDIT FAIL: {msg}")


# Title/loader invariants.
require("BlueJp = 0x0004000000170E00" in title, "BlueJp title id missing")
require("(LoadedTitle::BlueJp, 0)" in title, "hardware Blue update version 0 not accepted")
require("(LoadedTitle::BlueJp, 1056)" in title, "Blue remaster version 1056 not accepted")
require("0x00170E00" in plg, "Blue 3GX target missing")

# Exact host-side 2F controller invariants.
require("#define BLUE_FIXED_FRAMES 2" in main, "exact fixed frame count is not 2")
require("blue_fixed_frames_remaining--" in main, "fixed run does not consume one frame at a time")
require("blue_wait_a_release = true" in main, "no post-2F A-release gate")
require("if ((held & KEY_A) == 0)" in main, "A hold is not enforced")
require("blue_capture_target(blue_fixed_run_id)" in main, "frozen target snapshot is not captured")
require("if ((just_pressed & KEY_R) && !(held & KEY_A))" in main, "Blue resume is not R-only/A-released")
require("arm_suicune_probe" not in main, "Crystal/Suicune probe leaked into Blue host path")

fixed_trigger = main.index("if ((just_pressed & KEY_L) && (held & KEY_Y)")
plain_l = main.index("if ((just_pressed & KEY_L) && !(held & KEY_Y))")
require(fixed_trigger < plain_l, "Y+L fixed trigger must precede ordinary L frame advance")

capture = main.index("blue_capture_target(blue_fixed_run_id)")
start_frames = main.index("blue_fixed_frames_remaining = BLUE_FIXED_FRAMES")
require(capture < start_frames, "target snapshot must happen before the first permitted A frame")

# Blue memory/RNG invariants validated on hardware.
for token in [
    "0x0022_F6C8", "0x0022_F6D8", "0x0022_F794", "0x0022_F5FC",
    "0xFFD3", "0xFFD4", "0xFFD5", "0xD034", "0xD036",
    "0xCFCC", "0xCFD8", "0xCFD9", "0xCFDA",
]:
    require(token in gen1, f"validated Blue address missing: {token}")

# Trial pairing must use run-id capture, not a loose physical-A time window.
require("pub extern \"C\" fn blue_capture_target(run_id: u32)" in gen1, "run-id target capture export missing")
require("pnp::is_just_pressed" not in gen1, "physical A edge heuristic returned to Blue trial pairing")
require("last_valid_2f_a" not in gen1, "stale-A heuristic returned")
require("DV_MIN_BATTLE_AGE" in gen1 and "DV_STABLE_COUNT" in gen1, "DV settling guard missing")
require("state.stability.observe" in gen1, "DV stability state machine not used")

# Pointer validation must reject FREE/unreadable regions, not only svcQueryMemory errors.
require("info.state == MEMSTATE_FREE" in pnp_c, "FREE memory is not rejected")
require("info.perm & MEMPERM_READ" in pnp_c, "read permission is not checked")

print("Blue Mewtwo audit: PASS")
