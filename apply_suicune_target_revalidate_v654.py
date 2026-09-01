#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
text = path.read_text()

# 1) Give cadence-autophase failure its own code. ERR2 remains the original
# unsupported PRE-prototype/lane code from v6.4.
old = '''        let Some(ai_validate) = cadence_first else {
            self.practical_search_error = 2;
            return;
        };'''
new = '''        let Some(ai_validate) = cadence_first else {
            self.practical_search_error = 15;
            return;
        };'''
if text.count(old) != 1:
    raise SystemExit(f"v6.5.4 cadence error anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

# 2) Target-time PRE validation must use the same <=1 advance boundary
# compensation as search start. The old exact last_advance==current check
# caused valid targets to be skipped as ERR4 K1.
old = '''    fn live_practical_lane(&self) -> Option<u8> {
        let r = latest_pre_vblank_ring();
        let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if count != PRE_VBLANK_RING_LEN {
            return None;
        }
        let (last_advance, _) = pre_ring_sample(&r, count - 1);
        if last_advance != rng_advance() {
            return None;
        }
        let (proto, rot, best, _, consecutive) = classify_pre_ring(&r);
        if !consecutive || best != 0 {
            return None;
        }
        practical::lane_for_pre(proto, rot)
    }
'''
new = '''    fn live_practical_lane(&self) -> Option<u8> {
        let r = latest_pre_vblank_ring();
        let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if count != PRE_VBLANK_RING_LEN {
            return None;
        }
        let (last_advance, _) = pre_ring_sample(&r, count - 1);
        let current = rng_advance();
        let lag = current.wrapping_sub(last_advance);
        if lag > 1 {
            return None;
        }
        let (proto, mut rot, best, _, consecutive) = classify_pre_ring(&r);
        if !consecutive || best != 0 {
            return None;
        }
        if lag == 1 {
            rot = rot.wrapping_add(1) & 15;
        }
        practical::lane_for_pre(proto, rot)
    }
'''
if text.count(old) != 1:
    raise SystemExit(f"v6.5.4 live lane anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

# 3) Re-evaluate the ACTUAL root at the candidate Target. The precomputed
# state/DIV were only a projection used to decide when to look. Exact equality
# is unnecessarily brittle: evaluate() is the authoritative shiny/support gate
# and already consumes the live state+DIV.
old = '''        let lane_id = self.practical_lanes[idx];
        let root_ok = reader.rng_state() == self.practical_states[idx]
            && measured_div() == self.practical_divs[idx];
        let pre_ok = self.live_practical_lane() == Some(lane_id);

        if root_ok && pre_ok {
            if let Some(p) = practical::evaluate(lane_id, reader.rng_state(), measured_div()) {
                self.bind_practical_prediction(p);
                pnp::request_pause();
                return;
            }
        }
'''
new = '''        let lane_id = self.practical_lanes[idx];
        let pre_ok = self.live_practical_lane() == Some(lane_id);

        if pre_ok {
            if let Some(p) = practical::evaluate(lane_id, reader.rng_state(), measured_div()) {
                self.bind_practical_prediction(p);
                pnp::request_pause();
                return;
            }
        }
'''
if text.count(old) != 1:
    raise SystemExit(f"v6.5.4 target revalidate anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

# 4) If the short 12k queue is exhausted, freeze instead of silently leaving
# the game running. The user can immediately Y+Down to search another 12k
# window. Keep ERR4/K as useful telemetry.
old = '''        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
            return;
        }
'''
new = '''        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
            pnp::request_pause();
            return;
        }
'''
if text.count(old) != 1:
    raise SystemExit(f"v6.5.4 expired queue anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

old = '''        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
        }
'''
new = '''        if self.practical_search_index >= self.practical_search_count {
            self.practical_search_enabled = false;
            self.practical_search_error = 4;
            pnp::request_pause();
        }
'''
if text.count(old) != 1:
    raise SystemExit(f"v6.5.4 missed queue anchor count: {text.count(old)}")
text = text.replace(old, new, 1)

if "let lag = current.wrapping_sub(last_advance);" not in text:
    raise SystemExit("v6.5.4 live lag marker missing")

path.write_text(text)
print("Applied Suicune v6.5.4 live PRE + actual-root target revalidation")
