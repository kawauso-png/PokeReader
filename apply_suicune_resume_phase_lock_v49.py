#!/usr/bin/env python3
from pathlib import Path

main_path = Path("3gx/sources/main.c")
bind_path = Path("reader_core/src/pnp/bindings.rs")
input_path = Path("reader_core/src/pnp/input.rs")
trace_path = Path("reader_core/src/crystal/trace.rs")

m = main_path.read_text()
b = bind_path.read_text()
i = input_path.read_text()
t = trace_path.read_text()


def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return src.replace(old, new, 1)

m = rep(m,
'''static bool suicune_auto_resume_pending = false;''',
'''static bool suicune_auto_resume_pending = false;

// Suicune Resume Phase Lock v4.9.  After Exact-2F, UP release no longer
// determines the exact wall-clock resume phase.  We wait for one of 16 slots
// relative to the last Exact-frame top-screen hook and only then free-run.
#define SUICUNE_PHASE_PERIOD_TICKS 4481233ULL
#define SUICUNE_PHASE_SLOTS 16U
static u32 suicune_phase_slot = 0;
static bool suicune_phase_lock_active = false;
static u64 suicune_phase_anchor_tick = 0;
static u64 suicune_phase_target_tick = 0;
static u64 suicune_phase_actual_tick = 0;

u32 host_resume_phase_slot(void) { return suicune_phase_slot; }
u32 host_resume_phase_active(void) { return suicune_phase_lock_active ? 1 : 0; }
u64 host_resume_phase_period(void) { return SUICUNE_PHASE_PERIOD_TICKS; }
u64 host_resume_phase_anchor(void) { return suicune_phase_anchor_tick; }
u64 host_resume_phase_target(void) { return suicune_phase_target_tick; }
u64 host_resume_phase_actual(void) { return suicune_phase_actual_tick; }''',
"add phase state")

m = rep(m,
'''return (fixed_a_frames & 0xff) | ((fixed_last_run & 0xff) << 8) | ((u32)fixed_armed << 16) | ((fixed_frames_remaining > 0) << 17) | (physical_a << 18) | (physical_up << 19) | ((u32)fixed_run_pending << 20);''',
'''return (fixed_a_frames & 0xff) | ((fixed_last_run & 0xff) << 8) | ((u32)fixed_armed << 16) | ((fixed_frames_remaining > 0) << 17) | (physical_a << 18) | (physical_up << 19) | ((u32)fixed_run_pending << 20) | ((suicune_phase_slot & 0x0f) << 21) | ((u32)suicune_phase_lock_active << 25);''',
"pack phase state")

m = rep(m,
'''            if ((just_pressed & KEY_DLEFT) && fixed_a_frames > FIXED_A_FRAMES_MIN)
            {
                fixed_a_frames--;
            }''',
'''            if ((just_pressed & KEY_DLEFT) && fixed_a_frames > FIXED_A_FRAMES_MIN)
            {
                fixed_a_frames--;
            }
            // v4.9 phase selector: left/right = +/-1, down = opposite half-cycle.
            if (just_pressed & KEY_DRIGHT)
                suicune_phase_slot = (suicune_phase_slot + 1) & 0x0f;
            if (just_pressed & KEY_DLEFT)
                suicune_phase_slot = (suicune_phase_slot + 15) & 0x0f;
            if (just_pressed & KEY_DDOWN)
                suicune_phase_slot ^= 8;''',
"phase slot controls")

m = rep(m,
'''                    suicune_auto_resume_pending = true;''',
'''                    suicune_auto_resume_pending = true;
                    suicune_phase_lock_active = true;
                    suicune_phase_anchor_tick = 0;
                    suicune_phase_target_tick = 0;
                    suicune_phase_actual_tick = 0;''',
"arm phase lock")

m = rep(m,
'''    if (isTopScreen && suicune_obs_arm_tick != 0)
    {
        suicune_observe_top_hook(svcGetSystemTick());
    }''',
'''    if (isTopScreen && suicune_obs_arm_tick != 0)
    {
        u64 top_tick = svcGetSystemTick();
        suicune_observe_top_hook(top_tick);
        if (suicune_auto_resume_pending)
            suicune_phase_anchor_tick = top_tick;
    }''',
"capture last fixed hook")

