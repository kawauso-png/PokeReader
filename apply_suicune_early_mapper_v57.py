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
# Suicune Early Mapper v5.7
#
# v5.6 proved that the rel26 -> rel27 gate is a real actuator, but the same E
# slot can land on different stable J branches.  v5.7 adds the missing host
# timing telemetry around the gate and runs an automatic information-dense
# profile sequence:
#
#   A E08, B E09, C E08, D E09, E E07,
#   F E10, G E06, H E11, I E05, J E12
#
# The first four trials directly test same-slot branch reproducibility with the
# new telemetry.  Later trials expand outward without changing builds.
#
# Unlike v5.6, the sequence is consumed only when the 13th-rel26 gate request
# actually occurs.  A mistaken Y+X arm that is aborted before rel26 therefore
# does not skip a profile.
# -------------------------------------------------------------------------

m = rep(
    m,
    "static u32 suicune_early_profile_next = 0;\nstatic u32 suicune_early_slot_used = 0;",
    "static u32 suicune_early_profile_next = 0;\nstatic u32 suicune_early_profile_used = 0;\nstatic u32 suicune_early_slot_used = 0;\nstatic u64 suicune_early_request_tick = 0;\nstatic u64 suicune_early_loop_tick = 0;\nstatic u64 suicune_early_offset_tick = 0;\nstatic u32 suicune_early_wrap_count = 0;\nstatic bool suicune_early_capture_next_top = false;\nstatic u64 suicune_early_first_top_tick = 0;",
    "add mapper host telemetry state",
)

m = rep(
    m,
    '''static void suicune_early_lab_reset(void)
{
    static const u32 profile_slots[3] = {7, 8, 9};

    // Latch exactly one profile for this Y+X arm. Early control is always ON
    // in v5.6; there is no pause-screen UI state to keep in sync.
    suicune_early_control_enabled = true;
    suicune_early_phase_slot = profile_slots[suicune_early_profile_next % 3];
    suicune_early_profile_next = (suicune_early_profile_next + 1) % 3;
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_gate_pending = false;
    suicune_early_gate_requests = 0;
    suicune_early_anchor_tick = 0;
    suicune_early_target_tick = 0;
    suicune_early_actual_tick = 0;
}''',
    '''static void suicune_early_lab_reset(void)
{
    static const u32 profile_slots[10] = {8, 9, 8, 9, 7, 10, 6, 11, 5, 12};

    // Preview/latch the next profile, but do NOT consume it yet.  Consumption
    // happens only when the 13th-rel26 gate is actually requested.
    suicune_early_control_enabled = true;
    suicune_early_profile_used = suicune_early_profile_next % 10;
    suicune_early_phase_slot = profile_slots[suicune_early_profile_used];
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_gate_pending = false;
    suicune_early_gate_requests = 0;
    suicune_early_anchor_tick = 0;
    suicune_early_target_tick = 0;
    suicune_early_actual_tick = 0;
    suicune_early_request_tick = 0;
    suicune_early_loop_tick = 0;
    suicune_early_offset_tick = 0;
    suicune_early_wrap_count = 0;
    suicune_early_capture_next_top = false;
    suicune_early_first_top_tick = 0;
}''',
    "replace v56 profiles with v57 mapper sequence",
)

m = rep(
    m,
    '''void host_suicune_early_gate_request(void)
{
    suicune_early_gate_requests++;
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_anchor_tick = suicune_start_last_top_tick;
    suicune_early_target_tick = 0;
    suicune_early_actual_tick = 0;
    if (!suicune_early_control_enabled) return;
    suicune_early_gate_pending = true;
    is_paused = true;
}''',
    '''void host_suicune_early_gate_request(void)
{
    suicune_early_gate_requests++;
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_profile_used = suicune_early_profile_next % 10;
    suicune_early_request_tick = svcGetSystemTick();
    suicune_early_anchor_tick = suicune_start_last_top_tick;
    suicune_early_target_tick = 0;
    suicune_early_actual_tick = 0;
    suicune_early_first_top_tick = 0;
    suicune_early_capture_next_top = false;
    // Consume only a real gate.  The Rust detector guarantees one request per
    // trial, but retain the guard for diagnostic builds.
    if (suicune_early_gate_requests == 1)
        suicune_early_profile_next = (suicune_early_profile_next + 1) % 10;
    if (!suicune_early_control_enabled) return;
    suicune_early_gate_pending = true;
    is_paused = true;
}''',
    "consume mapper profile at real gate",
)

