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
# Suicune Early Adaptive v5.8
#
# Calibration from v5.6 traces 0060-0066 shows a clean split by the parity of
# the 13th-rel26 A-side DIV byte:
#   odd  DIV: E08 is the observed near-zero-J choice
#   even DIV: E09 is the observed closest-to-zero choice
# v5.8 therefore chooses E only after Rust has sampled that exact rel26 point.
# It preserves all v5.7 host telemetry so the rule can be validated/falsified
# immediately instead of becoming a black box.
# -------------------------------------------------------------------------

m = rep(
    m,
    "static u64 suicune_early_first_top_tick = 0;",
    "static u64 suicune_early_first_top_tick = 0;\nstatic u32 suicune_early_pre_ap4_input = 0;\nstatic u32 suicune_early_pre_div_parity = 0;",
    "add adaptive inputs",
)

m = rep(
    m,
    '''    suicune_early_first_top_tick = 0;
}''',
    '''    suicune_early_first_top_tick = 0;
    suicune_early_pre_ap4_input = 0;
    suicune_early_pre_div_parity = 0;
}''',
    "reset adaptive inputs",
)

m = rep(
    m,
    '''void host_suicune_early_gate_request(void)
{
    suicune_early_gate_requests++;
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_profile_used = suicune_early_profile_next % 10;
    suicune_early_request_tick = svcGetSystemTick();''',
    '''void host_suicune_early_gate_request(u32 pre_ap4)
{
    suicune_early_gate_requests++;
    suicune_early_pre_ap4_input = pre_ap4 & 0x3fff;
    suicune_early_pre_div_parity = (suicune_early_pre_ap4_input >> 6) & 1;
    // Closed-loop rule from 0060-0066: odd DIV -> E08, even DIV -> E09.
    suicune_early_phase_slot = suicune_early_pre_div_parity ? 8 : 9;
    suicune_early_slot_used = suicune_early_phase_slot;
    // A = even/E09, B = odd/E08.  v5.7's wider profile sequence is bypassed
    // in adaptive mode but its telemetry plumbing is retained.
    suicune_early_profile_used = suicune_early_pre_div_parity ? 1 : 0;
    suicune_early_request_tick = svcGetSystemTick();''',
    "choose E from rel26 DIV parity",
)

# Adaptive mode must not advance the old v5.7 mapper sequence.
m = rep(
    m,
    '''    // Consume only a real gate.  The Rust detector guarantees one request per
    // trial, but retain the guard for diagnostic builds.
    if (suicune_early_gate_requests == 1)
        suicune_early_profile_next = (suicune_early_profile_next + 1) % 10;
    if (!suicune_early_control_enabled) return;''',
    '''    // v5.8 adaptive mode does not consume the v5.7 sweep sequence.
    if (!suicune_early_control_enabled) return;''',
    "disable mapper sequence consumption",
)

m = rep(
    m,
    '''u64 host_early_first_top_tick(void) { return suicune_early_first_top_tick; }''',
    '''u64 host_early_first_top_tick(void) { return suicune_early_first_top_tick; }
u32 host_early_pre_ap4_input(void) { return suicune_early_pre_ap4_input; }
u32 host_early_pre_div_parity(void) { return suicune_early_pre_div_parity; }''',
    "expose adaptive choice inputs",
)

b = rep(
    b,
    '''    pub fn host_suicune_early_gate_request();''',
    '''    pub fn host_suicune_early_gate_request(pre_ap4: u32);''',
    "adaptive request binding signature",
)

b = rep(
    b,
    '''    pub fn host_early_first_top_tick() -> u64;''',
    '''    pub fn host_early_first_top_tick() -> u64;
    pub fn host_early_pre_ap4_input() -> u32;
    pub fn host_early_pre_div_parity() -> u32;''',
    "adaptive metric declarations",
)

b = rep(
    b,
    '''    pub extern "C" fn host_suicune_early_gate_request() {}''',
    '''    pub extern "C" fn host_suicune_early_gate_request(_pre_ap4: u32) {}''',
    "adaptive request stub signature",
)

b = rep(
    b,
    '''    pub extern "C" fn host_early_first_top_tick() -> u64 { 0 }''',
    '''    pub extern "C" fn host_early_first_top_tick() -> u64 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_pre_ap4_input() -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_early_pre_div_parity() -> u32 { 0 }''',
    "adaptive metric stubs",
)

i = rep(
    i,
    '''    pub first_top_tick: u64,
}''',
    '''    pub first_top_tick: u64,
    pub pre_ap4_input: u32,
    pub pre_div_parity: u32,
}''',
    "extend adaptive metrics",
)

i = rep(
    i,
    '''pub fn request_suicune_early_gate() {
    unsafe { bindings::host_suicune_early_gate_request() }
}''',
    '''pub fn request_suicune_early_gate(pre_ap4: u16) {
    unsafe { bindings::host_suicune_early_gate_request(pre_ap4 as u32) }
}''',
    "pass pre AP4 into host gate",
)

i = rep(
    i,
    '''        first_top_tick: unsafe { bindings::host_early_first_top_tick() },
    }''',
    '''        first_top_tick: unsafe { bindings::host_early_first_top_tick() },
        pre_ap4_input: unsafe { bindings::host_early_pre_ap4_input() },
        pre_div_parity: unsafe { bindings::host_early_pre_div_parity() },
    }''',
    "read adaptive metrics",
)

# The detector already snapshots early_pre before requesting the gate.
t = rep(
    t,
    '''                    self.early_pre = early_point(e);
                    pnp::request_suicune_early_gate();''',
    '''                    self.early_pre = early_point(e);
                    pnp::request_suicune_early_gate(self.early_pre.ap4);''',
    "pass 13th-rel26 AP4",
)

# In adaptive mode profile A/B describe parity policy, not the old mapper index.
old_match = '''        let profile = match em.profile_used {
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
new_match = '''        let profile = match em.pre_div_parity {
            0 => "EVEN",
            1 => "ODD",
            _ => "?",
        };'''
if t.count(old_match) != 2:
    raise SystemExit(f"adaptive profile matches: expected 2, got {t.count(old_match)}")
t = t.replace(old_match, new_match)

# Add an explicit adaptive decision row immediately before the mapper timing row.
needle = '''        let request_from_anchor = em.request_tick as i128 - em.anchor as i128;
        let loop_from_anchor = em.loop_tick as i128 - em.anchor as i128;'''
insert = '''        let _ = write!(line,
            "adaptive,version,pre_ap4,pre_div,parity,chosen_slot,policy\\nADAPT,V58,{:04X},{:02X},{},{},{}\\n",
            em.pre_ap4_input, (em.pre_ap4_input >> 6) & 0xff, em.pre_div_parity,
            em.used_slot, profile
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let request_from_anchor = em.request_tick as i128 - em.anchor as i128;
        let loop_from_anchor = em.loop_tick as i128 - em.anchor as i128;'''
t = rep(t, needle, insert, "insert adaptive decision CSV")

t = rep(t, '            "MAP,V57,', '            "MAP,V58,', "promote mapper row to v58")
t = rep(t, '            "EARLY,V57,{},', '            "EARLY,V58,{},', "promote early row to v58")

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print("Applied Suicune Early Adaptive v5.8")
