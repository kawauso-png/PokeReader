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

# -------------------------------------------------------------------------
# C host: lock the START of Exact-2F to one of 16 host/display-cycle slots.
# v4.9 already locks the post-Exact resume.  v5.0 makes the earlier boundary
# deterministic too, which directly attacks the rel26/J27 branch selector.
# -------------------------------------------------------------------------
m = rep(
    m,
    '''static u64 suicune_phase_actual_tick = 0;\n\nu32 host_resume_phase_slot(void) { return suicune_phase_slot; }''',
    '''static u64 suicune_phase_actual_tick = 0;\n\n// Suicune Start Phase Lock v5.0.  Track the last top-screen hook even before\n// Y+X is pressed; while paused it becomes a stable display-cycle anchor.\nstatic u32 suicune_start_phase_slot = 0;\nstatic bool suicune_start_phase_lock_active = false;\nstatic u64 suicune_start_last_top_tick = 0;\nstatic u64 suicune_start_phase_anchor_tick = 0;\nstatic u64 suicune_start_phase_target_tick = 0;\nstatic u64 suicune_start_phase_actual_tick = 0;\n\nu32 host_start_phase_slot(void) { return suicune_start_phase_slot; }\nu32 host_start_phase_active(void) { return suicune_start_phase_actual_tick != 0 ? 1 : 0; }\nu64 host_start_phase_period(void) { return SUICUNE_PHASE_PERIOD_TICKS; }\nu64 host_start_phase_anchor(void) { return suicune_start_phase_anchor_tick; }\nu64 host_start_phase_target(void) { return suicune_start_phase_target_tick; }\nu64 host_start_phase_actual(void) { return suicune_start_phase_actual_tick; }\n\nu32 host_resume_phase_slot(void) { return suicune_phase_slot; }''',
    "add start phase state",
)

m = rep(
    m,
    '''return (fixed_a_frames & 0xff) | ((fixed_last_run & 0xff) << 8) | ((u32)fixed_armed << 16) | ((fixed_frames_remaining > 0) << 17) | (physical_a << 18) | (physical_up << 19) | ((u32)fixed_run_pending << 20) | ((suicune_phase_slot & 0x0f) << 21) | ((u32)suicune_phase_lock_active << 25);''',
    '''return (fixed_a_frames & 0xff) | ((fixed_last_run & 0xff) << 8) | ((u32)fixed_armed << 16) | ((fixed_frames_remaining > 0) << 17) | (physical_a << 18) | (physical_up << 19) | ((u32)fixed_run_pending << 20) | ((suicune_phase_slot & 0x0f) << 21) | ((u32)suicune_phase_lock_active << 25) | ((suicune_start_phase_slot & 0x0f) << 26);''',
    "pack start slot",
)

# v4.9 used the selector for Resume.  In v5.0 Resume is intentionally held at
# P00 during the causal test; the same controls now select Exact-2F START slot.
m = rep(
    m,
    '''            // v4.9 phase selector: left/right = +/-1, down = opposite half-cycle.\n            if (just_pressed & KEY_DRIGHT)\n                suicune_phase_slot = (suicune_phase_slot + 1) & 0x0f;\n            if (just_pressed & KEY_DLEFT)\n                suicune_phase_slot = (suicune_phase_slot + 15) & 0x0f;\n            if (just_pressed & KEY_DDOWN)\n                suicune_phase_slot ^= 8;''',
    '''            // v5.0 START phase selector: left/right = +/-1, down = opposite half-cycle.\n            // Resume remains P00 so only one causal variable is changed.\n            suicune_phase_slot = 0;\n            if (just_pressed & KEY_DRIGHT)\n                suicune_start_phase_slot = (suicune_start_phase_slot + 1) & 0x0f;\n            if (just_pressed & KEY_DLEFT)\n                suicune_start_phase_slot = (suicune_start_phase_slot + 15) & 0x0f;\n            if (just_pressed & KEY_DDOWN)\n                suicune_start_phase_slot ^= 8;''',
    "repurpose selector to start phase",
)

m = rep(
    m,
    '''                    suicune_phase_actual_tick = 0;''',
    '''                    suicune_phase_actual_tick = 0;\n                    suicune_start_phase_lock_active = true;\n                    suicune_start_phase_anchor_tick = suicune_start_last_top_tick;\n                    suicune_start_phase_target_tick = 0;\n                    suicune_start_phase_actual_tick = 0;''',
    "arm start phase lock",
)

# Capture every top hook, including the one immediately preceding the frozen Target.
m = rep(
    m,
    '''    if (isTopScreen && suicune_obs_arm_tick != 0)\n    {\n        u64 top_tick = svcGetSystemTick();\n        suicune_observe_top_hook(top_tick);\n        if (suicune_auto_resume_pending)\n            suicune_phase_anchor_tick = top_tick;\n    }''',
    '''    if (isTopScreen)\n    {\n        u64 top_tick = svcGetSystemTick();\n        suicune_start_last_top_tick = top_tick;\n        if (suicune_obs_arm_tick != 0)\n        {\n            suicune_observe_top_hook(top_tick);\n            if (suicune_auto_resume_pending)\n                suicune_phase_anchor_tick = top_tick;\n        }\n    }''',
    "capture pre-arm top hook",
)

