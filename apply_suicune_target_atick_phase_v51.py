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

# C host: accept the exact Target VBlank-A host tick captured by Rust while
# the game is frozen.  This is a more direct phase origin than the last screen
# present hook and matches the historical feature (arm_tick - target_atick).
m = rep(
    m,
    '''static u64 suicune_start_phase_actual_tick = 0;\n\nu32 host_start_phase_slot(void) { return suicune_start_phase_slot; }''',
    '''static u64 suicune_start_phase_actual_tick = 0;\nstatic u64 suicune_target_atick_anchor = 0;\n\nvoid host_set_suicune_target_atick(u64 tick)\n{\n    suicune_target_atick_anchor = tick;\n}\n\nu32 host_start_phase_slot(void) { return suicune_start_phase_slot; }''',
    "add target atick setter",
)

m = rep(
    m,
    '''                    suicune_start_phase_anchor_tick = suicune_start_last_top_tick;''',
    '''                    // v5.1: phase origin is the Target VBlank-A rDIV host tick.\n                    // The top-screen hook is retained only as a diagnostic/fallback.\n                    suicune_start_phase_anchor_tick = suicune_target_atick_anchor != 0\n                        ? suicune_target_atick_anchor\n                        : suicune_start_last_top_tick;''',
    "use target atick anchor",
)

# Rust FFI binding to the host setter.
b = rep(
    b,
    '''    pub fn host_start_phase_slot() -> u32;''',
    '''    pub fn host_set_suicune_target_atick(tick: u64);\n    pub fn host_start_phase_slot() -> u32;''',
    "declare target atick setter",
)

# Add a test stub adjacent to the v5.0 start metrics stubs.
b = rep(
    b,
    '''    pub extern "C" fn host_start_phase_slot() -> u32 { 0 }''',
    '''    pub extern "C" fn host_set_suicune_target_atick(_tick: u64) {}\n    #[no_mangle]\n    pub extern "C" fn host_start_phase_slot() -> u32 { 0 }''',
    "stub target atick setter",
)

# Tiny safe wrapper.
i += '''\n\n/// v5.1: pass the frozen Target VBlank-A host tick to the C phase scheduler.\npub fn set_suicune_target_atick(tick: u64) {\n    unsafe { bindings::host_set_suicune_target_atick(tick) }\n}\n'''

# arm_suicune_probe already captures the exact target.atick while paused.
# Send it to C immediately, before the pause loop schedules Exact-2F.
t = rep(
    t,
    '''        self.probe_result = None;\n        self.probe_active = true;''',
    '''        pnp::set_suicune_target_atick(self.probe_target.atick);\n        self.probe_result = None;\n        self.probe_active = true;''',
    "publish target atick",
)

# Distinguish the saved phase row from the top-hook anchored v5.0 prototype.
t = rep(
    t,
    '''            "SPH,V50,{},{},{},{},{},{},{}\\n",''',
    '''            "SPH,V51,{},{},{},{},{},{},{}\\n",''',
    "version start phase row",
)

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print("Applied Suicune Target-ATICK Start Phase Lock v5.1")
