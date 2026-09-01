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


p = PRACTICAL.read_text()
p = replace_once(
    p,
    'pub const MIN_SEARCH_LEAD: u32 = 180;\npub const MAX_SEARCH_CANDIDATES: usize = 8;\n',
    '''pub const MIN_SEARCH_LEAD: u32 = 180;
pub const ROLL_REFRESH_INTERVAL: u32 = 256;
pub const ROLL_LOCK_LEAD: u32 = 384;
pub const MAX_SEARCH_CANDIDATES: usize = 8;
''',
    'rolling constants',
)
PRACTICAL.write_text(p)

t = TRACE.read_text()
t = replace_once(
    t,
    '    practical_transport_actual_lane: u8,\n',
    '''    practical_transport_actual_lane: u8,
    practical_roll_next: u32,
    practical_roll_count: u16,
    practical_roll_eval: u16,
    practical_roll_pre: u16,
    practical_roll_refresh_fail: u16,
''',
    'rolling fields',
)
t = replace_once(
    t,
    '            practical_transport_actual_lane: 0,\n',
    '''            practical_transport_actual_lane: 0,
            practical_roll_next: 0,
            practical_roll_count: 0,
            practical_roll_eval: 0,
            practical_roll_pre: 0,
            practical_roll_refresh_fail: 0,
''',
    'rolling field defaults',
)

ss, se = function_span(t, '    pub fn search_practical_targets(&mut self, reader: &Gen2Reader)')
search_block = t[ss:se]
search_block = replace_once(
    search_block,
    '        self.clear_transport_diag();\n',
    '''        self.clear_transport_diag();
        self.practical_roll_next = 0;
        self.practical_roll_count = 0;
        self.practical_roll_eval = 0;
        self.practical_roll_pre = 0;
        self.practical_roll_refresh_fail = 0;
''',
    'fresh rolling epoch',
)
search_block = replace_once(
    search_block,
    '        self.practical_search_enabled = true;\n',
    '''        self.practical_search_enabled = true;
        let first_lead = self.practical_targets[0].wrapping_sub(base_advance);
        self.practical_roll_next = if first_lead > practical::ROLL_LOCK_LEAD {
            base_advance.wrapping_add(practical::ROLL_REFRESH_INTERVAL)
        } else {
            0
        };
''',
    'initial rolling schedule',
)
t = t[:ss] + search_block + t[se:]

ws, _ = function_span(t, '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')
helper = r'''    fn rolling_refresh_targets(&mut self, reader: &Gen2Reader) -> bool {
        let r = latest_pre_vblank_ring();
        let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if count != PRE_VBLANK_RING_LEN {
            return false;
        }
        let (proto, mut rot, best, _, consecutive) = classify_pre_ring(&r);
        if !consecutive || best != 0 || !practical::has_proto(proto) {
            return false;
        }

        let (last_advance, _) = pre_ring_sample(&r, count - 1);
        let current_advance = rng_advance();
        let pre_lag = current_advance.wrapping_sub(last_advance);
        if pre_lag > 1 {
            return false;
        }
        if pre_lag == 1 {
            rot = rot.wrapping_add(1) & 15;
        }

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
            return false;
        };
        let ai_now = ai_validate
            .wrapping_add(16)
            .wrapping_add(pre_lag)
            & 0x3fff;

        let mut st = reader.rng_state();
        let mut div = measured_div();
        let mut ai = ai_now;
        let mut si = (sub_div_tracker().index().unwrap_or(0) as u32) & 0x3fff;
        let base_advance = rng_advance();

        let mut targets = [0u32; practical::MAX_SEARCH_CANDIDATES];
        let mut states = [0u16; practical::MAX_SEARCH_CANDIDATES];
        let mut divs = [0u16; practical::MAX_SEARCH_CANDIDATES];
        let mut lanes = [0u8; practical::MAX_SEARCH_CANDIDATES];
        let mut supports = [0u8; practical::MAX_SEARCH_CANDIDATES];
        let mut raws = [0u16; practical::MAX_SEARCH_CANDIDATES];
        let mut found: usize = 0;

        for step in 1..=practical::SEARCH_HORIZON {
            practical::normal_step(&mut st, &mut div, &mut ai, &mut si);
            if step < practical::MIN_SEARCH_LEAD {
                continue;
            }
            let future_rot = rot.wrapping_add((step & 15) as u8) & 15;
            let Some(lane_id) = practical::lane_for_pre(proto, future_rot) else {
                continue;
            };
            let Some(p) = practical::evaluate(lane_id, st, div) else {
                continue;
            };
            if found >= practical::MAX_SEARCH_CANDIDATES {
                break;
            }
            targets[found] = base_advance.wrapping_add(step);
            states[found] = st;
            divs[found] = div;
            lanes[found] = lane_id;
            supports[found] = p.support_weight;
            raws[found] = p.raw;
            found += 1;
        }

        if found == 0 {
            return false;
        }

        for i in 0..found {
            self.practical_targets[i] = targets[i];
            self.practical_states[i] = states[i];
            self.practical_divs[i] = divs[i];
            self.practical_lanes[i] = lanes[i];
            self.practical_supports[i] = supports[i];
            self.practical_raws[i] = raws[i];
        }
        self.practical_search_count = found as u8;
        self.practical_search_index = 0;
        self.practical_search_error = 0;
        self.practical_search_from = base_advance;
        self.practical_roll_count = self.practical_roll_count.saturating_add(1);
        self.clear_transport_diag();

        let first_lead = targets[0].wrapping_sub(base_advance);
        self.practical_roll_next = if first_lead > practical::ROLL_LOCK_LEAD {
            base_advance.wrapping_add(practical::ROLL_REFRESH_INTERVAL)
        } else {
            0
        };
        true
    }

'''
t = t[:ws] + helper + t[ws:]