m = rep(
    m,
    '''u32 host_early_control_enabled(void) { return suicune_early_control_enabled ? 1 : 0; }
u32 host_early_phase_slot(void) { return suicune_early_phase_slot; }
u32 host_early_slot_used(void) { return suicune_early_slot_used; }
u32 host_early_gate_requests(void) { return suicune_early_gate_requests; }
u64 host_early_phase_period(void) { return SUICUNE_PHASE_PERIOD_TICKS; }
u64 host_early_phase_anchor(void) { return suicune_early_anchor_tick; }
u64 host_early_phase_target(void) { return suicune_early_target_tick; }
u64 host_early_phase_actual(void) { return suicune_early_actual_tick; }''',
    '''u32 host_early_control_enabled(void) { return suicune_early_control_enabled ? 1 : 0; }
u32 host_early_phase_slot(void) { return suicune_early_phase_slot; }
u32 host_early_profile_used(void) { return suicune_early_profile_used; }
u32 host_early_slot_used(void) { return suicune_early_slot_used; }
u32 host_early_gate_requests(void) { return suicune_early_gate_requests; }
u64 host_early_phase_period(void) { return SUICUNE_PHASE_PERIOD_TICKS; }
u64 host_early_phase_anchor(void) { return suicune_early_anchor_tick; }
u64 host_early_phase_target(void) { return suicune_early_target_tick; }
u64 host_early_phase_actual(void) { return suicune_early_actual_tick; }
u64 host_early_request_tick(void) { return suicune_early_request_tick; }
u64 host_early_loop_tick(void) { return suicune_early_loop_tick; }
u64 host_early_offset_tick(void) { return suicune_early_offset_tick; }
u32 host_early_wrap_count(void) { return suicune_early_wrap_count; }
u64 host_early_first_top_tick(void) { return suicune_early_first_top_tick; }''',
    "expose mapper host telemetry",
)

# Capture the first top hook after the Early gate resumes.  This gives us a
# host-side marker independent of the later rDIV-read timestamp.
m = rep(
    m,
    '''        suicune_start_last_top_tick = top_tick;
        if (suicune_obs_arm_tick != 0)''',
    '''        suicune_start_last_top_tick = top_tick;
        if (suicune_early_capture_next_top)
        {
            suicune_early_first_top_tick = top_tick;
            suicune_early_capture_next_top = false;
        }
        if (suicune_obs_arm_tick != 0)''',
    "capture first post-gate top hook",
)

m = rep(
    m,
    '''        if (suicune_early_gate_pending)
        {
            u64 now = svcGetSystemTick();
            u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_early_phase_slot) / SUICUNE_PHASE_SLOTS;
            u64 target = suicune_early_anchor_tick + offset;
            if (target <= now + 4096ULL)
            {
                u64 delta = (now + 4096ULL) - target;
                target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;
            }
            suicune_early_target_tick = target;
            while (svcGetSystemTick() < target) { }
            suicune_early_actual_tick = svcGetSystemTick();
            suicune_early_gate_pending = false;
            is_paused = false;
            break;
        }''',
    '''        if (suicune_early_gate_pending)
        {
            u64 now = svcGetSystemTick();
            u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_early_phase_slot) / SUICUNE_PHASE_SLOTS;
            u64 target = suicune_early_anchor_tick + offset;
            u32 wraps = 0;
            suicune_early_loop_tick = now;
            suicune_early_offset_tick = offset;
            if (target <= now + 4096ULL)
            {
                u64 delta = (now + 4096ULL) - target;
                wraps = (u32)(delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL);
                target += (u64)wraps * SUICUNE_PHASE_PERIOD_TICKS;
            }
            suicune_early_wrap_count = wraps;
            suicune_early_target_tick = target;
            while (svcGetSystemTick() < target) { }
            suicune_early_actual_tick = svcGetSystemTick();
            suicune_early_capture_next_top = true;
            suicune_early_gate_pending = false;
            is_paused = false;
            break;
        }''',
    "instrument early gate wait",
)

