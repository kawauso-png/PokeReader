#!/usr/bin/env python3
from pathlib import Path

TRACE = Path('reader_core/src/crystal/trace.rs')
PRACTICAL = Path('reader_core/src/crystal/practical.rs')


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


# ---------------------------------------------------------------------------
# 1) Future normal-RNG transport must use the measured 0x4000 DIV-index model.
# Keep normal_inc() as the simple 16-phase helper used by old diagnostics, but
# use full-index stepping for actual future-root projection.
# ---------------------------------------------------------------------------
p = PRACTICAL.read_text()
old = '''pub fn normal_inc(index: u32) -> u8 {
    NORMAL_INC[(index as usize) & 15]
}

pub fn normal_step(state: &mut u16, div: &mut u16, ai: &mut u32, si: &mut u32) {
    let mut av = (*div >> 8) as u8;
    let mut sv = *div as u8;
    av = av.wrapping_add(normal_inc(*ai));
    sv = sv.wrapping_add(normal_inc(*si));
    *ai = (*ai).wrapping_add(1);
    *si = (*si).wrapping_add(1);
    *state = upd(*state, av, sv);
    *div = ((av as u16) << 8) | sv as u16;
}
'''
new = '''pub fn normal_inc(index: u32) -> u8 {
    NORMAL_INC[(index as usize) & 15]
}

// v6.7.0 Transport Stable: the 16-step cadence has six measured exceptions
// inside the full 0x4000 tracker cycle. Older practical search discarded the
// upper index bits and therefore accumulated a one-byte DIV error whenever a
// long WAIT crossed one of these sites.
pub fn normal_inc_full(index: u32) -> u8 {
    let n = index & 0x3fff;
    let mut x = NORMAL_INC[(n as usize) & 15];
    if matches!(n, 0x0008 | 0x0009 | 0x0562 | 0x0563 | 0x22b5 | 0x22b6) {
        x = if x == 0x12 { 0x13 } else { 0x12 };
    }
    x
}

pub fn normal_step(state: &mut u16, div: &mut u16, ai: &mut u32, si: &mut u32) {
    let mut av = (*div >> 8) as u8;
    let mut sv = *div as u8;
    av = av.wrapping_add(normal_inc_full(*ai));
    sv = sv.wrapping_add(normal_inc_full(*si));
    *ai = (*ai).wrapping_add(1) & 0x3fff;
    *si = (*si).wrapping_add(1) & 0x3fff;
    *state = upd(*state, av, sv);
    *div = ((av as u16) << 8) | sv as u16;
}
'''
p = replace_once(p, old, new, 'full-index normal step')
PRACTICAL.write_text(p)

# ---------------------------------------------------------------------------
# 2) Add transport diagnostics. ERR4 is pre-encounter, so distinguish:
#    1 PASS = target was already passed
#    2 PRE  = target hit but live PRE lane changed
#    3 EVAL = target/PRE hit but actual root no longer evaluates shiny
# ---------------------------------------------------------------------------
t = TRACE.read_text()
t = replace_once(
    t,
    '    practical_search_skipped: u8,\n',
    '''    practical_search_skipped: u8,
    practical_transport_reason: u8,
    practical_transport_target: u32,
    practical_transport_pred_state: u16,
    practical_transport_pred_div: u16,
    practical_transport_actual_state: u16,
    practical_transport_actual_div: u16,
    practical_transport_actual_lane: u8,
''',
    'transport fields',
)
t = replace_once(
    t,
    '            practical_search_skipped: 0,\n',
    '''            practical_search_skipped: 0,
            practical_transport_reason: 0,
            practical_transport_target: 0,
            practical_transport_pred_state: 0,
            practical_transport_pred_div: 0,
            practical_transport_actual_state: 0,
            practical_transport_actual_div: 0,
            practical_transport_actual_lane: 0,
''',
    'transport defaults',
)

# ---------------------------------------------------------------------------
# 3) Re-anchor ADIV against the full tracker cycle, not just modulo 16.
# The PRE ring observes the A-side VBlank DIV. We still leave SDIV on its live
# tracker index because PRE ring does not contain the B-side sample.
# ---------------------------------------------------------------------------
cal_start = t.find('        // Validate the normal 18/19 DIV-byte cadence')
cal_end = t.find('        // Heavy work is intentionally done only while the VC is frozen.', cal_start)
if cal_start < 0 or cal_end < 0:
    raise SystemExit('cadence calibration block anchors missing')
