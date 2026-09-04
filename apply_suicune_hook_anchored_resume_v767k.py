from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767k {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

C = Path('3gx/sources/main.c')
c = C.read_text()

# Add hook-anchored telemetry beside v3.8 observe state.
c = rep(c,
'''static u64 suicune_obs_post_resume_hook_tick = 0;\nstatic bool suicune_obs_wait_fixed_hook = false;''',
'''static u64 suicune_obs_post_resume_hook_tick = 0;\n\n// v7.6.7k: anchor post-Exact2 Resume to the live top-screen hook train, not\n// to systemTick zero.  This remains Pause/Resume timing control only.\nstatic u64 suicune_hooklock_prev_top_tick = 0;\nstatic u64 suicune_hooklock_last_top_tick = 0;\nstatic u64 suicune_hooklock_anchor_tick = 0;\nstatic u64 suicune_hooklock_anchor_prev_tick = 0;\nstatic u64 suicune_hooklock_resume_target_tick = 0;\nstatic u64 suicune_hooklock_resume_actual_tick = 0;\nstatic u64 suicune_hooklock_predicted_hook_tick = 0;\nstatic u32 suicune_hooklock_slot = 14;\n\nstatic bool suicune_obs_wait_fixed_hook = false;''',
'add hooklock state')

# Reset per trial, while the continuously observed top train itself is refreshed by run_hook.
c = rep(c,
'''    suicune_obs_post_resume_hook_tick = 0;\n    suicune_obs_wait_fixed_hook = false;''',
'''    suicune_obs_post_resume_hook_tick = 0;\n    suicune_hooklock_anchor_tick = 0;\n    suicune_hooklock_anchor_prev_tick = 0;\n    suicune_hooklock_resume_target_tick = 0;\n    suicune_hooklock_resume_actual_tick = 0;\n    suicune_hooklock_predicted_hook_tick = 0;\n    suicune_hooklock_slot = 14;\n    suicune_obs_wait_fixed_hook = false;''',
'reset hooklock trial state')

# Replace j absolute-M14 release path with top-hook anchored slot14.
old = '''        // v7.6.7j: after FFA4 proved two UP polls, stay frozen until physical\n        // UP is released, then resume at one fixed absolute host phase (M14).\n        // This controls only Pause/Resume timing; no input value is modified.\n        if (suicune_exact2_release_waiting())\n        {\n            if ((held & KEY_DUP) == 0)\n            {\n                suicune_exact2_release_confirmed();\n                u64 now = svcGetSystemTick();\n                const u32 wanted = 14U;\n                u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;\n                while (((u32)cycle & 15U) != wanted) cycle++;\n                u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                if (target <= now + 4096ULL)\n                {\n                    cycle += 16ULL;\n                    target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                }\n\n                suicune_obs_up_release_tick = now;\n                suicune_phase_slot = wanted;\n                suicune_phase_lock_active = true;\n                suicune_phase_anchor_tick = now;\n                suicune_phase_target_tick = target;\n                while (svcGetSystemTick() < target) { }\n                suicune_phase_actual_tick = svcGetSystemTick();\n\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                suicune_obs_resume_tick = suicune_phase_actual_tick;\n                suicune_obs_wait_resume_hook = true;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }\n'''
new = '''        // v7.6.7k: after FFA4 proved two UP polls, stay frozen until physical\n        // UP is released.  Then place Resume at slot14 RELATIVE TO the latest\n        // observed top-screen hook train.  No input/game/RNG/DIV value changes.\n        if (suicune_exact2_release_waiting())\n        {\n            if ((held & KEY_DUP) == 0)\n            {\n                suicune_exact2_release_confirmed();\n                u64 now = svcGetSystemTick();\n                const u32 wanted = 14U;\n                const u64 period = SUICUNE_PHASE_PERIOD_TICKS;\n                const u64 offset = (period * (u64)wanted) / 16ULL;\n                u64 anchor = suicune_hooklock_last_top_tick;\n\n                // Fail closed to ordinary immediate Resume only if no top-hook\n                // anchor has ever been observed.  This is telemetry-visible.\n                u64 target = now;\n                u64 predicted_hook = 0;\n                if (anchor != 0)\n                {\n                    target = anchor + offset;\n                    if (target <= now + 4096ULL)\n                    {\n                        u64 delta = (now + 4096ULL) - target;\n                        u64 wraps = delta / period + 1ULL;\n                        target += wraps * period;\n                    }\n                    predicted_hook = target + (period - offset);\n                    while (svcGetSystemTick() < target) { }\n                }\n\n                suicune_obs_up_release_tick = now;\n                suicune_hooklock_anchor_tick = anchor;\n                suicune_hooklock_anchor_prev_tick = suicune_hooklock_prev_top_tick;\n                suicune_hooklock_resume_target_tick = target;\n                suicune_hooklock_resume_actual_tick = svcGetSystemTick();\n                suicune_hooklock_predicted_hook_tick = predicted_hook;\n                suicune_hooklock_slot = wanted;\n\n                // Keep legacy RPH fields populated, but now anchor means the\n                // actual latest top-hook, not release time / tick-zero phase.\n                suicune_phase_slot = wanted;\n                suicune_phase_lock_active = anchor != 0;\n                suicune_phase_anchor_tick = anchor;\n                suicune_phase_target_tick = target;\n                suicune_phase_actual_tick = suicune_hooklock_resume_actual_tick;\n\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                suicune_obs_resume_tick = suicune_hooklock_resume_actual_tick;\n                suicune_obs_wait_resume_hook = true;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }\n'''
c = rep(c, old, new, 'replace absolute M14 with hook-anchored M14')

# Track the live top-hook train using the existing top callback; no extra hook is introduced.
c = rep(c,
'''        u64 top_tick = svcGetSystemTick();\n        suicune_start_last_top_tick = top_tick;''',
'''        u64 top_tick = svcGetSystemTick();\n        suicune_hooklock_prev_top_tick = suicune_hooklock_last_top_tick;\n        suicune_hooklock_last_top_tick = top_tick;\n        suicune_start_last_top_tick = top_tick;''',
'capture top-hook train')

# Append one compact hook-lock line after the existing v3.8 observe line.
needle = '''        if (len > 0)\n        {\n            FSFILE_Write(f, &written, size, linebuf, (u32)len, 0);\n            FSFILE_Flush(f);\n        }\n    }\n    if (f != 0) FSFILE_Close(f);'''
replacement = '''        if (len > 0)\n        {\n            FSFILE_Write(f, &written, size, linebuf, (u32)len, 0);\n            FSFILE_Flush(f);\n            size += (u64)len;\n        }\n\n        long long hook_err = 0;\n        if (suicune_hooklock_predicted_hook_tick != 0 && suicune_obs_post_resume_hook_tick != 0)\n            hook_err = (long long)(suicune_obs_post_resume_hook_tick - suicune_hooklock_predicted_hook_tick);\n        u64 anchor_period = (suicune_hooklock_anchor_tick >= suicune_hooklock_anchor_prev_tick)\n            ? suicune_hooklock_anchor_tick - suicune_hooklock_anchor_prev_tick : 0;\n        len = sprintf(linebuf,\n            "\\nhook_lock,version,slot,anchor_top_tick,prev_top_tick,last_interval,resume_target_tick,resume_actual_tick,predicted_next_hook_tick,actual_next_hook_tick,hook_error_ticks\\n"\n            "HOOKLOCK,V767K,%lu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%lld\\n",\n            (unsigned long)suicune_hooklock_slot,\n            (unsigned long long)suicune_hooklock_anchor_tick,\n            (unsigned long long)suicune_hooklock_anchor_prev_tick,\n            (unsigned long long)anchor_period,\n            (unsigned long long)suicune_hooklock_resume_target_tick,\n            (unsigned long long)suicune_hooklock_resume_actual_tick,\n            (unsigned long long)suicune_hooklock_predicted_hook_tick,\n            (unsigned long long)suicune_obs_post_resume_hook_tick,\n            hook_err);\n        if (len > 0)\n        {\n            FSFILE_Write(f, &written, size, linebuf, (u32)len, 0);\n            FSFILE_Flush(f);\n        }\n    }\n    if (f != 0) FSFILE_Close(f);'''
c = rep(c, needle, replacement, 'append HOOKLOCK CSV')

C.write_text(c)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
if t.count('V767J') < 5:
    raise SystemExit(f'v767k lineage markers too few: {t.count("V767J")}')
t = t.replace('V767J', 'V767K')
T.write_text(t)

print('Applied v7.6.7k: FFA4 Exact2 + top-hook-anchored slot14 Resume')