# -------------------------------------------------------------------------
# Rust bindings and metrics.
# -------------------------------------------------------------------------
b = rep(
    b,
    '''    pub fn host_early_phase_slot() -> u32;
    pub fn host_early_slot_used() -> u32;
    pub fn host_early_gate_requests() -> u32;
    pub fn host_early_phase_period() -> u64;
    pub fn host_early_phase_anchor() -> u64;
    pub fn host_early_phase_target() -> u64;
    pub fn host_early_phase_actual() -> u64;''',
    '''    pub fn host_early_phase_slot() -> u32;
    pub fn host_early_profile_used() -> u32;
    pub fn host_early_slot_used() -> u32;
    pub fn host_early_gate_requests() -> u32;
    pub fn host_early_phase_period() -> u64;
    pub fn host_early_phase_anchor() -> u64;
    pub fn host_early_phase_target() -> u64;
    pub fn host_early_phase_actual() -> u64;
    pub fn host_early_request_tick() -> u64;
    pub fn host_early_loop_tick() -> u64;
    pub fn host_early_offset_tick() -> u64;
    pub fn host_early_wrap_count() -> u32;
    pub fn host_early_first_top_tick() -> u64;''',
    "add mapper binding declarations",
)

b = rep(
    b,
    '''    pub extern "C" fn host_early_phase_slot() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_slot_used() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_gate_requests() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_period() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_anchor() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_target() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_actual() -> u64 { 0 }''',
    '''    pub extern "C" fn host_early_phase_slot() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_profile_used() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_slot_used() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_gate_requests() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_period() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_anchor() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_target() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_phase_actual() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_request_tick() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_loop_tick() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_offset_tick() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_wrap_count() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_first_top_tick() -> u64 { 0 }''',
    "add mapper binding stubs",
)

i = rep(
    i,
    '''pub struct EarlyControlMetrics {
    pub enabled: bool,
    pub selected_slot: u32,
    pub used_slot: u32,
    pub requests: u32,
    pub period: u64,
    pub anchor: u64,
    pub target: u64,
    pub actual: u64,
}''',
    '''pub struct EarlyControlMetrics {
    pub enabled: bool,
    pub selected_slot: u32,
    pub profile_used: u32,
    pub used_slot: u32,
    pub requests: u32,
    pub period: u64,
    pub anchor: u64,
    pub target: u64,
    pub actual: u64,
    pub request_tick: u64,
    pub loop_tick: u64,
    pub offset_tick: u64,
    pub wraps: u32,
    pub first_top_tick: u64,
}''',
    "extend EarlyControlMetrics",
)

i = rep(
    i,
    '''        selected_slot: unsafe { bindings::host_early_phase_slot() },
        used_slot: unsafe { bindings::host_early_slot_used() },
        requests: unsafe { bindings::host_early_gate_requests() },
        period: unsafe { bindings::host_early_phase_period() },
        anchor: unsafe { bindings::host_early_phase_anchor() },
        target: unsafe { bindings::host_early_phase_target() },
        actual: unsafe { bindings::host_early_phase_actual() },''',
    '''        selected_slot: unsafe { bindings::host_early_phase_slot() },
        profile_used: unsafe { bindings::host_early_profile_used() },
        used_slot: unsafe { bindings::host_early_slot_used() },
        requests: unsafe { bindings::host_early_gate_requests() },
        period: unsafe { bindings::host_early_phase_period() },
        anchor: unsafe { bindings::host_early_phase_anchor() },
        target: unsafe { bindings::host_early_phase_target() },
        actual: unsafe { bindings::host_early_phase_actual() },
        request_tick: unsafe { bindings::host_early_request_tick() },
        loop_tick: unsafe { bindings::host_early_loop_tick() },
        offset_tick: unsafe { bindings::host_early_offset_tick() },
        wraps: unsafe { bindings::host_early_wrap_count() },
        first_top_tick: unsafe { bindings::host_early_first_top_tick() },''',
    "read mapper metrics",
)

