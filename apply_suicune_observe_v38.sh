#!/bin/sh
set -eu

src="${1:-3gx/sources/main.c}"
tmp="${src}.v38.tmp"

awk '
BEGIN {
    c_include = c_proto = c_state = c_pause = c_pending = c_yx = c_auto = c_resume = c_hook = 0
    in_pause_fn = 0
    pending_block = 0
    yx_up_block = 0
    auto_block = 0
    auto_clear_block = 0
}
{
    line = $0

    if (line == "#include <stdio.h>") {
        print line
        print "#include <stdlib.h>"
        c_include++
        next
    }

    if (line == "static u32 trace_save_req = 0;") {
        print line
        print ""
        print "// Suicune Observe v3.8: clean C-side timing is captured outside the"
        print "// Deep Probe trace path so probe overhead cannot pollute host-phase data."
        print "static void append_suicune_observe_csv(void);"
        c_proto++
        next
    }

    if (line == "static u32 trace_written_slot = 0;") {
        print "static u32 trace_written_slot = 0xffffffff;"
        print ""
        print "// ---- Suicune Observe v3.8 ----------------------------------------------"
        print "#define SUICUNE_TICK_BENCH_N 4096"
        print "#define SUICUNE_PERIOD_N 128"
        print ""
        print "static u64 suicune_obs_arm_tick = 0;"
        print "static u64 suicune_obs_fixed_release_tick = 0;"
        print "static u64 suicune_obs_fixed_start_tick = 0;"
        print "static u64 suicune_obs_fixed_first_hook_tick = 0;"
        print "static u64 suicune_obs_fixed_end_tick = 0;"
        print "static u64 suicune_obs_up_release_tick = 0;"
        print "static u64 suicune_obs_resume_tick = 0;"
        print "static u64 suicune_obs_post_resume_hook_tick = 0;"
        print "static bool suicune_obs_wait_fixed_hook = false;"
        print "static bool suicune_obs_wait_resume_hook = false;"
        print "static bool suicune_obs_period_collecting = false;"
        print "static bool suicune_obs_csv_appended = false;"
        print "static u64 suicune_obs_period_prev_tick = 0;"
        print "static u32 suicune_obs_period_count = 0;"
        print "static u32 suicune_obs_period_delta[SUICUNE_PERIOD_N];"
        print ""
        print "static bool suicune_bench_ready = false;"
        print "static u32 suicune_bench_min_nonzero = 0;"
        print "static u32 suicune_bench_median = 0;"
        print "static u32 suicune_bench_p99 = 0;"
        print "static u32 suicune_bench_max = 0;"
        print "static u32 suicune_bench_zero = 0;"
        print "static u32 suicune_bench_le255 = 0;"
        print "static u32 suicune_bench_gcd = 0;"
        print "static u32 suicune_bench_delta[SUICUNE_TICK_BENCH_N];"
        print ""
        print "static int cmp_u32(const void *a, const void *b)"
        print "{"
        print "    u32 aa = *(const u32 *)a;"
        print "    u32 bb = *(const u32 *)b;"
        print "    return (aa > bb) - (aa < bb);"
        print "}"
        print ""
        print "static u32 gcd_u32(u32 a, u32 b)"
        print "{"
        print "    while (b != 0)"
        print "    {"
        print "        u32 t = a % b;"
        print "        a = b;"
        print "        b = t;"
        print "    }"
        print "    return a;"
        print "}"
        print ""
        print "static void suicune_tick_bench_once(void)"
        print "{"
        print "    if (suicune_bench_ready) return;"
        print ""
        print "    u64 prev = svcGetSystemTick();"
        print "    u32 min_nz = 0xffffffff;"
        print "    u32 zero = 0;"
        print "    u32 le255 = 0;"
        print "    u32 g = 0;"
        print "    for (u32 i = 0; i < SUICUNE_TICK_BENCH_N; i++)"
        print "    {"
        print "        u64 now = svcGetSystemTick();"
        print "        u64 d64 = now - prev;"
        print "        u32 d = d64 > 0xffffffffULL ? 0xffffffff : (u32)d64;"
        print "        suicune_bench_delta[i] = d;"
        print "        if (d == 0) zero++;"
        print "        else"
        print "        {"
        print "            if (d < min_nz) min_nz = d;"
        print "            g = g == 0 ? d : gcd_u32(g, d);"
        print "        }"
        print "        if (d <= 255) le255++;"
        print "        prev = now;"
        print "    }"
        print ""
        print "    qsort(suicune_bench_delta, SUICUNE_TICK_BENCH_N, sizeof(u32), cmp_u32);"
        print "    u32 p99_index = ((SUICUNE_TICK_BENCH_N * 99 + 99) / 100) - 1;"
        print "    suicune_bench_min_nonzero = min_nz == 0xffffffff ? 0 : min_nz;"
        print "    suicune_bench_median = suicune_bench_delta[SUICUNE_TICK_BENCH_N / 2];"
        print "    suicune_bench_p99 = suicune_bench_delta[p99_index];"
        print "    suicune_bench_max = suicune_bench_delta[SUICUNE_TICK_BENCH_N - 1];"
        print "    suicune_bench_zero = zero;"
        print "    suicune_bench_le255 = le255;"
        print "    suicune_bench_gcd = g;"
        print "    suicune_bench_ready = true;"
        print "}"
        print ""
        print "static void suicune_observe_reset(void)"
        print "{"
        print "    suicune_obs_arm_tick = 0;"
        print "    suicune_obs_fixed_release_tick = 0;"
        print "    suicune_obs_fixed_start_tick = 0;"
        print "    suicune_obs_fixed_first_hook_tick = 0;"
        print "    suicune_obs_fixed_end_tick = 0;"
        print "    suicune_obs_up_release_tick = 0;"
        print "    suicune_obs_resume_tick = 0;"
        print "    suicune_obs_post_resume_hook_tick = 0;"
        print "    suicune_obs_wait_fixed_hook = false;"
        print "    suicune_obs_wait_resume_hook = false;"
        print "    suicune_obs_period_collecting = false;"
        print "    suicune_obs_period_prev_tick = 0;"
        print "    suicune_obs_period_count = 0;"
        print "    suicune_obs_csv_appended = false;"
        print "    trace_written_slot = 0xffffffff;"
        print "}"
        print ""
        print "static void suicune_observe_top_hook(u64 tick)"
        print "{"
        print "    if (suicune_obs_wait_fixed_hook && suicune_obs_fixed_first_hook_tick == 0)"
        print "    {"
        print "        suicune_obs_fixed_first_hook_tick = tick;"
        print "        suicune_obs_wait_fixed_hook = false;"
        print "    }"
        print ""
        print "    if (suicune_obs_wait_resume_hook && suicune_obs_post_resume_hook_tick == 0)"
        print "    {"
        print "        suicune_obs_post_resume_hook_tick = tick;"
        print "        suicune_obs_wait_resume_hook = false;"
        print "        suicune_obs_period_collecting = true;"
        print "        suicune_obs_period_prev_tick = tick;"
        print "        return;"
        print "    }"
        print ""
        print "    if (suicune_obs_period_collecting && suicune_obs_period_count < SUICUNE_PERIOD_N)"
        print "    {"
        print "        u64 d64 = tick - suicune_obs_period_prev_tick;"
        print "        suicune_obs_period_delta[suicune_obs_period_count++] ="
        print "            d64 > 0xffffffffULL ? 0xffffffff : (u32)d64;"
        print "        suicune_obs_period_prev_tick = tick;"
        print "        if (suicune_obs_period_count >= SUICUNE_PERIOD_N)"
        print "            suicune_obs_period_collecting = false;"
        print "    }"
        print "}"
        print ""
        print "static void append_suicune_observe_csv(void)"
        print "{"
        print "    if (suicune_obs_csv_appended || suicune_obs_arm_tick == 0 || trace_written_slot == 0xffffffff) return;"
        print "    suicune_obs_csv_appended = true;"
        print ""
        print "    u32 period_min = 0, period_median = 0, period_p99 = 0, period_max = 0;"
        print "    if (suicune_obs_period_count > 0)"
        print "    {"
        print "        qsort(suicune_obs_period_delta, suicune_obs_period_count, sizeof(u32), cmp_u32);"
        print "        u32 p99_index = ((suicune_obs_period_count * 99 + 99) / 100) - 1;"
        print "        period_min = suicune_obs_period_delta[0];"
        print "        period_median = suicune_obs_period_delta[suicune_obs_period_count / 2];"
        print "        period_p99 = suicune_obs_period_delta[p99_index];"
        print "        period_max = suicune_obs_period_delta[suicune_obs_period_count - 1];"
        print "    }"
        print ""
        print "    u64 fixed_to_hook = (suicune_obs_fixed_first_hook_tick >= suicune_obs_fixed_start_tick)"
        print "        ? suicune_obs_fixed_first_hook_tick - suicune_obs_fixed_start_tick : 0;"
        print "    u64 resume_to_hook = (suicune_obs_post_resume_hook_tick >= suicune_obs_resume_tick)"
        print "        ? suicune_obs_post_resume_hook_tick - suicune_obs_resume_tick : 0;"
        print ""
        print "    FS_Archive sdmc;"
        print "    Handle f = 0;"
        print "    char path[128];"
        print "    char linebuf[1536];"
        print "    u64 size = 0;"
        print "    u32 written = 0;"
        print ""
        print "    if (R_FAILED(fsInit())) return;"
        print "    if (R_FAILED(FSUSER_OpenArchive(&sdmc, ARCHIVE_SDMC, fsMakePath(PATH_EMPTY, \"\"))))"
        print "    {"
        print "        fsExit();"
        print "        return;"
        print "    }"
        print "    sprintf(path, \"/luma/plugins/pokereader/traces/celebi_trace_%04lu.csv\", (unsigned long)trace_written_slot);"
        print "    Result res = FSUSER_OpenFile(&f, sdmc, fsMakePath(PATH_ASCII, path), FS_OPEN_WRITE, 0);"
        print "    if (R_SUCCEEDED(res) && R_SUCCEEDED(FSFILE_GetSize(f, &size)))"
        print "    {"
        print "        int len = sprintf(linebuf,"
        print "            \"\\nobserve_version,fixed_arm_tick,fixed_release_detect_tick,fixed_start_tick,fixed_first_hook_tick,fixed_end_tick,up_release_detect_tick,resume_command_tick,post_resume_hook_tick,fixed_to_hook_tick,resume_to_hook_tick,host_period_samples,host_period_min,host_period_median,host_period_p99,host_period_max,bench_samples,bench_min_nonzero,bench_median,bench_p99,bench_max,bench_zero,bench_le255,bench_gcd\\n\""
        print "            \"V38,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%lu,%lu,%lu,%lu,%lu,%u,%lu,%lu,%lu,%lu,%lu,%lu,%lu\\n\","
        print "            (unsigned long long)suicune_obs_arm_tick,"
        print "            (unsigned long long)suicune_obs_fixed_release_tick,"
        print "            (unsigned long long)suicune_obs_fixed_start_tick,"
        print "            (unsigned long long)suicune_obs_fixed_first_hook_tick,"
        print "            (unsigned long long)suicune_obs_fixed_end_tick,"
        print "            (unsigned long long)suicune_obs_up_release_tick,"
        print "            (unsigned long long)suicune_obs_resume_tick,"
        print "            (unsigned long long)suicune_obs_post_resume_hook_tick,"
        print "            (unsigned long long)fixed_to_hook,"
        print "            (unsigned long long)resume_to_hook,"
        print "            (unsigned long)suicune_obs_period_count,"
        print "            (unsigned long)period_min,"
        print "            (unsigned long)period_median,"
        print "            (unsigned long)period_p99,"
        print "            (unsigned long)period_max,"
        print "            SUICUNE_TICK_BENCH_N,"
        print "            (unsigned long)suicune_bench_min_nonzero,"
        print "            (unsigned long)suicune_bench_median,"
        print "            (unsigned long)suicune_bench_p99,"
        print "            (unsigned long)suicune_bench_max,"
        print "            (unsigned long)suicune_bench_zero,"
        print "            (unsigned long)suicune_bench_le255,"
        print "            (unsigned long)suicune_bench_gcd);"
        print "        if (len > 0)"
        print "        {"
        print "            FSFILE_Write(f, &written, size, linebuf, (u32)len, 0);"
        print "            FSFILE_Flush(f);"
        print "        }"
        print "    }"
        print "    if (f != 0) FSFILE_Close(f);"
        print "    FSUSER_CloseArchive(sdmc);"
        print "    fsExit();"
        print "}"
        c_state++
        next
    }

    if (line == "void host_request_pause(void)") {
        print line
        in_pause_fn = 1
        next
    }
    if (in_pause_fn && line == "{") {
        print line
        print "    append_suicune_observe_csv();"
        in_pause_fn = 0
        c_pause++
        next
    }

    if (line == "            if ((held & (KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)") {
        print line
        pending_block = 1
        next
    }
    if (pending_block && line == "            {") {
        print line
        print "                suicune_obs_fixed_release_tick = svcGetSystemTick();"
        pending_block = 2
        next
    }
    if (pending_block == 2 && line == "                fixed_frames_remaining = fixed_a_frames;") {
        print "                suicune_obs_fixed_start_tick = svcGetSystemTick();"
        print "                suicune_obs_wait_fixed_hook = true;"
        print line
        pending_block = 0
        c_pending++
        next
    }

    if (line == "                if (held & KEY_DUP)") {
        print line
        yx_up_block = 1
        next
    }
    if (yx_up_block && line == "                {") {
        print line
        print "                    suicune_observe_reset();"
        print "                    suicune_obs_arm_tick = svcGetSystemTick();"
        print "                    suicune_tick_bench_once();"
        yx_up_block = 0
        c_yx++
        next
    }

    if (line == "        if (suicune_auto_resume_pending)") {
        print line
        auto_block = 1
        next
    }
    if (auto_block && line == "        {") {
        print line
        print "            if (suicune_obs_fixed_end_tick == 0) suicune_obs_fixed_end_tick = svcGetSystemTick();"
        auto_block = 0
        c_auto++
        next
    }

    if (line == "            if ((held & (KEY_DUP | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)") {
        print line
        auto_clear_block = 1
        next
    }
    if (auto_clear_block && line == "            {") {
        print line
        print "                suicune_obs_up_release_tick = svcGetSystemTick();"
        auto_clear_block = 2
        next
    }
    if (auto_clear_block == 2 && line == "                is_paused = false;") {
        print "                suicune_obs_resume_tick = svcGetSystemTick();"
        print "                suicune_obs_wait_resume_hook = true;"
        print line
        auto_clear_block = 0
        c_resume++
        next
    }

    if (line == "    bool isTopScreen = screenId == 0;") {
        print line
        print "    if (isTopScreen && suicune_obs_arm_tick != 0)"
        print "    {"
        print "        suicune_observe_top_hook(svcGetSystemTick());"
        print "    }"
        c_hook++
        next
    }

    print line
}
END {
    if (c_include != 1 || c_proto != 1 || c_state != 1 || c_pause != 1 || c_pending != 1 || c_yx != 1 || c_auto != 1 || c_resume != 1 || c_hook != 1) {
        printf("v3.8 patch validation failed: inc=%d proto=%d state=%d pause=%d pending=%d yx=%d auto=%d resume=%d hook=%d\n", c_include, c_proto, c_state, c_pause, c_pending, c_yx, c_auto, c_resume, c_hook) > "/dev/stderr"
        exit 43
    }
}
' "$src" > "$tmp"

mv "$tmp" "$src"

grep -q 'SUICUNE_TICK_BENCH_N 4096' "$src"
grep -q 'observe_version,fixed_arm_tick' "$src"
grep -q 'suicune_obs_post_resume_hook_tick' "$src"
grep -q 'append_suicune_observe_csv();' "$src"

echo "Applied Suicune Observe v3.8 to $src"
