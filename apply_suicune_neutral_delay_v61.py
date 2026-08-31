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
# C host: neutral-frame actuator at the frozen Target.
#
# Y+B with NO UP held latches 0/1/2/3 neutral game frames. The plugin waits
# until every gameplay key is physically released, lets exactly N frames pass
# through the already-proven single-frame pause path, then remains paused.
# The normal UP-first -> Y+X -> Exact-2F path is left intact.
# -------------------------------------------------------------------------
m = rep(
    m,
    'static bool suicune_auto_resume_pending = false;\n',
    '''static bool suicune_auto_resume_pending = false;\n\n// Suicune Neutral Delay Actuator v6.1.\nstatic u32 suicune_delay_profile_next = 0;\nstatic u32 suicune_delay_profile_used = 0xffffffff;\nstatic u32 suicune_delay_frames_requested = 0;\nstatic u32 suicune_delay_frames_remaining = 0;\nstatic u32 suicune_delay_frames_executed = 0;\nstatic u32 suicune_delay_run_id = 0;\nstatic bool suicune_delay_pending = false;\nstatic bool suicune_delay_started = false;\nstatic bool suicune_delay_ready = false;\n\nu32 host_suicune_delay_profile_used(void) { return suicune_delay_profile_used; }\nu32 host_suicune_delay_frames_requested(void) { return suicune_delay_frames_requested; }\nu32 host_suicune_delay_frames_executed(void) { return suicune_delay_frames_executed; }\nu32 host_suicune_delay_run_id(void) { return suicune_delay_run_id; }\nu32 host_suicune_delay_ready(void) { return suicune_delay_ready ? 1 : 0; }\n''',
    'add neutral delay state',
)

# v6.0 showed E08/E09 wall-clock waits do not move emulated RNG phase. Keep the
# gate telemetry/capture, but force the old Early host-time actuator OFF.
m = rep(
    m,
    'static bool suicune_early_control_enabled = true;',
    'static bool suicune_early_control_enabled = false;',
    'disable early control initial',
)
# v5.7 reset re-enabled it on each arm; disable that too.
m = rep(
    m,
    '    suicune_early_control_enabled = true;\n',
    '    suicune_early_control_enabled = false;\n',
    'disable early control reset',
)

# Run neutral frames before any other paused-state actuator. Requiring ALL
# gameplay keys to be released guarantees the delay is input-neutral.
needle = '''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if (suicune_early_gate_pending)'''
insert = '''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if (suicune_delay_pending)\n        {\n            const u32 neutral_block_keys = KEY_A | KEY_B | KEY_X | KEY_Y |\n                KEY_DUP | KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT |\n                KEY_L | KEY_R | KEY_START | KEY_SELECT;\n\n            // Y+B and every other game input must be physically clear before\n            // the first neutral frame is permitted to pass.\n            if (held & neutral_block_keys)\n            {\n                svcSleepThread(1000000);\n                continue;\n            }\n\n            if (!suicune_delay_started)\n            {\n                suicune_delay_started = true;\n                suicune_delay_frames_remaining = suicune_delay_frames_requested;\n                suicune_delay_frames_executed = 0;\n            }\n\n            if (suicune_delay_frames_remaining > 0)\n            {\n                suicune_delay_frames_remaining--;\n                suicune_delay_frames_executed++;\n                // is_paused stays true: this is the same proven one-frame\n                // escape used by Exact-N fixed frames.\n                break;\n            }\n\n            // N frames are complete (including N=0). Stay frozen so the user\n            // can now perform the unchanged UP-first -> Y+X -> Exact-2F path.\n            suicune_delay_pending = false;\n            suicune_delay_started = false;\n            suicune_delay_ready = true;\n            continue;\n        }\n\n        if (suicune_early_gate_pending)'''
m = rep(m, needle, insert, 'insert neutral frame runner')

