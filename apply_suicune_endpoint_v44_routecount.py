#!/usr/bin/env python3
from pathlib import Path

hook_path = Path("reader_core/src/crystal/hook.rs")
trace_path = Path("reader_core/src/crystal/trace.rs")
h = hook_path.read_text()
t = trace_path.read_text()


def replace_once(src: str, old: str, new: str, label: str) -> str:
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return src.replace(old, new, 1)


h = replace_once(
    h,
    "static mut ENDPOINT_FAST_TAIL: bool = false;",
    """static mut ENDPOINT_FAST_TAIL: bool = false;
static mut ENDPOINT_FAST_CALLS: u8 = 0;""",
    "add fast call counter",
)

h = replace_once(
    h,
    """pub fn endpoint_fast_tail_start() {
    unsafe { ENDPOINT_FAST_TAIL = true };
}

pub fn endpoint_fast_tail_stop() {""",
    """pub fn endpoint_fast_tail_start() {
    unsafe {
        ENDPOINT_FAST_CALLS = 0;
        ENDPOINT_FAST_TAIL = true;
    }
}

pub fn endpoint_fast_tail_calls() -> u8 {
    unsafe { ENDPOINT_FAST_CALLS }
}

pub fn endpoint_fast_tail_stop() {""",
    "reset/expose fast call counter",
)

h = replace_once(
    h,
    """    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        return;
    }""",
    """    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        // Count only Random's first rDIV read.  No DIV/state/tick/mcycle reads
        // are performed in PURETAIL mode; this single host byte increment is
        // retained solely to distinguish the 3-call and 4-call item branch.
        if pc == 0x2f60 {
            unsafe { ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1) };
        }
        return;
    }""",
    "count Random calls in fast path",
)

hook_path.write_text(h)


t = replace_once(
    t,
    """    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, endpoint_fast_tail_start,
    endpoint_fast_tail_stop, measured_div, rng_advance, sdiv_cycles, sdiv_subtick, sdiv_tick,
    sub_div_tracker,""",
    """    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, endpoint_fast_tail_calls,
    endpoint_fast_tail_start, endpoint_fast_tail_stop, measured_div, rng_advance, sdiv_cycles,
    sdiv_subtick, sdiv_tick, sub_div_tracker,""",
    "import fast call count",
)

# The v4.4 fallback result used route=0 because no tail calls were logged.
# Replace only that calibration placeholder with the minimally observed count.
t = replace_once(
    t,
    "                    route: 0,",
    "                    route: endpoint_fast_tail_calls(),",
    "store PURETAIL route count",
)

trace_path.write_text(t)
print("Applied Suicune Endpoint v4.4 PURETAIL route counter")
