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
        print "// Suicune Observe v3.8 phase-gated Exact3F experiment."
        print "// The VC remains frozen while we debounce UP and then wait for a"
        print "// controlled host-tick phase relative to the frozen Target rDIV hook."
        print "static u32 suicune_up_gate_stable = 0;"
        print "#define SUICUNE_PHASE_PERIOD_TICKS 4481151ULL"
        print "#define SUICUNE_PHASE_TARGET_TICKS 3350000ULL"
        print "#define SUICUNE_PHASE_WINDOW_TICKS 5000ULL"
        print "static u64 suicune_phase_target_atick = 0;"
        print "static u64 suicune_phase_gate_tick = 0;"
        print "static bool suicune_phase_arm_pending = false;"
        print ""
        print "static void suicune_wait_phase_gate(void)"
        print "{"
        print "    if (suicune_phase_target_atick == 0)"
        print "    {"
        print "        suicune_phase_gate_tick = svcGetSystemTick();"
        print "        return;"
        print "    }"
        print ""
        print "    // One-shot busy wait: at most one 16.7 ms VC-frame period while"
        print "    // the game is already paused. This avoids scheduler jitter from"
        print "    // SleepThread at the final phase boundary."
        print "    for (;;)"
        print "    {"
        print "        u64 now = svcGetSystemTick();"
        print "        u64 phase = (now - suicune_phase_target_atick) % SUICUNE_PHASE_PERIOD_TICKS;"
        print "        if (phase >= SUICUNE_PHASE_TARGET_TICKS &&"
        print "            phase < SUICUNE_PHASE_TARGET_TICKS + SUICUNE_PHASE_WINDOW_TICKS)"
        print "        {"
        print "            suicune_phase_gate_tick = now;"
        print "            return;"
        print "        }"
        print "    }"
        print "}"
        inserted_state++
        next
    }

    if (line == "        if (fixed_run_pending)") {
        print "        if (fixed_run_pending)"
        print "        {"
        print "            // Y+X schedules the experiment; no game frame passes until"
        print "            // Y/X are clear, UP is stable, and the phase gate is hit."
        print "            if (suicune_auto_resume_pending && (just_pressed & KEY_B))"
        print "            {"
        print "                suicune_auto_resume_pending = false;"
        print "                fixed_run_pending = false;"
        print "                fixed_frames_remaining = 0;"
        print "                fixed_armed = false;"
        print "                suicune_up_gate_stable = 0;"
        print "                suicune_phase_arm_pending = false;"
        print "                suicune_phase_target_atick = 0;"
        print "                suicune_phase_gate_tick = 0;"
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
        print ""
        print "                        if (suicune_phase_arm_pending)"
        print "                        {"
        print "                            suicune_wait_phase_gate();"
        print "                            suicune_observe_reset();"
        print "                            // In PG1 fixed_arm_tick is the actual gate hit,"
        print "                            // immediately before the deferred probe arm."
        print "                            suicune_obs_arm_tick = suicune_phase_gate_tick;"
        print "                            arm_suicune_probe();"
        print "                            suicune_phase_arm_pending = false;"
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
        print "            // Phase-gated one-trigger path. The probe arm itself is"
        print "            // deferred until UP is stable and the controlled host phase"
        print "            // is reached. The frozen game state/Target cannot advance."
        print "            if (just_pressed & KEY_X)"
        print "            {"
        print "                suicune_phase_target_atick = suicune_target_atick();"
        print "                suicune_phase_gate_tick = 0;"
        print "                suicune_phase_arm_pending = true;"
        print "                fixed_a_frames = 3;"
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
        printf("phase-gate patch validation failed: state=%d pending=%d yx=%d\n", inserted_state, replaced_pending, replaced_yx) > "/dev/stderr"
        exit 45
    }
}
' "$src" > "$tmp"

mv "$tmp" "$src"

# Mark this timing experiment distinctly so PG1 traces are never silently
# mixed with ordinary V38 Exact3F traces by offline analysis.
sed -i 's/"V38,%llu/"V38PG1,%llu/' "$src"

grep -q 'static u32 suicune_up_gate_stable = 0;' "$src"
grep -q 'SUICUNE_PHASE_PERIOD_TICKS 4481151ULL' "$src"
grep -q 'SUICUNE_PHASE_TARGET_TICKS 3350000ULL' "$src"
grep -q 'suicune_phase_target_atick = suicune_target_atick();' "$src"
grep -q 'suicune_wait_phase_gate();' "$src"
grep -q 'fixed_a_frames = 3;' "$src"
grep -q 'V38PG1' "$src"

echo "Applied Suicune Observe v3.8 PG1 phase gate (Exact 3F) to $src"
