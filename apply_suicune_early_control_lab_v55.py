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
# C host: one-frame-away control point for the rel26 -> rel27 transition.
# The 13th repeated rel26 is detected by Rust while run_frame() is executing on
# the top-screen hook. The request freezes before the following frame. Because
# the anchor is that very top hook, E-slot timing only extrapolates by <= 1
# display period instead of the tens/hundreds of periods used by v5.0 START.
# -------------------------------------------------------------------------
m = rep(
    m,
    '''static u64 suicune_start_phase_actual_tick = 0;\n\nu32 host_start_phase_slot(void) { return suicune_start_phase_slot; }''',
    '''static u64 suicune_start_phase_actual_tick = 0;\n\n// Suicune Early Control Lab v5.5. E controls the single critical transition\n// immediately after the 13th repeated rel26. OFF leaves the transition natural\n// but still logs it, so baseline and controlled trials use the same build.\nstatic bool suicune_early_control_enabled = true;\nstatic u32 suicune_early_phase_slot = 0;\nstatic u32 suicune_early_slot_used = 0;\nstatic bool suicune_early_gate_pending = false;\nstatic u32 suicune_early_gate_requests = 0;\nstatic u64 suicune_early_anchor_tick = 0;\nstatic u64 suicune_early_target_tick = 0;\nstatic u64 suicune_early_actual_tick = 0;\n\nstatic void suicune_early_lab_reset(void)\n{\n    suicune_early_slot_used = suicune_early_phase_slot;\n    suicune_early_gate_pending = false;\n    suicune_early_gate_requests = 0;\n    suicune_early_anchor_tick = 0;\n    suicune_early_target_tick = 0;\n    suicune_early_actual_tick = 0;\n}\n\nvoid host_suicune_early_gate_request(void)\n{\n    suicune_early_gate_requests++;\n    suicune_early_slot_used = suicune_early_phase_slot;\n    suicune_early_anchor_tick = suicune_start_last_top_tick;\n    suicune_early_target_tick = 0;\n    suicune_early_actual_tick = 0;\n    if (!suicune_early_control_enabled) return;\n    suicune_early_gate_pending = true;\n    is_paused = true;\n}\n\nu32 host_early_control_enabled(void) { return suicune_early_control_enabled ? 1 : 0; }\nu32 host_early_phase_slot(void) { return suicune_early_phase_slot; }\nu32 host_early_slot_used(void) { return suicune_early_slot_used; }\nu32 host_early_gate_requests(void) { return suicune_early_gate_requests; }\nu64 host_early_phase_period(void) { return SUICUNE_PHASE_PERIOD_TICKS; }\nu64 host_early_phase_anchor(void) { return suicune_early_anchor_tick; }\nu64 host_early_phase_target(void) { return suicune_early_target_tick; }\nu64 host_early_phase_actual(void) { return suicune_early_actual_tick; }\n\nu32 host_start_phase_slot(void) { return suicune_start_phase_slot; }''',
    "add early lab state",
)

# Reset per-trial metrics at the same Y+X/UP arm point used by the clean timing
# observer. Keep the selected E slot and ON/OFF state persistent across trials.
m = rep(
    m,
    '''                    suicune_observe_reset();\n                    suicune_obs_arm_tick = svcGetSystemTick();''',
    '''                    suicune_observe_reset();\n                    suicune_early_lab_reset();\n                    suicune_obs_arm_tick = svcGetSystemTick();''',
    "reset early metrics on arm",
)