# Once Y/X are physically released, do not immediately start Exact-2F.  Wait
# until the selected display-cycle slot, then release exactly two game frames.
m = rep(
    m,
    '''                suicune_obs_fixed_release_tick = svcGetSystemTick();\n                suicune_obs_fixed_start_tick = svcGetSystemTick();\n                suicune_obs_wait_fixed_hook = true;''',
    '''                suicune_obs_fixed_release_tick = svcGetSystemTick();\n                if (suicune_auto_resume_pending && suicune_start_phase_lock_active && suicune_start_phase_anchor_tick != 0)\n                {\n                    u64 now = suicune_obs_fixed_release_tick;\n                    u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_start_phase_slot) / SUICUNE_PHASE_SLOTS;\n                    u64 target = suicune_start_phase_anchor_tick + offset;\n                    if (target <= now + 4096ULL)\n                    {\n                        u64 delta = (now + 4096ULL) - target;\n                        target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;\n                    }\n                    suicune_start_phase_target_tick = target;\n                    while (svcGetSystemTick() < target) { }\n                    suicune_start_phase_actual_tick = svcGetSystemTick();\n                }\n                suicune_obs_fixed_start_tick = svcGetSystemTick();\n                suicune_obs_wait_fixed_hook = true;''',
    "wait before exact start",
)

# -------------------------------------------------------------------------
# Rust bindings and display/CSV diagnostics.
# -------------------------------------------------------------------------
b = rep(
    b,
    '''    pub fn host_resume_phase_slot() -> u32;''',
    '''    pub fn host_start_phase_slot() -> u32;\n    pub fn host_start_phase_active() -> u32;\n    pub fn host_start_phase_period() -> u64;\n    pub fn host_start_phase_anchor() -> u64;\n    pub fn host_start_phase_target() -> u64;\n    pub fn host_start_phase_actual() -> u64;\n    pub fn host_resume_phase_slot() -> u32;''',
    "start binding declarations",
)

b = rep(
    b,
    '''    pub extern "C" fn host_resume_phase_slot() -> u32 { 0 }''',
    '''    pub extern "C" fn host_start_phase_slot() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_start_phase_active() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_start_phase_period() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_start_phase_anchor() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_start_phase_target() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_start_phase_actual() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_resume_phase_slot() -> u32 { 0 }''',
    "start binding stubs",
)

i = rep(
    i,
    '''    pub phase_lock: bool,\n}''',
    '''    pub phase_lock: bool,\n    pub start_phase_slot: u8,\n}''',
    "start slot field",
)

i = rep(
    i,
    '''        phase_lock: (bits & (1 << 25)) != 0,\n    }''',
    '''        phase_lock: (bits & (1 << 25)) != 0,\n        start_phase_slot: ((bits >> 26) & 0x0f) as u8,\n    }''',
    "decode start slot",
)

i += '''\n\n/// v5.0 Exact-2F START phase diagnostics.\npub struct StartPhaseMetrics {\n    pub slot: u32,\n    pub active: bool,\n    pub period: u64,\n    pub anchor: u64,\n    pub target: u64,\n    pub actual: u64,\n}\n\npub fn start_phase_metrics() -> StartPhaseMetrics {\n    StartPhaseMetrics {\n        slot: unsafe { bindings::host_start_phase_slot() },\n        active: unsafe { bindings::host_start_phase_active() } != 0,\n        period: unsafe { bindings::host_start_phase_period() },\n        anchor: unsafe { bindings::host_start_phase_anchor() },\n        target: unsafe { bindings::host_start_phase_target() },\n        actual: unsafe { bindings::host_start_phase_actual() },\n    }\n}\n'''

t = rep(
    t,
    '''            "Fix {} A{} {} U{} P{:02}",\n            fixed.frames,\n            fixed.armed as u8,\n            run,\n            fixed.physical_up as u8,\n            fixed.phase_slot\n        );''',
    '''            "Fix {} A{} {} U{} S{:02} P{:02}",\n            fixed.frames,\n            fixed.armed as u8,\n            run,\n            fixed.physical_up as u8,\n            fixed.start_phase_slot,\n            fixed.phase_slot\n        );''',
    "draw start and resume slots",
)

# Save START metrics immediately before the existing resume metrics section.
t = rep(
    t,
    '''        let rpm = pnp::resume_phase_metrics();\n        line.clear();''',
    '''        let spm = pnp::start_phase_metrics();\n        line.clear();\n        let serr = spm.actual as i128 - spm.target as i128;\n        let _ = write!(line,\n            "\\nstart_phase,version,slot,active,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks\\n"\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line,\n            "SPH,V50,{},{},{},{},{},{},{}\\n",\n            spm.slot, spm.active as u8, spm.period, spm.anchor, spm.target, spm.actual, serr\n        );\n        pnp::trace_file_write(line.as_bytes());\n\n        let rpm = pnp::resume_phase_metrics();\n        line.clear();''',
    "save start metrics",
)

# v4.9's active flag is false after successful resume.  For saved diagnostics,
# report whether the lock actually executed (actual tick nonzero).
t = rep(
    t,
    '''            rpm.slot, rpm.active as u8, rpm.period, rpm.anchor, rpm.target, rpm.actual, err''',
    '''            rpm.slot, (rpm.actual != 0) as u8, rpm.period, rpm.anchor, rpm.target, rpm.actual, err''',
    "fix resume used flag",
)

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print("Applied Suicune Start+Resume Phase Lock v5.0")
