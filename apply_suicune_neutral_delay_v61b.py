#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
bind_path = Path('reader_core/src/pnp/bindings.rs')
input_path = Path('reader_core/src/pnp/input.rs')
trace_path = Path('reader_core/src/crystal/trace.rs')

m = main_path.read_text()
b = bind_path.read_text()
i = input_path.read_text()
t = trace_path.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# -------------------------------------------------------------------------
# v6.1b: measure the actuator inside each trial.
# Direct host reads do not advance the emulated GB. Capture rDIV+M-cycle
# subtick once when Y+B is accepted (pre), and once after exactly N neutral
# frames have completed and the game is frozen again (post).
# -------------------------------------------------------------------------
m = rep(m,
'''static bool suicune_delay_ready = false;\n\nu32 host_suicune_delay_profile_used(void) { return suicune_delay_profile_used; }''',
'''static bool suicune_delay_ready = false;\n\n#define SUICUNE_DIV_PTR_SLOT 0x0022f794\n#define SUICUNE_MCYCLE_SUBTICK_ADDR 0x0022f604\nstatic u32 suicune_delay_pre_valid = 0;\nstatic u8 suicune_delay_pre_div = 0;\nstatic u8 suicune_delay_pre_sub = 0;\nstatic u16 suicune_delay_pre_phase = 0;\nstatic u32 suicune_delay_post_valid = 0;\nstatic u8 suicune_delay_post_div = 0;\nstatic u8 suicune_delay_post_sub = 0;\nstatic u16 suicune_delay_post_phase = 0;\n\nstatic u8 suicune_live_div_direct(void)\n{\n    u32 ptr = *(volatile u32 *)SUICUNE_DIV_PTR_SLOT;\n    return ptr ? *(volatile u8 *)ptr : 0;\n}\n\nstatic u8 suicune_live_sub_direct(void)\n{\n    return *(volatile u8 *)SUICUNE_MCYCLE_SUBTICK_ADDR;\n}\n\nstatic u16 suicune_live_phase_direct(u8 div, u8 sub)\n{\n    return (u16)((((u16)div << 6) | (u16)sub) & 0x3fff);\n}\n\nu32 host_suicune_delay_pre_valid(void) { return suicune_delay_pre_valid; }\nu32 host_suicune_delay_pre_div(void) { return suicune_delay_pre_div; }\nu32 host_suicune_delay_pre_sub(void) { return suicune_delay_pre_sub; }\nu32 host_suicune_delay_pre_phase(void) { return suicune_delay_pre_phase; }\nu32 host_suicune_delay_post_valid(void) { return suicune_delay_post_valid; }\nu32 host_suicune_delay_post_div(void) { return suicune_delay_post_div; }\nu32 host_suicune_delay_post_sub(void) { return suicune_delay_post_sub; }\nu32 host_suicune_delay_post_phase(void) { return suicune_delay_post_phase; }\n\nu32 host_suicune_delay_profile_used(void) { return suicune_delay_profile_used; }''',
'add direct phase telemetry state')

m = rep(m,
'''                    suicune_delay_frames_executed = 0;\n                    suicune_delay_pending = true;''',
'''                    suicune_delay_frames_executed = 0;\n                    suicune_delay_pre_div = suicune_live_div_direct();\n                    suicune_delay_pre_sub = suicune_live_sub_direct();\n                    suicune_delay_pre_phase = suicune_live_phase_direct(suicune_delay_pre_div, suicune_delay_pre_sub);\n                    suicune_delay_pre_valid = 1;\n                    suicune_delay_post_valid = 0;\n                    suicune_delay_post_div = 0;\n                    suicune_delay_post_sub = 0;\n                    suicune_delay_post_phase = 0;\n                    suicune_delay_pending = true;''',
'capture pre-delay phase')

m = rep(m,
'''            suicune_delay_pending = false;\n            suicune_delay_started = false;\n            suicune_delay_ready = true;''',
'''            suicune_delay_post_div = suicune_live_div_direct();\n            suicune_delay_post_sub = suicune_live_sub_direct();\n            suicune_delay_post_phase = suicune_live_phase_direct(suicune_delay_post_div, suicune_delay_post_sub);\n            suicune_delay_post_valid = 1;\n            suicune_delay_pending = false;\n            suicune_delay_started = false;\n            suicune_delay_ready = true;''',
'capture post-delay phase')

