#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/trace.rs')
s = P.read_text()


def rep(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'v721 {label}: expected 1 match, got {n}')
    s = s.replace(old, new, 1)


def function_span(text, signature):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'v721 function not found: {signature}')
    brace = text.find('{', start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit(f'v721 unclosed function: {signature}')

# Diagnostic distribution/identity state. This lives in Trace, not in the
# per-root PRE ring, so classification cadence remains unchanged.
rep(
'''    practical_evidence_reject: u32,
    practical_learn: u8,''',
'''    practical_evidence_reject: u32,
    phase_now_proto: u8,
    phase_now_rot: u8,
    phase_now_lag: u8,
    phase_exact_count: u32,
    phase_target_count: u32,
    phase_target_proto: u8,
    phase_target_rot: u8,
    phase_counts: [u32; 64],
    practical_learn: u8,''',
'fields')

rep(
'''            practical_evidence_reject: 0,
            practical_learn: 0,''',
'''            practical_evidence_reject: 0,
            phase_now_proto: b'?',
            phase_now_rot: 0,
            phase_now_lag: 0xff,
            phase_exact_count: 0,
            phase_target_count: 0,
            phase_target_proto: 0,
            phase_target_rot: 0,
            phase_counts: [0; 64],
            practical_learn: 0,''',
'defaults')

rep(
'''        self.practical_evidence_reject = 0;
        self.practical_learn = 0;''',
'''        self.practical_evidence_reject = 0;
        self.phase_now_proto = b'?';
        self.phase_now_rot = 0;
        self.phase_now_lag = 0xff;
        self.phase_exact_count = 0;
        self.phase_target_count = 0;
        self.phase_target_proto = 0;
        self.phase_target_rot = 0;
        self.phase_counts = [0; 64];
        self.practical_learn = 0;''',
'reset epoch')

rep(
'''        // v7.2.0 diagnostic build: actual-root A/r10 BranchPhase scan only.
        // No shiny READY is produced by this build.''',
'''        // v7.2.1 diagnostic build: collect the first exact-lag0 member of the
        // hardware-confirmed branch-conflict set. No shiny READY is produced.''',
'scan comment')

helper = r'''
    fn phase_cell_index(proto: u8, rot: u8) -> Option<usize> {
        if !(b'A'..=b'D').contains(&proto) || rot >= 16 {
            return None;
        }
        Some(((proto - b'A') as usize) * 16 + rot as usize)
    }

    fn phase_conflict_target(proto: u8, rot: u8) -> bool {
        (proto == b'A' && (rot == 3 || rot == 10))
            || (proto == b'B' && (rot == 1 || rot == 11))
            || (proto == b'D' && rot == 12)
    }

'''
anchor = '    fn live_root_monitor(&mut self, reader: &Gen2Reader) {'
if helper.strip() not in s:
    pos = s.find(anchor)
    if pos < 0:
        raise SystemExit('v721 live_root_monitor anchor missing')
    s = s[:pos] + helper + s[pos:]

start, end = function_span(s, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)')
new_monitor = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled
            || !self.practical_live_scan
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        {
            return;
        }

        let cur = rng_advance();
        if cur == self.practical_live_last_advance {
            return;
        }
        self.practical_live_last_advance = cur;
        self.practical_live_checked = self.practical_live_checked.saturating_add(1);

        let Some((proto, rot, lag)) = self.live_pre_cell_v720() else {
            self.phase_now_proto = b'?';
            self.phase_now_lag = 0xff;
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        };
        self.phase_now_proto = proto;
        self.phase_now_rot = rot;
        self.phase_now_lag = lag.min(0xff) as u8;

        // Keep target data exact: the classified PRE endpoint must be the
        // current root. lag=1 remains visible on screen but is not counted.
        if lag != 0 {
            return;
        }

        // Require a full timing ring collected after this scan epoch began.
        if self.practical_live_checked < PRE_VBLANK_RING_LEN as u32 {
            return;
        }

        self.phase_exact_count = self.phase_exact_count.saturating_add(1);
        if let Some(ci) = Self::phase_cell_index(proto, rot) {
            self.phase_counts[ci] = self.phase_counts[ci].saturating_add(1);
        }

        // All five cells below have hardware-confirmed PRE->POST conflicts.
        // The purpose is to collect branch-phase evidence, never to claim shiny.
        if !Self::phase_conflict_target(proto, rot) {
            return;
        }
        self.phase_target_count = self.phase_target_count.saturating_add(1);

        let Some(ai0) = add_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let Some(si0) = sub_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let ai = (ai0 as u32) & 0x3fff;
        let si = (si0 as u32) & 0x3fff;
        let state = reader.rng_state();
        let div = measured_div();

        self.practical_live_lane_frames = self.practical_live_lane_frames.saturating_add(1);
        self.phase_target_proto = proto;
        self.phase_target_rot = rot;
        self.practical_live_found_advance = cur;
        self.practical_live_found_state = state;
        self.practical_live_found_div = div;
        self.practical_live_found_lane = 251; // v7.2.1 diagnostic sentinel
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = ai;
        self.practical_live_found_si = si;
        self.practical_live_scan = false;
        self.practical_scan_enabled = false;
        pre_vblank_timing_capture_stop();
        self.practical_candidate_valid = false;
        self.practical_active = false;
        pnp::request_pause();
    }'''
s = s[:start] + new_monitor + s[end:]

# Add scan distribution before BRPHASE/PREFP. This is written only after the
# run is frozen/saved, so the 64-row export cannot perturb branch timing.
marker = '        // v6.3 authoritative suffix fingerprint.'
if s.count(marker) != 1:
    raise SystemExit(f'v721 CSV marker expected 1, got {s.count(marker)}')
csv_block = r'''        if self.probe_session {
            line.clear();
            let _ = write!(
                line,
                "phase_scan,version,start,found,fr,exact,target_hits,target_proto,target_rot,last_proto,last_rot,last_lag,no_class,index_wait\nPHASESCAN,V721,{},{},{},{},{},{},{},{},{},{},{},{}\n",
                self.practical_live_start_advance,
                self.practical_live_found_advance,
                self.practical_live_checked,
                self.phase_exact_count,
                self.phase_target_count,
                self.phase_target_proto as char,
                self.phase_target_rot,
                self.phase_now_proto as char,
                self.phase_now_rot,
                self.phase_now_lag,
                self.practical_live_no_lane,
                self.practical_live_index_wait
            );
            pnp::trace_file_write(line.as_bytes());
            line.clear();
            let _ = write!(line, "phase_count,version,proto,rot,count\n");
            pnp::trace_file_write(line.as_bytes());
            for pi in 0..4usize {
                for rot in 0..16usize {
                    let idx = pi * 16 + rot;
                    line.clear();
                    let _ = write!(line, "PRECOUNT,V721,{},{},{}\n", (b'A' + pi as u8) as char, rot, self.phase_counts[idx]);
                    pnp::trace_file_write(line.as_bytes());
                }
            }
            line.clear();
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());
        }

