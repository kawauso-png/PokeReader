from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767j {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.7j keeps v7.6.7i's FFA4 Exact2 authority and changes only the
# post-release Resume timing.  After physical UP is confirmed released while
# paused, wait for absolute host-cycle M14 and then resume the untouched VC.
# No game/input/RNG/DIV/DV/save value is written or synthesized.

C = Path('3gx/sources/main.c')
c = C.read_text()
old = '''        // After Crystal accepted UP on two advances, remain frozen until the
        // user physically releases UP; then resume the untouched game.
        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) == 0)
            {
                suicune_exact2_release_confirmed();
                fixed_frames_remaining = 0;
                fixed_run_pending = false;
                is_paused = false;
                break;
            }
            svcSleepThread(1000000);
            continue;
        }
'''
new = '''        // v7.6.7j: after FFA4 proved two UP polls, stay frozen until physical
        // UP is released, then resume at one fixed absolute host phase (M14).
        // This controls only Pause/Resume timing; no input value is modified.
        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) == 0)
            {
                suicune_exact2_release_confirmed();
                u64 now = svcGetSystemTick();
                const u32 wanted = 14U;
                u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;
                while (((u32)cycle & 15U) != wanted) cycle++;
                u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;
                if (target <= now + 4096ULL)
                {
                    cycle += 16ULL;
                    target = cycle * SUICUNE_PHASE_PERIOD_TICKS;
                }

                suicune_obs_up_release_tick = now;
                suicune_phase_slot = wanted;
                suicune_phase_lock_active = true;
                suicune_phase_anchor_tick = now;
                suicune_phase_target_tick = target;
                while (svcGetSystemTick() < target) { }
                suicune_phase_actual_tick = svcGetSystemTick();

                fixed_frames_remaining = 0;
                fixed_run_pending = false;
                suicune_obs_resume_tick = suicune_phase_actual_tick;
                suicune_obs_wait_resume_hook = true;
                is_paused = false;
                break;
            }
            svcSleepThread(1000000);
            continue;
        }
'''
c = rep(c, old, new, 'M14 release/resume phase lock')
C.write_text(c)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
if t.count('V767I') < 5:
    raise SystemExit(f'v767j lineage markers too few: {t.count("V767I")}')
t = t.replace('V767I', 'V767J')
T.write_text(t)

print('Applied v7.6.7j: FFA4 Exact2 + physical release + absolute M14 Resume phase lock')
