#!/usr/bin/env python3
from pathlib import Path
M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
m=M.read_text(); t=T.read_text()

def need(x,s,label):
    if s not in x: raise SystemExit('v738 missing '+label+': '+s[:160])
def rep(x,a,b,label,count=1):
    n=x.count(a)
    if n!=count: raise SystemExit(f'v738 {label}: expected {count}, got {n}')
    return x.replace(a,b)

# --- Host input: debounced UP request, phase-boundary final proof ---------
# New debounce counters must be declared with the other TEST globals because
# suicune_host_transient_reset() is defined before the helper functions.
old_globals='''static bool suicune_test_exec_active = false;\nstatic u32 suicune_test_exec_state = 0; // 0 idle,1 ready,2 UP stable,3 armed,4 exact2F,5 release,6 resumed,7 abort\n'''
new_globals='''static bool suicune_test_exec_active = false;\nstatic u32 suicune_test_exec_state = 0; // 0 idle,1 ready,2 UP stable,3 armed,4 exact2F,5 release,6 resumed,7 abort\nstatic u32 suicune_test_up_debounce = 0;\nstatic u32 suicune_test_phase_retries = 0;\n'''
m=rep(m,old_globals,new_globals,'declare debounce fields')

# v7.3.7 required exact UP-only continuously for the whole 0..1-frame host
# phase wait. Any transient HID zero/diagonal restarted the attempt. The VC is
# frozen, so only the final key state at the chosen boundary needs to be exact.
old_helper=r'''static bool suicune_test_up_only_now(void)
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
new_helper=r'''#define SUICUNE_TEST_UP_DEBOUNCE_SAMPLES 8U
#define SUICUNE_TEST_GAME_KEYS (KEY_A | KEY_B | KEY_X | KEY_Y | KEY_DUP | \
    KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R | KEY_START | KEY_SELECT)

static bool suicune_test_up_only_held(u32 held)
{
    return (held & SUICUNE_TEST_GAME_KEYS) == KEY_DUP;
}

static bool suicune_test_up_only_now(void)
{
    scan_input();
    return suicune_test_up_only_held(get_current_keys());
}

static bool suicune_test_wait_start_phase_boundary(void)
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
            svcSleepThread(250000); // root frozen; do not reject transient HID bounce here.
        suicune_start_phase_actual_tick = svcGetSystemTick();
    }
    // The only key proof that matters before ARM: exactly UP at the selected
    // boundary. A miss is retryable and consumes zero VC frames.
    return suicune_test_up_only_now();
}
'''
m=rep(m,old_helper,new_helper,'replace strict phase helper')

old_reset='''    suicune_test_ready_flag = false;\n    suicune_test_exec_active = false;\n    suicune_test_exec_state = 0;\n'''
new_reset='''    suicune_test_ready_flag = false;\n    suicune_test_exec_active = false;\n    suicune_test_exec_state = 0;\n    suicune_test_up_debounce = 0;\n    suicune_test_phase_retries = 0;\n'''
m=rep(m,old_reset,new_reset,'reset debounce fields')

old_exec=r'''        if (suicune_test_exec_active && suicune_test_exec_state <= 2)
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
new_exec=r'''        if (suicune_test_exec_active && suicune_test_exec_state <= 2)
        {
            if (!suicune_test_ready_flag)
            {
                suicune_test_exec_active = false;
                suicune_test_exec_state = 0;
                suicune_test_up_debounce = 0;
                continue;
            }

            // Human-friendly debounce: require a short stable UP-only hold
            // before phase alignment. One bad sample simply resets the debounce;
            // it does not consume the candidate or a VC frame.
            if (!suicune_test_up_only_now())
            {
                suicune_test_up_debounce = 0;
                suicune_test_exec_state = 1;
                svcSleepThread(1000000);
                continue;
            }
            if (suicune_test_up_debounce < SUICUNE_TEST_UP_DEBOUNCE_SAMPLES)
            {
                suicune_test_up_debounce++;
                suicune_test_exec_state = 1;
                svcSleepThread(1000000);
                continue;
            }

            // Root is frozen. Wait to the selected host boundary without
            // requiring every intermediate HID sample to be perfect. Only the
            // boundary sample is authoritative. A miss retries at zero frames.
            suicune_test_exec_state = 2;
            if (!suicune_test_wait_start_phase_boundary())
            {
                suicune_test_phase_retries++;
                suicune_test_up_debounce = 0;
                suicune_test_exec_state = 1;
                continue;
            }

            // Exact UP has already been proven at the boundary. ARM and pass
            // frame #1 immediately; do not create a second post-ARM HID race.
            suicune_test_exec_state = 3;
            arm_suicune_probe();
            suicune_test_begin_exact2f();
            fixed_frames_remaining--; // exact frame #1
            break;
        }
'''
m=rep(m,old_exec,new_exec,'debounced executor')