cal = '''        // v6.7.0: validate the cadence in the full 0x4000 ADIV index space.
        // The tracker supplies the coarse absolute block; the 17-sample PRE
        // ring resolves the low phase. This also validates exception sites if
        // the recent window crosses one of them.
        let ai_hint = (add_div_tracker().index().unwrap_or(0) as u32) & 0x3fff;
        let first_block = ai_hint
            .wrapping_sub(16u32.wrapping_add(pre_lag))
            & 0x3ff0;
        let mut cadence_first: Option<u32> = None;
        for phase in 0..16u32 {
            let candidate = (first_block | phase) & 0x3fff;
            let mut ok = true;
            for j in 0..16usize {
                let (_, p0) = pre_ring_sample(&r, j);
                let (_, p1) = pre_ring_sample(&r, j + 1);
                let b0 = (p0 >> 6) as u8;
                let b1 = (p1 >> 6) as u8;
                if b1.wrapping_sub(b0)
                    != practical::normal_inc_full(candidate.wrapping_add(j as u32))
                {
                    ok = false;
                    break;
                }
            }
            if ok {
                cadence_first = Some(candidate);
                break;
            }
        }
        let Some(ai_validate) = cadence_first else {
            self.practical_search_error = 15;
            self.practical_terminal_advance = rng_advance();
            return;
        };
        let ai_now = ai_validate
            .wrapping_add(16)
            .wrapping_add(pre_lag)
            & 0x3fff;
        for i in 0..16usize {
            let (_, p0) = pre_ring_sample(&r, i);
            let (_, p1) = pre_ring_sample(&r, i + 1);
            let b0 = (p0 >> 6) as u8;
            let b1 = (p1 >> 6) as u8;
            if b1.wrapping_sub(b0)
                != practical::normal_inc_full(ai_validate.wrapping_add(i as u32))
            {
                self.practical_search_error = 5;
                self.practical_terminal_advance = rng_advance();
                return;
            }
        }

'''
t = t[:cal_start] + cal + t[cal_end:]

# Ensure the S-side live tracker enters normal_step in the same bounded index
# space used by normal_inc_full().
t = replace_once(
    t,
    '        let mut si = sub_div_tracker().index().unwrap_or(0) as u32;\n',
    '        let mut si = (sub_div_tracker().index().unwrap_or(0) as u32) & 0x3fff;\n',
    'bounded S tracker',
)

# Insert reusable transport diagnostic helpers immediately before WAIT monitor.
wait_start, _ = function_span(t, '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')
helpers = '''    fn clear_transport_diag(&mut self) {
        self.practical_transport_reason = 0;
        self.practical_transport_target = 0;
        self.practical_transport_pred_state = 0;
        self.practical_transport_pred_div = 0;
        self.practical_transport_actual_state = 0;
        self.practical_transport_actual_div = 0;
        self.practical_transport_actual_lane = 0;
    }

    fn set_transport_diag(
        &mut self,
        reason: u8,
        idx: usize,
        reader: &Gen2Reader,
        actual_lane: Option<u8>,
    ) {
        self.practical_transport_reason = reason;
        self.practical_transport_target = self.practical_targets[idx];
        self.practical_transport_pred_state = self.practical_states[idx];
        self.practical_transport_pred_div = self.practical_divs[idx];
        self.practical_transport_actual_state = reader.rng_state();
        self.practical_transport_actual_div = measured_div();
        self.practical_transport_actual_lane = actual_lane.unwrap_or(0);
    }

    fn save_transport_diag(&mut self) {
        if !pnp::trace_file_open(self.save_index) {
            self.save_result = Some(false);
            return;
        }
        let mut line = LineBuf::new();
        let _ = write!(
            line,
            "transport,version,reason,search_from,target,current,search_count,search_index,search_skipped,pred_state,pred_div,actual_state,actual_div,expected_lane,actual_lane\\n"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let idx = (self.practical_search_index as usize)
            .min((self.practical_search_count as usize).saturating_sub(1));
        let expected_lane = if self.practical_search_count == 0 { 0 } else { self.practical_lanes[idx] };
        let _ = write!(
            line,
            "TRANSPORT,V670,{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{},{}\\n",
            self.practical_transport_reason,
            self.practical_search_from,
            self.practical_transport_target,
            rng_advance(),
            self.practical_search_count,
            self.practical_search_index,
            self.practical_search_skipped,
            self.practical_transport_pred_state,
            self.practical_transport_pred_div,
            self.practical_transport_actual_state,
            self.practical_transport_actual_div,
            expected_lane,
            self.practical_transport_actual_lane,
        );
        pnp::trace_file_write(line.as_bytes());
        pnp::trace_file_close();
        self.save_result = Some(true);
        self.save_index += 1;
    }

'''
t = t[:wait_start] + helpers + t[wait_start:]

# Clear transport diagnostics whenever Y+DOWN starts a new search.
ss, se = function_span(t, '    pub fn search_practical_targets(&mut self, reader: &Gen2Reader)')
search_block = t[ss:se]
search_block = replace_once(
    search_block,
    '        self.practical_search_skipped = 0;\n',
    '        self.practical_search_skipped = 0;\n        self.clear_transport_diag();\n',
    'fresh search transport clear',
)
t = t[:ss] + search_block + t[se:]

