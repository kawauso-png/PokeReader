#!/bin/sh
set -eu

src="${1:-3gx/sources/main.c}"
tmp="${src}.v37.tmp"

awk '
BEGIN {
    c_state = c_mask = c_fixed = c_yx = c_resume = 0
    skip = 0
    in_resume = 0
}

skip > 0 {
    skip--
    next
}

{
    line = $0

    if (line == "static u32 fixed_run_id = 0;") {
        print line
        print ""
        print "// Suicune Deterministic Execute v3.7. The player still supplies real UP,"
        print "// but the plugin controls the exact two-frame window and the final resume."
        print "// This removes the human R press from the timing path."
        print "static bool suicune_auto_resume_pending = false;"
        c_state++
        next
    }

    if (line == "            if ((held & (KEY_Y | KEY_L | KEY_R)) == 0)") {
        print "            if ((held & (KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
        c_mask++
        next
    }

    if (line == "        if (fixed_frames_remaining > 0)") {
        print "        if (fixed_frames_remaining > 0)"
        print "        {"
        print "            // v3.7 safety: every exact Suicune frame must contain real UP."
        print "            // If UP is released too early, stop while still paused."
        print "            if (suicune_auto_resume_pending && !(held & KEY_DUP))"
        print "            {"
        print "                suicune_auto_resume_pending = false;"
        print "                fixed_frames_remaining = 0;"
        print "                fixed_run_pending = false;"
        print "                continue;"
        print "            }"
        print ""
        print "            fixed_frames_remaining--;"
        print "            break;"
        print "        }"
        print ""
        print "        // After the exact two frames the game is frozen again. The player"
        print "        // may release UP at ordinary human speed; once all timing-related"
        print "        // keys are clear, resume automatically without an R press."
        print "        if (suicune_auto_resume_pending)"
        print "        {"
        print "            if ((held & (KEY_DUP | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
        print "            {"
        print "                suicune_auto_resume_pending = false;"
        print "                fixed_armed = false;"
        print "                fixed_run_pending = false;"
        print "                fixed_frames_remaining = 0;"
        print "                is_paused = false;"
        print "                break;"
        print "            }"
        print "            svcSleepThread(1000000);"
        print "            continue;"
        print "        }"
        # Skip the original opening brace, decrement, break, closing brace.
        skip = 4
        c_fixed++
        next
    }

    if (line == "            if (just_pressed & KEY_X)") {
        print "            // v3.7 one-action path: hold UP and tap Y+X at Target."
        print "            // Without UP held, Y+X remains probe-arm only."
        print "            if (just_pressed & KEY_X)"
        print "            {"
        print "                arm_suicune_probe();"
        print "                if (held & KEY_DUP)"
        print "                {"
        print "                    fixed_a_frames = 2;"
        print "                    fixed_frames_remaining = 0;"
        print "                    fixed_armed = true;"
        print "                    fixed_run_pending = true;"
        print "                    suicune_auto_resume_pending = true;"
        print "                }"
        print "            }"
        # Skip original opening brace, arm call, closing brace.
        skip = 3
        c_yx++
        next
    }

    if (line == "        if (just_pressed & resume_keys)") {
        in_resume = 1
        print line
        next
    }

    if (in_resume && line == "            fixed_run_pending = false;") {
        print line
        print "            suicune_auto_resume_pending = false;"
        c_resume++
        next
    }

    if (in_resume && line == "        }") {
        in_resume = 0
        print line
        next
    }

    print line
}

END {
    if (c_state != 1 || c_mask != 1 || c_fixed != 1 || c_yx != 1 || c_resume != 1) {
        printf("v3.7 patch validation failed: state=%d mask=%d fixed=%d yx=%d resume=%d\n", c_state, c_mask, c_fixed, c_yx, c_resume) > "/dev/stderr"
        exit 42
    }
}
' "$src" > "$tmp"

mv "$tmp" "$src"

grep -q 'static bool suicune_auto_resume_pending = false;' "$src"
grep -q 'KEY_DUP | KEY_Y | KEY_X | KEY_L | KEY_R' "$src"
grep -q 'fixed_a_frames = 2;' "$src"

echo "Applied Suicune Deterministic Execute v3.7 to $src"