# Manual Y+B arm is obsolete in the Suicune one-action path. Reuse it for the
# neutral delay profile. Profile consumption happens only when UP+Y+X actually
# starts the encounter, so an accidental/repeated Y+B does not skip a profile.
m = rep(
    m,
    '''            if (just_pressed & KEY_B)\n            {\n                fixed_armed = !fixed_armed;\n            }''',
    '''            if (just_pressed & KEY_B)\n            {\n                if (!(held & KEY_DUP))\n                {\n                    suicune_delay_profile_used = suicune_delay_profile_next & 3;\n                    suicune_delay_frames_requested = suicune_delay_profile_used;\n                    suicune_delay_frames_remaining = 0;\n                    suicune_delay_frames_executed = 0;\n                    suicune_delay_pending = true;\n                    suicune_delay_started = false;\n                    suicune_delay_ready = false;\n                    suicune_delay_run_id++;\n                }\n            }''',
    'repurpose Y+B for neutral delay',
)

# Consume 0->1->2->3 only when the real UP+Y+X execution starts. If the user
# skips Y+B the encounter still works, but the CSV exposes profile=FFFFFFFF so
# such a trial cannot be mistaken for actuator data.
m = rep(
    m,
    '''                    suicune_observe_reset();\n                    suicune_early_lab_reset();''',
    '''                    if (suicune_delay_ready)\n                    {\n                        suicune_delay_profile_next = (suicune_delay_profile_used + 1) & 3;\n                        suicune_delay_ready = false;\n                    }\n                    suicune_observe_reset();\n                    suicune_early_lab_reset();''',
    'consume neutral profile on encounter arm',
)

# -------------------------------------------------------------------------
# Rust bindings/wrapper for CSV telemetry.
# -------------------------------------------------------------------------
b = rep(
    b,
    '''    pub fn host_early_control_enabled() -> u32;''',
    '''    pub fn host_suicune_delay_profile_used() -> u32;\n    pub fn host_suicune_delay_frames_requested() -> u32;\n    pub fn host_suicune_delay_frames_executed() -> u32;\n    pub fn host_suicune_delay_run_id() -> u32;\n    pub fn host_suicune_delay_ready() -> u32;\n    pub fn host_early_control_enabled() -> u32;''',
    'add delay binding declarations',
)
b = rep(
    b,
    '''    pub extern "C" fn host_early_control_enabled() -> u32 { 0 }''',
    '''    pub extern "C" fn host_suicune_delay_profile_used() -> u32 { 0xffffffff }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_frames_requested() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_frames_executed() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_run_id() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_ready() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_control_enabled() -> u32 { 0 }''',
    'add delay binding stubs',
)

i += '''\n\n/// Suicune v6.1 input-neutral pre-execution delay metrics.\npub struct SuicuneDelayMetrics {\n    pub profile_used: u32,\n    pub frames_requested: u32,\n    pub frames_executed: u32,\n    pub run_id: u32,\n    pub ready: bool,\n}\n\npub fn suicune_delay_metrics() -> SuicuneDelayMetrics {\n    SuicuneDelayMetrics {\n        profile_used: unsafe { bindings::host_suicune_delay_profile_used() },\n        frames_requested: unsafe { bindings::host_suicune_delay_frames_requested() },\n        frames_executed: unsafe { bindings::host_suicune_delay_frames_executed() },\n        run_id: unsafe { bindings::host_suicune_delay_run_id() },\n        ready: unsafe { bindings::host_suicune_delay_ready() } != 0,\n    }\n}\n'''

# -------------------------------------------------------------------------
# Robust live-gate detector.
# 0081 proved the 13-repeat plateau can be rel27 instead of rel26. Detect the
# same-state/same-advance 13-row plateau within the narrow early-event window.
# -------------------------------------------------------------------------
t = rep(
    t,
    '''    early_rel26_count: u8,\n    early_gate_seen: bool,''',
    '''    early_rel26_count: u8,\n    early_repeat_rel: u32,\n    early_repeat_state: u16,\n    early_gate_seen: bool,''',
    'add robust repeat fields',
)
t = rep(
    t,
    '''            early_rel26_count: 0,\n            early_gate_seen: false,''',
    '''            early_rel26_count: 0,\n            early_repeat_rel: 0xffffffff,\n            early_repeat_state: 0,\n            early_gate_seen: false,''',
    'init robust repeat fields',
)
t = rep(
    t,
    '''        self.early_rel26_count = 0;\n        self.early_gate_seen = false;''',
    '''        self.early_rel26_count = 0;\n        self.early_repeat_rel = 0xffffffff;\n        self.early_repeat_state = 0;\n        self.early_gate_seen = false;''',
    'reset robust repeat fields',
)