# Replace WAIT monitor as one unit so every ERR4 exit has an explicit reason.
ws, we = function_span(t, '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')
wait_new = '''    fn practical_wait_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_search_enabled
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        {
            return;
        }

        let current = rng_advance();
        while (self.practical_search_index as usize) < (self.practical_search_count as usize)
            && self.practical_targets[self.practical_search_index as usize] < current
        {
            let missed = self.practical_search_index as usize;
            let actual_lane = self.live_practical_lane();
            self.set_transport_diag(1, missed, reader, actual_lane);
            self.practical_search_index += 1;
            self.practical_search_skipped = self.practical_search_skipped.saturating_add(1);
        }

        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
            self.practical_terminal_advance = rng_advance();
            self.save_transport_diag();
            pnp::request_pause();
            return;
        }

        let idx = self.practical_search_index as usize;
        if current != self.practical_targets[idx] {
            return;
        }

        let lane_id = self.practical_lanes[idx];
        let actual_lane = self.live_practical_lane();
        if actual_lane == Some(lane_id) {
            if let Some(p) = practical::evaluate(lane_id, reader.rng_state(), measured_div()) {
                self.clear_transport_diag();
                self.bind_practical_prediction(p);
                pnp::request_pause();
                return;
            }
            self.set_transport_diag(3, idx, reader, actual_lane);
        } else {
            self.set_transport_diag(2, idx, reader, actual_lane);
        }

        // Candidate was reached but failed live transport revalidation. Keep
        // the game untouched and try the next precomputed candidate.
        self.practical_search_index += 1;
        self.practical_search_skipped = self.practical_search_skipped.saturating_add(1);
        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
            self.practical_terminal_advance = rng_advance();
            self.save_transport_diag();
            pnp::request_pause();
        }
    }'''
t = t[:ws] + wait_new + t[we:]

# v6.6.1 clears terminal runtime state after reset. Clear diagnostic epoch too.
cs, ce = function_span(t, '    fn clear_stale_practical_status(&mut self)')
clear_block = t[cs:ce]
clear_block = replace_once(
    clear_block,
    '        self.practical_terminal_advance = 0;\n',
    '        self.practical_terminal_advance = 0;\n        self.clear_transport_diag();\n',
    'stale transport clear',
)
t = t[:cs] + clear_block + t[ce:]

# Add transport state to ordinary successful/branch-fail trace saves too.
old_if = '        if self.probe_session || self.practical_candidate_valid || self.practical_miss != 0 {\n'
new_if = '''        if self.probe_session || self.practical_candidate_valid || self.practical_miss != 0 {
            line.clear();
            let _ = write!(
                line,
                "transport,version,reason,search_from,target,current,search_count,search_index,search_skipped,pred_state,pred_div,actual_state,actual_div,expected_lane,actual_lane\\nTRANSPORT,V670,{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{},{}\\n",
                self.practical_transport_reason,
                self.practical_search_from,
                self.practical_transport_target,
                rng_advance(),
                self.practical_search_count,
                self.practical_search_index,
                self.practical_search_skipped,
                self.practical_transport_pred_state,
                self.practical_transport_pred_div,
                self.practical_transport_actual_state,
                self.practical_transport_actual_div,
                self.practical_lane,
                self.practical_transport_actual_lane,
            );
            pnp::trace_file_write(line.as_bytes());
            line.clear();
'''
t = replace_once(t, old_if, new_if, 'normal transport telemetry')

# Give ERR4 a useful on-screen reason instead of a generic K count.
old_status = '''        } else if self.practical_search_error != 0 {
            pnp::println!("S661 ERR {} K{}", self.practical_search_error, self.practical_search_skipped);
        } else {
            pnp::println!("S661 IDLE");
'''
new_status = '''        } else if self.practical_search_error == 4 {
            let why = match self.practical_transport_reason {
                1 => "PASS",
                2 => "PRE",
                3 => "EVAL",
                _ => "UNK",
            };
            pnp::println!("S670 E4 {} K{}", why, self.practical_search_skipped);
        } else if self.practical_search_error != 0 {
            pnp::println!("S670 ERR {} K{}", self.practical_search_error, self.practical_search_skipped);
        } else {
            pnp::println!("S670 IDLE");
'''
t = replace_once(t, old_status, new_status, 'ERR4 reason status')

# Make all v6.6.1 practical statuses visually identify the new build.
t = t.replace('S661 ', 'S670 ')

TRACE.write_text(t)
print('Applied Suicune Transport Stable v6.7.0: full-index projection + ERR4 diagnostics')