# Repurpose the old START slot controls. START and Resume stay at S00/P00 so E
# is the only deliberate variable. Y+Up toggles Early control ON/OFF.
m = rep(
    m,
    '''            // v5.0 START phase selector: left/right = +/-1, down = opposite half-cycle.\n            // Resume remains P00 so only one causal variable is changed.\n            suicune_phase_slot = 0;\n            if (just_pressed & KEY_DRIGHT)\n                suicune_start_phase_slot = (suicune_start_phase_slot + 1) & 0x0f;\n            if (just_pressed & KEY_DLEFT)\n                suicune_start_phase_slot = (suicune_start_phase_slot + 15) & 0x0f;\n            if (just_pressed & KEY_DDOWN)\n                suicune_start_phase_slot ^= 8;''',
    '''            // v5.5 selector: S00/P00 are fixed; D-pad controls only the\n            // rel26->27 Early gate. Right/Left +/-1, Down opposite half-cycle,\n            // Up toggles Early control ON/OFF for a natural baseline trial.\n            suicune_phase_slot = 0;\n            suicune_start_phase_slot = 0;\n            if (just_pressed & KEY_DRIGHT)\n                suicune_early_phase_slot = (suicune_early_phase_slot + 1) & 0x0f;\n            if (just_pressed & KEY_DLEFT)\n                suicune_early_phase_slot = (suicune_early_phase_slot + 15) & 0x0f;\n            if (just_pressed & KEY_DDOWN)\n                suicune_early_phase_slot ^= 8;\n            if (just_pressed & KEY_DUP)\n                suicune_early_control_enabled = !suicune_early_control_enabled;''',
    "repurpose selector to early slot",
)

# When Rust detects the 13th rel26, the next bottom-screen hook enters here.
# Resume at E-slot relative to the immediately preceding top hook. This is a
# single-period correction, minimizing period-drift error.
m = rep(
    m,
    '''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        // Y+L schedules a fixed run,''',
    '''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if (suicune_early_gate_pending)\n        {\n            u64 now = svcGetSystemTick();\n            u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_early_phase_slot) / SUICUNE_PHASE_SLOTS;\n            u64 target = suicune_early_anchor_tick + offset;\n            if (target <= now + 4096ULL)\n            {\n                u64 delta = (now + 4096ULL) - target;\n                target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;\n            }\n            suicune_early_target_tick = target;\n            while (svcGetSystemTick() < target) { }\n            suicune_early_actual_tick = svcGetSystemTick();\n            suicune_early_gate_pending = false;\n            is_paused = false;\n            break;\n        }\n\n        // Y+L schedules a fixed run,''',
    "add early gate resume path",
)

# -------------------------------------------------------------------------
# Rust bindings / pnp wrapper.
# -------------------------------------------------------------------------
b = rep(
    b,
    '''    pub fn host_request_pause();\n    pub fn host_trace_last_error() -> u32;''',
    '''    pub fn host_request_pause();\n    pub fn host_suicune_early_gate_request();\n    pub fn host_early_control_enabled() -> u32;\n    pub fn host_early_phase_slot() -> u32;\n    pub fn host_early_slot_used() -> u32;\n    pub fn host_early_gate_requests() -> u32;\n    pub fn host_early_phase_period() -> u64;\n    pub fn host_early_phase_anchor() -> u64;\n    pub fn host_early_phase_target() -> u64;\n    pub fn host_early_phase_actual() -> u64;\n    pub fn host_trace_last_error() -> u32;''',
    "add early bindings",
)

b = rep(
    b,
    '''    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_trace_last_error() -> u32 {''',
    '''    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_suicune_early_gate_request() {}\n    #[no_mangle]\n    pub extern "C" fn host_early_control_enabled() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_phase_slot() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_slot_used() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_gate_requests() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_phase_period() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_phase_anchor() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_phase_target() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_early_phase_actual() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_trace_last_error() -> u32 {''',
    "add early binding stubs",
)

i += '''\n\n/// Suicune Early Control Lab v5.5 metrics.\npub struct EarlyControlMetrics {\n    pub enabled: bool,\n    pub selected_slot: u32,\n    pub used_slot: u32,\n    pub requests: u32,\n    pub period: u64,\n    pub anchor: u64,\n    pub target: u64,\n    pub actual: u64,\n}\n\npub fn request_suicune_early_gate() {\n    unsafe { bindings::host_suicune_early_gate_request() }\n}\n\npub fn early_control_metrics() -> EarlyControlMetrics {\n    EarlyControlMetrics {\n        enabled: unsafe { bindings::host_early_control_enabled() } != 0,\n        selected_slot: unsafe { bindings::host_early_phase_slot() },\n        used_slot: unsafe { bindings::host_early_slot_used() },\n        requests: unsafe { bindings::host_early_gate_requests() },\n        period: unsafe { bindings::host_early_phase_period() },\n        anchor: unsafe { bindings::host_early_phase_anchor() },\n        target: unsafe { bindings::host_early_phase_target() },\n        actual: unsafe { bindings::host_early_phase_actual() },\n    }\n}\n'''