old_gate = '''            if !self.early_gate_seen && rel == 26 {\n                self.early_rel26_count = self.early_rel26_count.saturating_add(1);\n                if self.early_rel26_count == 13 {\n                    self.early_gate_seen = true;\n                    self.early_pre = early_point(e);\n                    // Unlike early_pre, these are sampled NOW at the 13th rel26.\n                    // reader.div() resolves the emulator rDIV backing byte via\n                    // direct host memory; no GB memory dispatcher is involved.\n                    self.early_live_valid = 1;\n                    self.early_live_div = reader.div();\n                    self.early_live_sub = pnp::read::<u8>(LIVE_MCYCLE_SUBTICK_ADDR);\n                    self.early_live_phase = direct_phase_m(self.early_live_div, self.early_live_sub);\n                    self.early_live_tick = pnp::system_tick();\n                    pnp::request_suicune_early_gate(self.early_pre.ap4);\n                }\n            } else if self.early_gate_seen && self.early_post1.valid == 0'''
new_gate = '''            if !self.early_gate_seen && rel >= 20 && rel <= 35 {\n                if self.early_rel26_count == 0\n                    || (self.early_repeat_rel == rel && self.early_repeat_state == e.state)\n                {\n                    if self.early_rel26_count == 0 {\n                        self.early_repeat_rel = rel;\n                        self.early_repeat_state = e.state;\n                    }\n                    self.early_rel26_count = self.early_rel26_count.saturating_add(1);\n                } else {\n                    self.early_repeat_rel = rel;\n                    self.early_repeat_state = e.state;\n                    self.early_rel26_count = 1;\n                }\n\n                if self.early_rel26_count == 13 {\n                    self.early_gate_seen = true;\n                    self.early_pre = early_point(e);\n                    // v6.1: exact live phase at whichever early plateau is\n                    // repeated 13 times (rel26 normally, rel27 on the shifted route).\n                    self.early_live_valid = 1;\n                    self.early_live_div = reader.div();\n                    self.early_live_sub = pnp::read::<u8>(LIVE_MCYCLE_SUBTICK_ADDR);\n                    self.early_live_phase = direct_phase_m(self.early_live_div, self.early_live_sub);\n                    self.early_live_tick = pnp::system_tick();\n                    // Keep the old request only for telemetry. C-side Early\n                    // control is forced OFF, so no host-wall-clock pause occurs.\n                    pnp::request_suicune_early_gate(self.early_pre.ap4);\n                }\n            } else if !self.early_gate_seen {\n                self.early_rel26_count = 0;\n                self.early_repeat_rel = 0xffffffff;\n            } else if self.early_gate_seen && self.early_post1.valid == 0'''
t = rep(t, old_gate, new_gate, 'robust 13-repeat live gate')

# Add actuator telemetry immediately before the LIVE section.
needle = '''        let stale_age = self.early_live_tick.saturating_sub(self.early_pre.atick);'''
insert = '''        let dm = pnp::suicune_delay_metrics();\n        let _ = write!(line,\n            "actuator,version,profile,frames_requested,frames_executed,run_id,ready_at_save\\n"\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line,\n            "ACT,V61,{},{},{},{},{}\\n",\n            dm.profile_used, dm.frames_requested, dm.frames_executed, dm.run_id, dm.ready as u8\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n\n        let stale_age = self.early_live_tick.saturating_sub(self.early_pre.atick);'''
t = rep(t, needle, insert, 'write v61 actuator row')

# Version all current compact rows as v6.1.
for old, new in [
    ('PLAN,V60,', 'PLAN,V61,'),
    ('MAP,V60,', 'MAP,V61,'),
    ('EARLY,V60,', 'EARLY,V61,'),
    ('LIVE,V60,', 'LIVE,V61,'),
]:
    if old not in t:
        raise SystemExit(f'missing version marker {old}')
    t = t.replace(old, new)

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print('Applied Suicune Neutral Delay Actuator v6.1')
