#!/bin/sh
set -eu

src="${1:-3gx/sources/main.c}"
tmp="${src}.upgate.tmp"

awk '
BEGIN {
    inserted_state = 0
    replaced_pending = 0
    replaced_yx = 0
    skip_block = 0
    block_depth = 0
    saw_open = 0
}

function brace_delta(s,    t, o, c) {
    t = s
    o = gsub(/\{/, "{", t)
    t = s
    c = gsub(/\}/, "}", t)
    return o - c
}

skip_block {
    d = brace_delta($0)
    if (index($0, "{") > 0) saw_open = 1
    block_depth += d
    if (saw_open && block_depth == 0) {
        skip_block = 0
        saw_open = 0
    }
    next
}

{
    line = $0

    if (line == "static bool suicune_auto_resume_pending = false;") {
        print line
        print "// Suicune Observe v3.8 UP gate: require a stable physical UP before"
        print "// releasing the exact two game frames. Three pause-loop samples at"
        print "// 10 ms spacing debounce transient D-pad misses without advancing VC."
        print "static u32 suicune_up_gate_stable = 0;"
        inserted_state++
        next
    }

    if (line == "        if (fixed_run_pending)") {
        print "        if (fixed_run_pending)"
        print "        {"
        print "            // UP-gated one-trigger path. Y+X only arms while paused."
        print "            // After Y/X are released, wait indefinitely for a stable UP;"
        print "            // no game frame is allowed through during this wait."
        print "            if (suicune_auto_resume_pending && (just_pressed & KEY_B))"
        print "            {"
        print "                suicune_auto_resume_pending = false;"
        print "                fixed_run_pending = false;"
        print "                fixed_frames_remaining = 0;"
        print "                fixed_armed = false;"
        print "                suicune_up_gate_stable = 0;"
        print "                continue;"
        print "            }"
        print ""
        print "            if ((held & (KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)"
        print "            {"
        print "                if (!suicune_auto_resume_pending || (held & KEY_DUP))"
        print "                {"
        print "                    if (suicune_auto_resume_pending)"
        print "                    {"
        print "                        if (suicune_up_gate_stable < 3) suicune_up_gate_stable++;"
        print "                        if (suicune_up_gate_stable < 3)"
        print "                        {"
        print "                            svcSleepThread(10000000);"
        print "                            continue;"
        print "                        }"
        print "                    }"
        print ""
        print "                    suicune_obs_fixed_release_tick = svcGetSystemTick();"
        print "                    fixed_run_pending = false;"
        print "                    suicune_obs_fixed_start_tick = svcGetSystemTick();"
        print "                    suicune_obs_wait_fixed_hook = true;"
        print "                    fixed_frames_remaining = fixed_a_frames;"
        print "                    fixed_last_run = fixed_a_frames;"
        print "                    fixed_run_id++;"
        print "                    suicune_up_gate_stable = 0;"
        print "                    continue;"
        print "                }"
        print "                suicune_up_gate_stable = 0;"
        print "            }"
        print "            else"
        print "            {"
        print "                suicune_up_gate_stable = 0;"
        print "            }"
        print ""
        print "            svcSleepThread(10000000);"
        print "            continue;"
        print "        }"
        skip_block = 1
        block_depth = 0
        saw_open = 0
        replaced_pending++
        next
    }

    if (line == "            if (just_pressed & KEY_X)") {
        print "            // UP-gated v3.8 one-trigger path. Tap Y+X at Target; UP may"
        print "            // already be held or may be pressed after Y/X are released."
        print "            // Exact 2F starts only after UP is stable for three samples."
        print "            if (just_pressed & KEY_X)"
        print "            {"
        print "                arm_suicune_probe();"
        print "                suicune_observe_reset();"
        print "                suicune_obs_arm_tick = svcGetSystemTick();"
        print "                fixed_a_frames = 2;"
        print "                fixed_frames_remaining = 0;"
        print "                fixed_armed = true;"
        print "                fixed_run_pending = true;"
        print "                suicune_auto_resume_pending = true;"
        print "                suicune_up_gate_stable = 0;"
        print "                continue;"
        print "            }"
        skip_block = 1
        block_depth = 0
        saw_open = 0
        replaced_yx++
        next
    }

    print line
}

END {
    if (inserted_state != 1 || replaced_pending != 1 || replaced_yx != 1) {
        printf("UP gate patch validation failed: state=%d pending=%d yx=%d\n", inserted_state, replaced_pending, replaced_yx) > "/dev/stderr"
        exit 45
    }
}
' "$src" > "$tmp"

mv "$tmp" "$src"

grep -q 'static u32 suicune_up_gate_stable = 0;' "$src"
grep -q 'if (suicune_up_gate_stable < 3) suicune_up_gate_stable++;' "$src"
grep -q 'UP-gated v3.8 one-trigger path' "$src"
grep -q 'suicune_auto_resume_pending && (just_pressed & KEY_B)' "$src"

echo "Applied Suicune Observe v3.8 UP gate to $src"