# Bindings.
b = rep(b,
'''    pub fn host_suicune_delay_ready() -> u32;\n    pub fn host_early_control_enabled() -> u32;''',
'''    pub fn host_suicune_delay_ready() -> u32;\n    pub fn host_suicune_delay_pre_valid() -> u32;\n    pub fn host_suicune_delay_pre_div() -> u32;\n    pub fn host_suicune_delay_pre_sub() -> u32;\n    pub fn host_suicune_delay_pre_phase() -> u32;\n    pub fn host_suicune_delay_post_valid() -> u32;\n    pub fn host_suicune_delay_post_div() -> u32;\n    pub fn host_suicune_delay_post_sub() -> u32;\n    pub fn host_suicune_delay_post_phase() -> u32;\n    pub fn host_early_control_enabled() -> u32;''',
'add phase binding declarations')

b = rep(b,
'''    pub extern "C" fn host_suicune_delay_ready() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_control_enabled() -> u32 { 0 }''',
'''    pub extern "C" fn host_suicune_delay_ready() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_pre_valid() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_pre_div() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_pre_sub() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_pre_phase() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_post_valid() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_post_div() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_post_sub() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_post_phase() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_control_enabled() -> u32 { 0 }''',
'add phase binding stubs')

# Metrics wrapper.
i = rep(i,
'''    pub run_id: u32,\n    pub ready: bool,\n}\n\npub fn suicune_delay_metrics() -> SuicuneDelayMetrics {''',
'''    pub run_id: u32,\n    pub ready: bool,\n    pub pre_valid: bool,\n    pub pre_div: u8,\n    pub pre_sub: u8,\n    pub pre_phase: u16,\n    pub post_valid: bool,\n    pub post_div: u8,\n    pub post_sub: u8,\n    pub post_phase: u16,\n}\n\npub fn suicune_delay_metrics() -> SuicuneDelayMetrics {''',
'extend delay metrics struct')

i = rep(i,
'''        run_id: unsafe { bindings::host_suicune_delay_run_id() },\n        ready: unsafe { bindings::host_suicune_delay_ready() } != 0,\n    }''',
'''        run_id: unsafe { bindings::host_suicune_delay_run_id() },\n        ready: unsafe { bindings::host_suicune_delay_ready() } != 0,\n        pre_valid: unsafe { bindings::host_suicune_delay_pre_valid() } != 0,\n        pre_div: unsafe { bindings::host_suicune_delay_pre_div() } as u8,\n        pre_sub: unsafe { bindings::host_suicune_delay_pre_sub() } as u8,\n        pre_phase: unsafe { bindings::host_suicune_delay_pre_phase() } as u16,\n        post_valid: unsafe { bindings::host_suicune_delay_post_valid() } != 0,\n        post_div: unsafe { bindings::host_suicune_delay_post_div() } as u8,\n        post_sub: unsafe { bindings::host_suicune_delay_post_sub() } as u8,\n        post_phase: unsafe { bindings::host_suicune_delay_post_phase() } as u16,\n    }''',
'populate phase metrics')

# CSV: one row contains the whole causal chain for this experiment.
t = rep(t,
'''        let _ = write!(line,\n            "actuator,version,profile,frames_requested,frames_executed,run_id,ready_at_save\\n"\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line,\n            "ACT,V61,{},{},{},{},{}\\n",\n            dm.profile_used, dm.frames_requested, dm.frames_executed, dm.run_id, dm.ready as u8\n        );''',
'''        let actuator_delta = if dm.pre_valid && dm.post_valid {\n            (dm.post_phase.wrapping_sub(dm.pre_phase) & 0x3fff) as u32\n        } else { 0xffffffff };\n        let _ = write!(line,\n            "actuator,version,profile,frames_requested,frames_executed,run_id,ready_at_save,pre_valid,pre_div,pre_sub,pre_phase,post_valid,post_div,post_sub,post_phase,phase_delta_m\\n"\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line,\n            "ACT,V61B,{},{},{},{},{},{},{:02X},{:02X},{:04X},{},{:02X},{:02X},{:04X},{}\\n",\n            dm.profile_used, dm.frames_requested, dm.frames_executed, dm.run_id, dm.ready as u8,\n            dm.pre_valid as u8, dm.pre_div, dm.pre_sub, dm.pre_phase,\n            dm.post_valid as u8, dm.post_div, dm.post_sub, dm.post_phase, actuator_delta\n        );''',
'expand ACT telemetry')

for old, new in [
    ('PLAN,V61,', 'PLAN,V61B,'),
    ('MAP,V61,', 'MAP,V61B,'),
    ('EARLY,V61,', 'EARLY,V61B,'),
    ('LIVE,V61,', 'LIVE,V61B,'),
]:
    if old not in t:
        raise SystemExit(f'missing marker {old}')
    t = t.replace(old, new)

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print('Applied Suicune Neutral Delay v6.1b causal telemetry')