# v5.6 has two identical slot->profile matches: one in CSV save and one in the
# on-screen status.  In v5.7 profile means sequence position, not E slot.
old_match = '''        let profile = match em.selected_slot {
            7 => "A",
            8 => "B",
            9 => "C",
            _ => "?",
        };'''
new_match = '''        let profile = match em.profile_used {
            0 => "A",
            1 => "B",
            2 => "C",
            3 => "D",
            4 => "E",
            5 => "F",
            6 => "G",
            7 => "H",
            8 => "I",
            9 => "J",
            _ => "?",
        };'''
if t.count(old_match) != 2:
    raise SystemExit(f"profile matches: expected 2, got {t.count(old_match)}")
t = t.replace(old_match, new_match)

# Add a dedicated high-value mapper row without breaking the established V56
# EARLY section.  pre/post atick come from the rDIV/VBlank trace points; the
# host fields come from the C gate itself.
needle = '''        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "early_lab,version,profile,enabled,selected_slot,used_slot,requests,repeat_count,gate_seen,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks,pre_valid,pre_advance,pre_state,pre_ap4,pre_sp4,pre_asub,pre_ssub,post1_valid,post1_advance,post1_state,post1_ap4,post1_sp4,j_a,j_s,post2_valid,post2_advance,post2_state,post2_ap4,post2_sp4,next_resid_a,next_resid_s\\n"'''
insert = '''        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let request_from_anchor = em.request_tick as i128 - em.anchor as i128;
        let loop_from_anchor = em.loop_tick as i128 - em.anchor as i128;
        let actual_to_first_top = em.first_top_tick as i128 - em.actual as i128;
        let actual_to_post1 = self.early_post1.atick as i128 - em.actual as i128;
        let _ = write!(line,
            "mapper,version,profile_index,profile,slot,request_tick,loop_tick,anchor_tick,request_from_anchor,loop_from_anchor,offset_tick,wraps,target_tick,actual_tick,error_ticks,wait_ticks,first_top_tick,actual_to_first_top,pre_atick,post1_atick,post2_atick,actual_to_post1,j_a,j_s,next_resid_a,next_resid_s,pre_ap4,pre_sp4,post1_ap4,post1_sp4\\n"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "MAP,V57,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X}\\n",
            em.profile_used, profile, em.used_slot, em.request_tick, em.loop_tick, em.anchor,
            request_from_anchor, loop_from_anchor, em.offset_tick, em.wraps, em.target, em.actual,
            eerr, em.actual.saturating_sub(em.loop_tick), em.first_top_tick, actual_to_first_top,
            self.early_pre.atick, self.early_post1.atick, self.early_post2.atick, actual_to_post1,
            self.early_j_a, self.early_j_s, self.early_next_a, self.early_next_s,
            self.early_pre.ap4, self.early_pre.sp4, self.early_post1.ap4, self.early_post1.sp4
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "early_lab,version,profile,enabled,selected_slot,used_slot,requests,repeat_count,gate_seen,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks,pre_valid,pre_advance,pre_state,pre_ap4,pre_sp4,pre_asub,pre_ssub,post1_valid,post1_advance,post1_state,post1_ap4,post1_sp4,j_a,j_s,post2_valid,post2_advance,post2_state,post2_ap4,post2_sp4,next_resid_a,next_resid_s\\n"'''
t = rep(t, needle, insert, "insert v57 mapper CSV")

# Keep the established EARLY row but mark this generated build as v5.7.
t = rep(t, '            "EARLY,V56,{},', '            "EARLY,V57,{},', "promote early row to v57")

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print("Applied Suicune Early Mapper v5.7")
