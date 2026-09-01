#!/usr/bin/env python3
from pathlib import Path

TRACE = Path('reader_core/src/crystal/trace.rs')


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)


def function_span(text, signature):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'function not found: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'function brace not found: {signature}')
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit(f'unclosed function: {signature}')


t = TRACE.read_text()

# ---------------------------------------------------------------------------
# v6.8.0: stop transporting a predicted RNG root through long WAIT periods.
# Instead, inspect each new *actual* advance exactly once and ask the already
# proven donor evaluator whether pressing UP+B from that root would be shiny.
# ---------------------------------------------------------------------------
t = replace_once(
    t,
    '    practical_roll_refresh_fail: u16,\n',
    '''    practical_roll_refresh_fail: u16,
    practical_live_scan: bool,
    practical_live_last_advance: u32,
    practical_live_start_advance: u32,
    practical_live_checked: u32,
    practical_live_lane_frames: u32,
    practical_live_no_lane: u32,
    practical_live_found_advance: u32,
    practical_live_found_state: u16,
    practical_live_found_div: u16,
    practical_live_found_lane: u8,
    practical_live_start_tick: u64,
    practical_live_found_tick: u64,
''',
    'live scan fields',
)
t = replace_once(
    t,
    '            practical_roll_refresh_fail: 0,\n',
    '''            practical_roll_refresh_fail: 0,
            practical_live_scan: false,
            practical_live_last_advance: u32::MAX,
            practical_live_start_advance: 0,
            practical_live_checked: 0,
            practical_live_lane_frames: 0,
            practical_live_no_lane: 0,
            practical_live_found_advance: 0,
            practical_live_found_state: 0,
            practical_live_found_div: 0,
            practical_live_found_lane: 0,
            practical_live_start_tick: 0,
            practical_live_found_tick: 0,
''',
    'live scan defaults',
)

# Y+DOWN no longer performs any future search. It only starts a safe live scan
# epoch and release-gated resume. Unsupported PRE roots are skipped rather than
# forcing E2, and there is no E3 because an empty 12k future window is irrelevant.
ss, se = function_span(t, '    pub fn search_practical_targets(&mut self, reader: &Gen2Reader)')
search_new = r'''    pub fn search_practical_targets(&mut self, _reader: &Gen2Reader) {
        self.practical_search_error = 0;
        self.practical_search_skipped = 0;
        self.practical_terminal_advance = 0;
        self.practical_search_count = 0;
        self.practical_search_index = 0;
        self.practical_search_from = rng_advance();
        self.practical_candidate_valid = false;
        self.practical_active = false;
        self.practical_miss = 0;
        self.practical_roll_next = 0;
        self.clear_transport_diag();

        self.practical_live_scan = true;
        self.practical_live_last_advance = u32::MAX;
        self.practical_live_start_advance = rng_advance();
        self.practical_live_checked = 0;
        self.practical_live_lane_frames = 0;
        self.practical_live_no_lane = 0;
        self.practical_live_found_advance = 0;
        self.practical_live_found_state = 0;
        self.practical_live_found_div = 0;
        self.practical_live_found_lane = 0;
        self.practical_live_start_tick = pnp::system_tick();
        self.practical_live_found_tick = 0;

        // Reuse the existing search-enabled display/runtime gate, but there is
        // deliberately no target queue in v6.8.0.
        self.practical_search_enabled = true;
        pnp::request_release_resume();
    }'''
t = t[:ss] + search_new + t[se:]

# The live monitor is intentionally tiny: one evaluation per actual RNG advance.
# No normal_step(), no future state/div prediction, no target revalidation and
# therefore no EVAL failure mode before READY.
ws, we = function_span(t, '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')
wait_new = r'''    fn practical_wait_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_search_enabled
            || !self.practical_live_scan
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        {
            return;
        }

        let current = rng_advance();
        if current == self.practical_live_last_advance {
            return;
        }
        self.practical_live_last_advance = current;
        self.practical_live_checked = self.practical_live_checked.saturating_add(1);

        let Some(lane_id) = self.live_practical_lane() else {
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        };
        self.practical_live_lane_frames = self.practical_live_lane_frames.saturating_add(1);

        let state = reader.rng_state();
        let div = measured_div();
        let Some(p) = practical::evaluate(lane_id, state, div) else {
            return;
        };

        // This root is real, not transported. Freeze immediately and hand the
        // exact root to the unchanged donor/branch-guard execution pipeline.
        self.practical_live_found_advance = current;
        self.practical_live_found_state = state;
        self.practical_live_found_div = div;
        self.practical_live_found_lane = lane_id;
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_scan = false;
        self.practical_search_enabled = false;
        self.clear_transport_diag();
        self.bind_practical_prediction(p);
        pnp::request_pause();
    }'''
t = t[:ws] + wait_new + t[we:]

# Reset-safe status cleanup must also disarm a stale scanner.
cs, ce = function_span(t, '    fn clear_stale_practical_status(&mut self)')
clear_block = t[cs:ce]
if 'self.practical_live_scan = false;' not in clear_block:
    clear_block = replace_once(
        clear_block,
        '        self.practical_roll_next = 0;\n',
        '''        self.practical_roll_next = 0;
        self.practical_live_scan = false;
''',
        'stale live scanner clear',
    )
t = t[:cs] + clear_block + t[ce:]

# Add compact telemetry to ordinary saved traces. This is intentionally useful
# for the later no-CFW project: it preserves elapsed advances and host ticks
# from scan start to a real shiny-capable root.
needle = '        if self.probe_session || self.practical_candidate_valid || self.practical_miss != 0 {\n'
insert = '''        if self.probe_session || self.practical_candidate_valid || self.practical_miss != 0 {
            line.clear();
            let _ = write!(
                line,
                "LIVE_SCAN,V680,{},{},{},{},{},{},{:04X},{:04X},{},{},{}\\n",
                self.practical_live_start_advance,
                self.practical_live_found_advance,
                self.practical_live_checked,
                self.practical_live_lane_frames,
                self.practical_live_no_lane,
                self.practical_live_found_lane,
                self.practical_live_found_state,
                self.practical_live_found_div,
                self.practical_live_start_tick,
                self.practical_live_found_tick,
                self.practical_live_found_advance.wrapping_sub(self.practical_live_start_advance)
            );
            pnp::trace_file_write(line.as_bytes());
            line.clear();
'''
t = replace_once(t, needle, insert, 'live scan trace telemetry')

# With a zero-length target queue the old WAIT renderer takes its WAIT END arm.
# Turn that arm into a live scanner dashboard. READY/PATH/RETRY strings are then
# version-bumped below and keep the proven v6.6 execution behavior.
t = replace_once(
    t,
    'pnp::println!("S671 WAIT END");',
    '''pnp::println!(
                    "S680 SCAN A{} C{} L{}",
                    rng_advance().wrapping_sub(self.practical_live_start_advance),
                    self.practical_live_checked,
                    self.practical_live_lane_frames
                );''',
    'SCAN status',
)
t = t.replace('S671 ', 'S680 ')

TRACE.write_text(t)
print('Applied Suicune v6.8.0 Live Root Scan: actual-root shiny detection, no future Target transport')
