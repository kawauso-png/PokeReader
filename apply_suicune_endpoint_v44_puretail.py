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


# ---------------------------------------------------------------------------
# hook.rs: after the Endpoint DV-2 snapshot, Random's rDIV reads must be as
# close to uninstrumented as possible.  v4.2 removed Deep snapshots, but the
# lightweight CALL_LOG path still sampled host tick/mcycle/state/DIV on every
# 2F60/2F68 hook.  0033 showed that this remaining observer can move rDIV by
# tens of M-cycles inside a 4-call burst.  PURETAIL returns immediately for
# those Random PCs once the endpoint has been captured.
# ---------------------------------------------------------------------------
h = replace_once(
    h,
    """static mut CALL_WRITE: usize = 0;
static mut CALL_COUNT: u32 = 0;
static mut CALL_LOGGING: bool = false;

pub fn call_log_start() {""",
    """static mut CALL_WRITE: usize = 0;
static mut CALL_COUNT: u32 = 0;
static mut CALL_LOGGING: bool = false;
// Endpoint v4.4 PURETAIL.  When true, the two rDIV reads inside Random are
// allowed to execute with only the unavoidable hook entry + PC read.  All
// timing/state/logging work is skipped so the observer does not move rDIV.
static mut ENDPOINT_FAST_TAIL: bool = false;

pub fn endpoint_fast_tail_start() {
    unsafe { ENDPOINT_FAST_TAIL = true };
}

pub fn endpoint_fast_tail_stop() {
    unsafe { ENDPOINT_FAST_TAIL = false };
}

pub fn call_log_start() {""",
    "insert fast-tail state",
)

h = replace_once(
    h,
    """    let reader = Gen2Reader::crystal();
    let pc = reader.pc_reg();
    // Sample once and reuse the value for every record produced by this rDIV""",
    """    let reader = Gen2Reader::crystal();
    let pc = reader.pc_reg();
    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        return;
    }
    // Sample once and reuse the value for every record produced by this rDIV""",
    "fast-return Random hooks",
)

hook_path.write_text(h)

# ---------------------------------------------------------------------------
# trace.rs: stop CALL_LOG at DV-2, enable the hook fast path, and detect the
# real DV directly from wEnemyMon at the already-proven expected DV advance.
# Route is intentionally stored as 0 in this calibration build because no
# Random calls are observed after Endpoint.  raw_dv remains ground truth.
# ---------------------------------------------------------------------------
t = replace_once(
    t,
    """    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, measured_div, rng_advance,
    sdiv_cycles, sdiv_subtick, sdiv_tick, sub_div_tracker,""",
    """    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, endpoint_fast_tail_start,
    endpoint_fast_tail_stop, measured_div, rng_advance, sdiv_cycles, sdiv_subtick, sdiv_tick,
    sub_div_tracker,""",
    "import fast-tail controls",
)

# Clear a stale fast-tail mode whenever a new probe is armed.
t = replace_once(
    t,
    """        deep_log_clear();
        self.probe_target = ProbeTarget {""",
    """        deep_log_clear();
        endpoint_fast_tail_stop();
        self.probe_target = ProbeTarget {""",
    "clear fast-tail on Suicune arm",
)

# Legacy/manual trace arm should also never inherit PURETAIL mode.
t = replace_once(
    t,
    """        self.probe_result = None;
        deep_log_clear();
        self.state = TraceState::Armed;""",
    """        self.probe_result = None;
        deep_log_clear();
        endpoint_fast_tail_stop();
        self.state = TraceState::Armed;""",
    "clear fast-tail on normal arm",
)

# Explicit stop/abort restores normal hook behavior.
t = replace_once(
    t,
    """            call_log_stop();
            deep_log_stop();
            self.probe_active = false;
            self.state = TraceState::Done;""",
    """            call_log_stop();
            deep_log_stop();
            endpoint_fast_tail_stop();
            self.probe_active = false;
            self.state = TraceState::Done;""",
    "clear fast-tail on stop",
)

# v4.2 already stops Deep at the endpoint.  v4.4 also stops CALL_LOG and turns
# on the Random-PC immediate return before asking the host to pause.
t = replace_once(
    t,
    """                // Endpoint v4.2 LIGHTTAIL: keep the lightweight per-rDIV
                // CALL_LOG running, but remove Deep snapshot overhead from the
                // final two advances and the 3/4-call DV burst.
                deep_log_stop();
                pnp::request_pause();""",
    """                // Endpoint v4.4 PURETAIL: after the DV-2 snapshot no
                // Random-call timing instrumentation is allowed to influence
                // the hardware divider.  Frame/VBlank observation continues.
                deep_log_stop();
                call_log_stop();
                endpoint_fast_tail_start();
                pnp::request_pause();""",
    "activate pure tail at endpoint",
)

# Once CALL_LOG is intentionally stopped, the original result detector cannot
# count route3/route4.  At/after expected_dv_advance, wEnemyMon already holds
# the final two DV bytes, so use them directly as ground truth for calibration.
t = replace_once(
    t,
    """        if self.probe_active && window[2] == SUICUNE_SPECIES {
            if let Some(result) = self.detect_suicune_result(
                self.entries[self.len - 1].advance,
                window[8],
                window[9],
            ) {
                self.probe_result = Some(result);""",
    """        if self.probe_active && window[2] == SUICUNE_SPECIES {
            let observed_advance = self.entries[self.len - 1].advance;
            let result = if self.endpoint.capture_advance != 0
                && observed_advance >= self.endpoint.expected_dv_advance
            {
                Some(ProbeResult {
                    dv_advance: self.endpoint.expected_dv_advance,
                    offset: self
                        .endpoint
                        .expected_dv_advance
                        .wrapping_sub(self.probe_target.advance),
                    route: 0,
                    raw_dv: ((window[8] as u16) << 8) | window[9] as u16,
                    first_call_index: 0,
                    final_call_index: 0,
                    clean_tail: false,
                })
            } else {
                self.detect_suicune_result(observed_advance, window[8], window[9])
            };

            if let Some(result) = result {
                self.probe_result = Some(result);""",
    "fallback result from final DV memory",
)

# Restore normal hook behavior as soon as the real DV is locked.
t = replace_once(
    t,
    """                self.probe_active = false;
                call_log_stop();
                deep_log_stop();
                self.state = TraceState::Done;""",
    """                self.probe_active = false;
                call_log_stop();
                deep_log_stop();
                endpoint_fast_tail_stop();
                self.state = TraceState::Done;""",
    "restore hooks after DV lock",
)

# Identify the build on screen.  CSV endpoint format stays v4.1-compatible.
t = replace_once(
    t,
    '                "EP42 +{} S{:04X}",',
    '                "EP44 +{} S{:04X}",',
    "screen PURETAIL marker",
)

trace_path.write_text(t)
print("Applied Suicune Endpoint v4.4 PURETAIL")