# -------------------------------------------------------------------------
# Trace-side detector and compact snapshots.
# -------------------------------------------------------------------------
t = rep(
    t,
    '''fn direct_phase_m(div: u8, subtick: u8) -> u16 {\n    (((div as u16) << 6) | subtick as u16) & 0x3fff\n}\n''',
    '''fn direct_phase_m(div: u8, subtick: u8) -> u16 {\n    (((div as u16) << 6) | subtick as u16) & 0x3fff\n}\n\nfn phase_step_m(from: u16, to: u16) -> i32 {\n    (to.wrapping_sub(from) & 0x3fff) as i32\n}\n\n#[derive(Clone, Copy, Default)]\nstruct EarlyLabPoint {\n    valid: u8,\n    advance: u32,\n    state: u16,\n    ap4: u16,\n    sp4: u16,\n    asub: u8,\n    ssub: u8,\n    atick: u64,\n    stick: u64,\n}\n\nfn early_point(e: TraceEntry) -> EarlyLabPoint {\n    EarlyLabPoint {\n        valid: 1,\n        advance: e.advance,\n        state: e.state,\n        ap4: direct_phase_m((e.div >> 8) as u8, e.asub),\n        sp4: direct_phase_m(e.div as u8, e.ssub),\n        asub: e.asub,\n        ssub: e.ssub,\n        atick: e.atick,\n        stick: e.stick,\n    }\n}\n''',
    "add early point helpers",
)

t = rep(
    t,
    '''    probe_result: Option<ProbeResult>,\n    /// Row shown first in the on screen table.''',
    '''    probe_result: Option<ProbeResult>,\n    // v5.5 Early Control Lab. These are reset only when Y+X arms a fresh\n    // Suicune probe; start() calls reset() again and must not erase them.\n    early_rel26_count: u8,\n    early_gate_seen: bool,\n    early_pre: EarlyLabPoint,\n    early_post1: EarlyLabPoint,\n    early_post2: EarlyLabPoint,\n    early_j_a: i32,\n    early_j_s: i32,\n    early_next_a: i32,\n    early_next_s: i32,\n    /// Row shown first in the on screen table.''',
    "add early trace fields",
)

t = rep(
    t,
    '''            probe_result: None,\n            cursor: 0,''',
    '''            probe_result: None,\n            early_rel26_count: 0,\n            early_gate_seen: false,\n            early_pre: EarlyLabPoint::default(),\n            early_post1: EarlyLabPoint::default(),\n            early_post2: EarlyLabPoint::default(),\n            early_j_a: 0,\n            early_j_s: 0,\n            early_next_a: 0,\n            early_next_s: 0,\n            cursor: 0,''',
    "init early trace fields",
)

# Fresh trial reset immediately after the existing Y+X bookkeeping. Do not put
# this in reset(), because start() invokes reset() again on the first live frame.
t = rep(
    t,
    '''        self.last_run_id = pnp::fixed_run_id();\n        deep_log_clear();''',
    '''        self.last_run_id = pnp::fixed_run_id();\n        deep_log_clear();\n        self.early_rel26_count = 0;\n        self.early_gate_seen = false;\n        self.early_pre = EarlyLabPoint::default();\n        self.early_post1 = EarlyLabPoint::default();\n        self.early_post2 = EarlyLabPoint::default();\n        self.early_j_a = 0;\n        self.early_j_s = 0;\n        self.early_next_a = 0;\n        self.early_next_s = 0;''',
    "reset early trial on YX",
)