old_f2='''            if (suicune_auto_resume_pending && !(held & KEY_DUP))\n'''
new_f2='''            if (suicune_auto_resume_pending && !suicune_test_up_only_held(held))\n'''
m=rep(m,old_f2,new_f2,'frame2 exact UP guard')

old_release='''            if ((held & (KEY_DUP | KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)\n'''
new_release='''            if ((held & SUICUNE_TEST_GAME_KEYS) == 0)\n'''
m=rep(m,old_release,new_release,'all-game-key release guard')

# --- Search: remove proven GLOBAL speculative Tier2 -----------------------
# 0099(2),0100(2),0128-0136 give ten recent TEST executions; every selected
# proven lane had a different observed PRE cell, and none reproduced its
# predicted POST. Keep only PRE-matched proven/empirical candidates until a
# validated cross-PRE transport model exists.
start=t.index(' // Tier 2: global speculative branches.')
end=t.index('\n }\n',start)
t=t[:start]+''' // v7.3.8: GLOBAL speculative proven transport disabled.\n // Candidate search is intentionally limited to the actually observed PRE\n // cell. rel40 remains the downstream branch/rebind boundary.\n'''+t[end:]

# --- rel40 learning: do not throw away a high-confidence nonzero POST -----
# 0133 had valid B/r8, best=3, second=19 but v7.3.7 hard-saved at rel40,
# losing the suffix. Any valid classifier result is safe to continue as LEARN;
# exact score0 is still required for shiny rebind.
old_rel40='''                let post=classify_post_entries(self.entries,self.len,self.probe_target.advance);\n                if !post.valid||post.best_score!=0{self.practical_fail(1);return}\n                self.practical_post_proto=post.proto;self.practical_post_rot=post.rot40;self.practical_post_score=post.best_score;\n                let identity_ok=practical::prediction_post(self.practical_lane)==Some((post.proto,post.rot40));\n                let root_ok=e.state==self.practical_expected40_state&&e.div==self.practical_expected40_div;\n                if !identity_ok||!root_ok{\n                    if self.rebind_shiny_post_v736(post.proto,post.rot40,e.state,e.div){return}\n                    self.enter_stage3_learn(post.proto,post.rot40);return\n                }\n'''
new_rel40='''                let post=classify_post_entries(self.entries,self.len,self.probe_target.advance);\n                if !post.valid{self.practical_fail(1);return}\n                self.practical_post_proto=post.proto;self.practical_post_rot=post.rot40;self.practical_post_score=post.best_score;\n                if post.best_score!=0{\n                    self.practical_learn=2;\n                    self.enter_stage3_learn(post.proto,post.rot40);\n                    self.practical_learn=2;\n                    return\n                }\n                let identity_ok=practical::prediction_post(self.practical_lane)==Some((post.proto,post.rot40));\n                let root_ok=e.state==self.practical_expected40_state&&e.div==self.practical_expected40_div;\n                if !identity_ok||!root_ok{\n                    if self.rebind_shiny_post_v736(post.proto,post.rot40,e.state,e.div){return}\n                    self.enter_stage3_learn(post.proto,post.rot40);return\n                }\n'''
t=rep(t,old_rel40,new_rel40,'continue approximate POST learn')

# UI/telemetry epoch and clearer operation.
t=t.replace('S737','S738')
t=t.replace('EXEC,V737','EXEC,V738')
t=t.replace('GLOBALBEAM,V737','GLOBALBEAM,V738')
t=t.replace('SOFTRESET,V737','SOFTRESET,V738')
t=t.replace('S738 TEST HOLD UP 0.3s','S738 TEST HOLD UP 0.5s')
t=t.replace('}else if self.practical_learn==1&&self.probe_session&&self.probe_active{pnp::println!("S738 LEARN POST");',
''' }else if self.practical_learn==2&&self.probe_session&&self.probe_active{pnp::println!("S738 LEARN POST~ S{}",self.practical_post_score);\n        }else if self.practical_learn==1&&self.probe_session&&self.probe_active{pnp::println!("S738 LEARN POST");''')

for s in ['S738 TEST HOLD UP 0.5s','EXEC,V738','GLOBALBEAM,V738','SOFTRESET,V738','S738 LEARN POST~']:
    need(t,s,s)
if 'S737' in t: raise SystemExit('v738 stale S737 UI')
ms=t.index('fn practical_wait_monitor'); me=t.index('fn practical_fail',ms)
if 'practical_global_speculative=true' in t[ms:me]: raise SystemExit('v738 global speculative scan remains')
if 'for id in 1..=practical::proven_lane_count()' in t[ms:me]: raise SystemExit('v738 global proven loop remains')

M.write_text(m);T.write_text(t)
print('Applied v7.3.8: debounced UP-only, boundary-only phase proof, no post-ARM reread, exact frame2/all-key release guards, global speculative search disabled, approximate POST continues LEARN')