m = rep(m,
'''                suicune_obs_up_release_tick = svcGetSystemTick();
                suicune_auto_resume_pending = false;''',
'''                suicune_obs_up_release_tick = svcGetSystemTick();
                if (suicune_phase_lock_active && suicune_phase_anchor_tick != 0)
                {
                    u64 now = suicune_obs_up_release_tick;
                    u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_phase_slot) / SUICUNE_PHASE_SLOTS;
                    u64 target = suicune_phase_anchor_tick + offset;
                    if (target <= now + 4096ULL)
                    {
                        u64 delta = (now + 4096ULL) - target;
                        target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;
                    }
                    suicune_phase_target_tick = target;
                    while (svcGetSystemTick() < target) { }
                    suicune_phase_actual_tick = svcGetSystemTick();
                }
                suicune_auto_resume_pending = false;''',
"wait phase before resume")

m = rep(m,
'''            suicune_auto_resume_pending = false;
            break;''',
'''            suicune_auto_resume_pending = false;
            suicune_phase_lock_active = false;
            break;''',
"clear phase on manual resume")

b = rep(b,
'''    pub fn host_fixed_run_id() -> u32;''',
'''    pub fn host_fixed_run_id() -> u32;
    pub fn host_resume_phase_slot() -> u32;
    pub fn host_resume_phase_active() -> u32;
    pub fn host_resume_phase_period() -> u64;
    pub fn host_resume_phase_anchor() -> u64;
    pub fn host_resume_phase_target() -> u64;
    pub fn host_resume_phase_actual() -> u64;''',
"binding declarations")
b = rep(b,
'''    pub extern "C" fn host_fixed_run_id() -> u32 {
        0
    }''',
'''    pub extern "C" fn host_fixed_run_id() -> u32 {
        0
    }
    #[no_mangle]
    pub extern "C" fn host_resume_phase_slot() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_resume_phase_active() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_resume_phase_period() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_resume_phase_anchor() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_resume_phase_target() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_resume_phase_actual() -> u64 { 0 }''',
"binding stubs")

i = rep(i,
'''    pub physical_up: bool,
}''',
'''    pub physical_up: bool,
    pub phase_slot: u8,
    pub phase_lock: bool,
}''',
"fixed struct fields")
i = rep(i,
'''        pending: (bits & (1 << 20)) != 0,
    }''',
'''        pending: (bits & (1 << 20)) != 0,
        phase_slot: ((bits >> 21) & 0x0f) as u8,
        phase_lock: (bits & (1 << 25)) != 0,
    }''',
"fixed struct decode")
i += '''\n\n/// v4.9 Resume Phase Lock diagnostics; read only during draw/save, never in the timing hook.\npub struct ResumePhaseMetrics {\n    pub slot: u32,\n    pub active: bool,\n    pub period: u64,\n    pub anchor: u64,\n    pub target: u64,\n    pub actual: u64,\n}\n\npub fn resume_phase_metrics() -> ResumePhaseMetrics {\n    ResumePhaseMetrics {\n        slot: unsafe { bindings::host_resume_phase_slot() },\n        active: unsafe { bindings::host_resume_phase_active() } != 0,\n        period: unsafe { bindings::host_resume_phase_period() },\n        anchor: unsafe { bindings::host_resume_phase_anchor() },\n        target: unsafe { bindings::host_resume_phase_target() },\n        actual: unsafe { bindings::host_resume_phase_actual() },\n    }\n}\n'''

t = rep(t,
'''            "Fix {} A{} {} U{}",
            fixed.frames,
            fixed.armed as u8,
            run,
            fixed.physical_up as u8
        );''',
'''            "Fix {} A{} {} U{} P{:02}",
            fixed.frames,
            fixed.armed as u8,
            run,
            fixed.physical_up as u8,
            fixed.phase_slot
        );''',
"draw phase slot")

t = rep(t,
'''        // v3.5 intentionally omits the heavy differential dump. F604 is now
        // sampled directly at every rDIV hook, so ordinary probe timing stays clean.

        pnp::trace_file_close();''',
'''        // v3.5 intentionally omits the heavy differential dump. F604 is now
        // sampled directly at every rDIV hook, so ordinary probe timing stays clean.

        let rpm = pnp::resume_phase_metrics();
        line.clear();
        let err = rpm.actual as i128 - rpm.target as i128;
        let _ = write!(line,
            "\\nresume_phase,version,slot,active,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks\\n"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "RPH,V49,{},{},{},{},{},{},{}\\n",
            rpm.slot, rpm.active as u8, rpm.period, rpm.anchor, rpm.target, rpm.actual, err
        );
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();''',
"save phase metrics")

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print("Applied Suicune Resume Phase Lock v4.9")