# Detect 13 copies of rel26. The request is made after the 13th rel26 entry has
# been sampled, so the C host freezes before the following critical transition.
t = rep(
    t,
    '''        self.len += 1;\n\n        if self.probe_active && window[2] == SUICUNE_SPECIES {''',
    '''        if self.probe_active && self.probe_session {\n            let e = self.entries[self.len];\n            let rel = e.advance.wrapping_sub(self.start_advance);\n\n            if !self.early_gate_seen && rel == 26 {\n                self.early_rel26_count = self.early_rel26_count.saturating_add(1);\n                if self.early_rel26_count == 13 {\n                    self.early_gate_seen = true;\n                    self.early_pre = early_point(e);\n                    pnp::request_suicune_early_gate();\n                }\n            } else if self.early_gate_seen && self.early_post1.valid == 0\n                && e.advance != self.early_pre.advance\n            {\n                self.early_post1 = early_point(e);\n                self.early_j_a = phase_step_m(self.early_pre.ap4, self.early_post1.ap4) - 1172;\n                self.early_j_s = phase_step_m(self.early_pre.sp4, self.early_post1.sp4) - 1172;\n            } else if self.early_post1.valid != 0 && self.early_post2.valid == 0\n                && e.advance != self.early_post1.advance\n            {\n                self.early_post2 = early_point(e);\n                self.early_next_a = phase_step_m(self.early_post1.ap4, self.early_post2.ap4) - 1172;\n                self.early_next_s = phase_step_m(self.early_post1.sp4, self.early_post2.sp4) - 1172;\n            }\n        }\n\n        self.len += 1;\n\n        if self.probe_active && window[2] == SUICUNE_SPECIES {''',
    "detect rel26 gate and post transitions",
)

# Save one compact lab row before the full frame section. This gives all control
# and outcome values in one place while preserving every existing CSV section.
t = rep(
    t,
    '''        let _ = write!(\n            line,\n            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"\n        );''',
    '''        let em = pnp::early_control_metrics();\n        line.clear();\n        let eerr = em.actual as i128 - em.target as i128;\n        let _ = write!(line,\n            "early_lab,version,enabled,selected_slot,used_slot,requests,repeat_count,gate_seen,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks,pre_valid,pre_advance,pre_state,pre_ap4,pre_sp4,pre_asub,pre_ssub,post1_valid,post1_advance,post1_state,post1_ap4,post1_sp4,j_a,j_s,post2_valid,post2_advance,post2_state,post2_ap4,post2_sp4,next_resid_a,next_resid_s\\n"\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line,\n            "EARLY,V55,{},{},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:02X},{:02X},{},{},{:04X},{:04X},{:04X},{},{},{},{},{:04X},{:04X},{:04X},{},{}\\n\\n",\n            em.enabled as u8, em.selected_slot, em.used_slot, em.requests,\n            self.early_rel26_count, self.early_gate_seen as u8, em.period, em.anchor,\n            em.target, em.actual, eerr, self.early_pre.valid, self.early_pre.advance,\n            self.early_pre.state, self.early_pre.ap4, self.early_pre.sp4,\n            self.early_pre.asub, self.early_pre.ssub, self.early_post1.valid,\n            self.early_post1.advance, self.early_post1.state, self.early_post1.ap4,\n            self.early_post1.sp4, self.early_j_a, self.early_j_s,\n            self.early_post2.valid, self.early_post2.advance, self.early_post2.state,\n            self.early_post2.ap4, self.early_post2.sp4, self.early_next_a, self.early_next_s\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n\n        let _ = write!(\n            line,\n            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"\n        );''',
    "write early lab csv section",
)

# On-screen selector/diagnostic. Existing Fix line remains unchanged so the
# user can still verify S00/P00; this second line is the only new operation UI.
t = rep(
    t,
    '''        if self.probe_active {\n            let mode = if self.state == TraceState::Armed { "ARM" } else { "REC" };''',
    '''        let em = pnp::early_control_metrics();\n        pnp::println!(\n            "Lab E{:02} {} C{} G{}",\n            em.selected_slot,\n            if em.enabled { "ON" } else { "OFF" },\n            self.early_rel26_count,\n            self.early_gate_seen as u8\n        );\n\n        if self.probe_active {\n            let mode = if self.state == TraceState::Armed { "ARM" } else { "REC" };''',
    "draw early lab status",
)

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print("Applied Suicune Early Control Lab v5.5")
