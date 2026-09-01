#!/usr/bin/env python3
from pathlib import Path

main_path = Path("3gx/sources/main.c")
trace_path = Path("reader_core/src/crystal/trace.rs")

mainc = main_path.read_text()
trace = trace_path.read_text()

# v6.5.8 Fast Validate
# --------------------
# Keep physical UP (HID is read-only), but remove the awkward UP+Y+X chord.
# While paused, UP+B is consumed entirely by PokeReader.  The existing
# fixed_run_pending gate then waits until B is physically released before any
# game frame is allowed through, so the Exact-2F window contains UP only.
#
# The same path works both at a practical READY target and without a practical
# target.  The latter is the fast validation mode: arm a normal Deep Probe at
# the current frozen root and collect a complete PRE->POST->DV donor without
# spending time on shiny search.

marker = "// v6.5.8 FastValidate: hold UP and tap B; no Y/X chord."
if marker not in mainc:
    x_marker = "// v3.7 one-action path: hold UP and tap Y+X at Target."
    xm = mainc.find(x_marker)
    if xm < 0:
        raise SystemExit("v6.5.8 Y+X marker not found")

    x_if = mainc.find("if (just_pressed & KEY_X)", xm)
    if x_if < 0:
        raise SystemExit("v6.5.8 generated X trigger not found")
    open_brace = mainc.find("{", x_if)
    if open_brace < 0:
        raise SystemExit("v6.5.8 X trigger opening brace not found")

    depth = 0
    close_brace = -1
    for i in range(open_brace, len(mainc)):
        ch = mainc[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                close_brace = i
                break
    if close_brace < 0:
        raise SystemExit("v6.5.8 X trigger closing brace not found")

    # Reuse the entire generated body so all v4.9/v5.x/v6.1 telemetry and
    # phase-lock initialization stays identical to the proven Y+X path.
    body = mainc[open_brace + 1:close_brace]

    # Insert before the Y-modifier command block, at pause-loop scope.
    insert_anchor = "        // Y + right / Y + left adjusts the frame count."
    ins = mainc.find(insert_anchor, close_brace)
    if ins < 0:
        raise SystemExit("v6.5.8 pause-loop insertion anchor not found")

    b_block = (
        "        " + marker + "\n"
        "        // B never reaches a VC frame: fixed_run_pending waits for its release.\n"
        "        // Requiring !Y preserves the legacy Y+B neutral-delay command.\n"
        "        if ((just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y))\n"
        "        {" + body + "\n"
        "            continue;\n"
        "        }\n\n"
    )
    mainc = mainc[:ins] + b_block + mainc[ins:]

# The pending gate must wait for B release too.  Otherwise a short B press can
# leak into the first exact game frame on a fast polling boundary.
old_pending = "if ((held & (KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
new_pending = "if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
if new_pending not in mainc:
    if mainc.count(old_pending) != 1:
        raise SystemExit(f"v6.5.8 fixed pending release mask count: {mainc.count(old_pending)}")
    mainc = mainc.replace(old_pending, new_pending, 1)

# Also keep B in the post-2F release mask.  This is mostly defensive because
# B must already be released before the fixed run starts.
old_resume = "if ((held & (KEY_DUP | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
new_resume = "if ((held & (KEY_DUP | KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
if new_resume not in mainc:
    if mainc.count(old_resume) != 1:
        raise SystemExit(f"v6.5.8 auto-resume release mask count: {mainc.count(old_resume)}")
    mainc = mainc.replace(old_resume, new_resume, 1)

# Give direct, non-practical donor collection an unambiguous status.  A READY
# run becomes PATH as before because arm_suicune_probe binds the practical
# candidate; only the search-bypassing validation path displays S658 TEST.
test_line = '            pnp::println!("S658 TEST");'
if test_line not in trace:
    anchor = "        } else if self.practical_miss == 1 && self.probe_active {"
    if trace.count(anchor) != 1:
        raise SystemExit(f"v6.5.8 TEST UI anchor count: {trace.count(anchor)}")
    repl = (
        "        } else if self.probe_session && self.probe_active && !self.practical_active {\n"
        + test_line + "\n"
        + anchor
    )
    trace = trace.replace(anchor, repl, 1)

# Static safety checks against accidental timing-path regression.
if mainc.count(marker) != 1:
    raise SystemExit(f"v6.5.8 B trigger marker count: {mainc.count(marker)}")
if mainc.count("(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)") != 1:
    raise SystemExit("v6.5.8 UP+B trigger condition missing/duplicated")
if mainc.count("arm_suicune_probe();") < 2:
    raise SystemExit("v6.5.8 B path did not clone probe arm")
if new_pending not in mainc:
    raise SystemExit("v6.5.8 B release is not gated before Exact-2F")
if new_resume not in mainc:
    raise SystemExit("v6.5.8 B missing from post-2F release mask")
if "suicune_auto_resume_pending && !(held & KEY_DUP)" not in mainc:
    raise SystemExit("v6.5.8 physical-UP safety guard missing")
if "S658 TEST" not in trace:
    raise SystemExit("v6.5.8 TEST status missing")

main_path.write_text(mainc)
trace_path.write_text(trace)
print("Applied Suicune v6.5.8 Fast Validate: UP+B Exact-2F + direct donor TEST mode")