'''
pos = s.find(marker)
s = s[:pos] + csv_block + s[pos:]

old_ui_start = '''        if self.practical_scan_enabled {
            pnp::println!("S720 PHASE SCAN");
            pnp::println!("A/r10 ONLY");
            pnp::println!("FR{} ADV{}", self.practical_live_checked, rng_advance().wrapping_sub(self.practical_live_start_advance));
        } else if self.practical_live_found_lane == 250 && !self.probe_session {
            pnp::println!("S720 PROBE A/r10");
            pnp::println!("UP+B DONOR");
'''
new_ui_start = '''        if self.practical_scan_enabled {
            pnp::println!("S721 MULTI PHASE");
            if self.phase_now_proto == b'?' {
                pnp::println!("NOW ?");
            } else {
                pnp::println!("NOW {}/r{} L{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag);
            }
            pnp::println!("FR{} EX{}", self.practical_live_checked, self.phase_exact_count);
            if self.practical_live_checked >= 10000 {
                pnp::println!("RESET SUGGESTED");
            } else {
                pnp::println!("TGT A3 A10 B1 B11 D12");
            }
        } else if self.practical_live_found_lane == 251 && !self.probe_session {
            pnp::println!("S721 PROBE {}/r{}", self.phase_target_proto as char, self.phase_target_rot);
            pnp::println!("UP+B DONOR");
'''
rep(old_ui_start, new_ui_start, 'UI')
s = s.replace('pnp::println!("S720 PHASE RUN");', 'pnp::println!("S721 PHASE RUN");')
s = s.replace('pnp::println!("S720 IDLE");', 'pnp::println!("S721 IDLE");')

P.write_text(s)
print('Applied Suicune v7.2.1 MultiCell BranchPhase: five conflict cells + live cell UI + 64-cell distribution')
