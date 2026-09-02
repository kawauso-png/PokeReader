#!/usr/bin/env python3
from pathlib import Path

M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
m=M.read_text(); t=T.read_text()

def need(x,s,label):
    if s not in x: raise SystemExit('v737 missing '+label+': '+s[:120])
def rep(x,a,b,label,count=1):
    n=x.count(a)
    if n!=count: raise SystemExit(f'v737 {label}: expected {count}, got {n}')
    return x.replace(a,b)

# Production TEST phase wait must continuously sample physical UP.  If UP is
# released before the selected host phase, the candidate root is still frozen
# and remains READY; no probe is armed and no VC frame is consumed.
helper=r'''
static bool suicune_test_up_only_now(void)
{
    scan_input();
    u32 held = get_current_keys();
    const u32 other_game_keys = KEY_A | KEY_B | KEY_X | KEY_Y |
        KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT |
        KEY_L | KEY_R | KEY_START | KEY_SELECT;
    return (held & KEY_DUP) != 0 && (held & other_game_keys) == 0;
}

static bool suicune_test_wait_start_phase_while_up(void)
{
    suicune_start_phase_slot = 0;
    suicune_start_phase_lock_active = true;
    suicune_start_phase_anchor_tick = suicune_start_last_top_tick;
    suicune_start_phase_target_tick = 0;
    suicune_start_phase_actual_tick = 0;

    u64 now = svcGetSystemTick();
    u64 target = suicune_start_phase_anchor_tick;
    if (target != 0)
    {
        if (target <= now + 4096ULL)
        {
            u64 delta = (now + 4096ULL) - target;
            target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;
        }
        suicune_start_phase_target_tick = target;
        while (svcGetSystemTick() < target)
        {
            if (!suicune_test_up_only_now()) return false;
            svcSleepThread(250000); // 0.25 ms; VC remains frozen.
        }
        suicune_start_phase_actual_tick = svcGetSystemTick();
    }
    return suicune_test_up_only_now();
}

'''
needle='static void suicune_test_begin_exact2f(void)\n{'
need(m,needle,'begin_exact2f')
m=m.replace(needle,helper+needle,1)

old_phase=r'''    suicune_start_phase_slot = 0;
    suicune_start_phase_lock_active = true;
    suicune_start_phase_anchor_tick = suicune_start_last_top_tick;
    suicune_start_phase_target_tick = 0;
    suicune_start_phase_actual_tick = 0;

    // Same START-phase lock used by the historically successful FastValidate
    // controller, but now there is no B/Y/X chord to release first.
    u64 now = svcGetSystemTick();
    u64 target = suicune_start_phase_anchor_tick;
    if (target != 0)
    {
        if (target <= now + 4096ULL)
        {
            u64 delta = (now + 4096ULL) - target;
            target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;
        }
        suicune_start_phase_target_tick = target;
        while (svcGetSystemTick() < target) { }
        suicune_start_phase_actual_tick = svcGetSystemTick();
    }
'''
new_phase=r'''    // START phase was already aligned by suicune_test_wait_start_phase_while_up().
    // Do not busy-wait here: doing so without re-sampling HID created the v7.3.6
    // intermittent early-release race (0F/1F UP instead of exact 2F).
'''
m=rep(m,old_phase,new_phase,'remove blind phase wait')

old_exec=r'''        if (suicune_test_exec_active && suicune_test_exec_state <= 2)
        {
            const u32 other_game_keys = KEY_A | KEY_B | KEY_X | KEY_Y |
                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT |
                KEY_L | KEY_R | KEY_START | KEY_SELECT;
            bool up_only = (held & KEY_DUP) != 0 && (held & other_game_keys) == 0;

            if (!suicune_test_ready_flag)
            {
                suicune_test_exec_active = false;
                suicune_test_exec_state = 0;
                continue;
            }
            if (!up_only)
            {
                suicune_test_exec_state = 1;
                svcSleepThread(1000000);
                continue;
            }
            if (suicune_test_exec_state == 1)
            {
                // 20 ms stable UP-only hold. The VC is frozen, so this changes
                // no RNG/root and removes dependence on a simultaneous B edge.
                suicune_test_exec_state = 2;
                svcSleepThread(20000000);
                continue;
            }

            suicune_test_exec_state = 3;
            arm_suicune_probe();
            // arm_suicune_probe() clears ready through Rust, but this C executor
            // remains active until Exact2F/release completes.
            suicune_test_begin_exact2f();
            continue;
        }
'''
new_exec=r'''        if (suicune_test_exec_active && suicune_test_exec_state <= 2)
        {
            if (!suicune_test_ready_flag)
            {
                suicune_test_exec_active = false;
                suicune_test_exec_state = 0;
                continue;
            }
            if (!suicune_test_up_only_now())
            {
                suicune_test_exec_state = 1;
                svcSleepThread(1000000);
                continue;
            }

            // Align the host phase while continuously proving physical UP-only.
            // A release here is retryable: the candidate/root remains frozen.
            suicune_test_exec_state = 2;
            if (!suicune_test_wait_start_phase_while_up())
            {
                suicune_test_exec_state = 1;
                continue;
            }

            // Only now consume the candidate and arm the real probe.
            suicune_test_exec_state = 3;
            arm_suicune_probe();
            suicune_test_begin_exact2f();

            // Minimize the post-ARM release race: re-read HID and pass frame #1
            // immediately from this same pause-loop iteration.
            if (!suicune_test_up_only_now())
            {
                suicune_auto_resume_pending = false;
                fixed_frames_remaining = 0;
                fixed_run_pending = false;
                suicune_test_exec_state = 7;
                suicune_test_exec_active = false;
                continue;
            }
            fixed_frames_remaining--; // exact frame #1
            break;
        }
'''
m=rep(m,old_exec,new_exec,'production TEST executor')

# Keep the proven exact-frame safety check for frame #2.  State 7 remains a
# hard abort if the user releases during the actual two-frame window.
need(m,'if (suicune_auto_resume_pending && !(held & KEY_DUP))','frame2 UP guard')
need(m,'if (suicune_test_exec_active) { suicune_test_exec_state = 6; suicune_test_exec_active = false; }','EX6 resume')

# UI/telemetry: make the physical operation explicit and remove stale reset text.
t=t.replace('S736','S737')
t=t.replace('EXEC,V736','EXEC,V737')
t=t.replace('GLOBALBEAM,V736','GLOBALBEAM,V737')
t=t.replace('SOFTRESET,V734','SOFTRESET,V737')
t=t.replace('S737 TEST HOLD UP','S737 TEST HOLD UP 0.3s')
t=t.replace('S737 RETRY B40 R>RESET','S737 FAIL B40 SOFT RESET')
t=t.replace('S737 RETRY B716 R>RESET','S737 FAIL B716 SOFT RESET')
t=t.replace('S737 RETRY B717 R>RESET','S737 FAIL B717 SOFT RESET')
t=t.replace('S737 RETRY M{} R>RESET','S737 FAIL M{} SOFT RESET')

for s in ['S737 TEST HOLD UP 0.3s','EXEC,V737','GLOBALBEAM,V737','SOFTRESET,V737']:
    need(t,s,s)
if 'S736' in t: raise SystemExit('v737 stale S736 UI remains')
if 'R>RESET' in t: raise SystemExit('v737 stale R reset instruction remains')

M.write_text(m); T.write_text(t)
print('Applied v7.3.7: continuous-UP phase alignment, retryable pre-ARM release, immediate frame1, explicit 0.3s hold UI, corrected reset labels')