ws, we = function_span(t, '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')
wait_new = r'''    fn practical_wait_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_search_enabled
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        {
            return;
        }

        let current = rng_advance();

        if self.practical_roll_next != 0 && current >= self.practical_roll_next {
            if self.rolling_refresh_targets(reader) {
                return;
            }
            self.practical_roll_refresh_fail =
                self.practical_roll_refresh_fail.saturating_add(1);
            self.practical_roll_next =
                current.wrapping_add(practical::ROLL_REFRESH_INTERVAL / 4);
        }

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
            if self.rolling_refresh_targets(reader) {
                return;
            }
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
                self.practical_roll_next = 0;
                self.bind_practical_prediction(p);
                pnp::request_pause();
                return;
            }
            self.set_transport_diag(3, idx, reader, actual_lane);
            self.practical_roll_eval = self.practical_roll_eval.saturating_add(1);
        } else {
            self.set_transport_diag(2, idx, reader, actual_lane);
            self.practical_roll_pre = self.practical_roll_pre.saturating_add(1);
        }

        self.practical_search_index += 1;
        self.practical_search_skipped = self.practical_search_skipped.saturating_add(1);

        if self.rolling_refresh_targets(reader) {
            return;
        }

        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
            self.practical_terminal_advance = rng_advance();
            self.save_transport_diag();
            pnp::request_pause();
        }
    }'''
t = t[:ws] + wait_new + t[we:]

cs, ce = function_span(t, '    fn clear_stale_practical_status(&mut self)')
clear_block = t[cs:ce]
clear_block = replace_once(
    clear_block,
    '        self.clear_transport_diag();\n',
    '''        self.clear_transport_diag();
        self.practical_roll_next = 0;
''',
    'stale rolling schedule clear',
)
t = t[:cs] + clear_block + t[ce:]

ss, se = function_span(t, '    fn save_transport_diag(&mut self)')
save_block = t[ss:se]
save_block = replace_once(
    save_block,
    '        pnp::trace_file_write(line.as_bytes());\n        pnp::trace_file_close();\n',
    '''        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(
            line,
            "ROLL,V671,{},{},{},{},{}\\n",
            self.practical_roll_count,
            self.practical_roll_eval,
            self.practical_roll_pre,
            self.practical_roll_refresh_fail,
            self.practical_roll_next
        );
        pnp::trace_file_write(line.as_bytes());
        pnp::trace_file_close();
''',
    'rolling terminal telemetry',
)
t = t[:ss] + save_block + t[se:]

old_wait = '''                    "S670 WAIT {}/{} +{}",
                    self.practical_search_index + 1,
                    self.practical_search_count,
                    target.saturating_sub(rng_advance())
'''
new_wait = '''                    "S671 WAIT {}/{} +{} R{}",
                    self.practical_search_index + 1,
                    self.practical_search_count,
                    target.saturating_sub(rng_advance()),
                    self.practical_roll_count
'''
t = replace_once(t, old_wait, new_wait, 'rolling WAIT status')
t = t.replace('S670 ', 'S671 ')

TRACE.write_text(t)
print('Applied Suicune v6.7.1 rolling actual-root re-search')
