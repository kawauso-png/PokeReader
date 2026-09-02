#!/usr/bin/env python3
from pathlib import Path

HOOK=Path('reader_core/src/crystal/hook.rs')
TRACE=Path('reader_core/src/crystal/trace.rs')


def rep(s, old, new, label):
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'v720 {label}: expected 1 match, got {n}')
    return s.replace(old,new,1)

h=HOOK.read_text()
t=TRACE.read_text()

# ---------------------------------------------------------------------------
# v7.2.0 BranchPhase Probe
#
# The current PRE fingerprint stores only (DIV,mcycle).  The rDIV hook already
# samples one host tick for every read.  Keep that existing sample and add only
# static stores/arithmetic: no extra system_tick(), DIV/state read, or emulator
# memory read on the hook path.
# ---------------------------------------------------------------------------
h=rep(h,
'''pub struct PreVBlankRing {
    pub count: u8,
    pub write: u8,
    pub advance: [u32; PRE_VBLANK_RING_LEN],
    pub phase: [u16; PRE_VBLANK_RING_LEN],
}''',
'''pub struct PreVBlankRing {
    pub count: u8,
    pub write: u8,
    pub advance: [u32; PRE_VBLANK_RING_LEN],
    pub phase: [u16; PRE_VBLANK_RING_LEN],
    // v7.2: host timing already sampled by gb_read_mem().  These are passive
    // copies only, used offline to explain one PRE cell producing many POSTs.
    pub a_tick: [u64; PRE_VBLANK_RING_LEN],
    pub aa_delta: [u32; PRE_VBLANK_RING_LEN],
    pub ab_delta: [u32; PRE_VBLANK_RING_LEN],
}''','extend PRE ring')

h=rep(h,
'''        advance: [0; PRE_VBLANK_RING_LEN],
        phase: [0; PRE_VBLANK_RING_LEN],
    };
}

static mut PRE_VBLANK_RING: PreVBlankRing = PreVBlankRing::EMPTY;''',
'''        advance: [0; PRE_VBLANK_RING_LEN],
        phase: [0; PRE_VBLANK_RING_LEN],
        a_tick: [0; PRE_VBLANK_RING_LEN],
        aa_delta: [0; PRE_VBLANK_RING_LEN],
        ab_delta: [0; PRE_VBLANK_RING_LEN],
    };
}

static mut PRE_VBLANK_RING: PreVBlankRing = PreVBlankRing::EMPTY;
static mut PRE_VBLANK_LAST_A_TICK: u64 = 0;
static mut PRE_VBLANK_LAST_SLOT: u8 = 0xff;''','PRE ring defaults')

h=rep(h,
'''fn push_pre_vblank_sample(advance: u32, div: u8, mcycle: u8) {
    unsafe {
        let idx = PRE_VBLANK_RING.write as usize;
        PRE_VBLANK_RING.advance[idx] = advance;
        PRE_VBLANK_RING.phase[idx] =
            (((div as u16) << 6) | ((mcycle as u16) & 0x3f)) & 0x3fff;
        PRE_VBLANK_RING.write =
            ((PRE_VBLANK_RING.write as usize + 1) % PRE_VBLANK_RING_LEN) as u8;
        if (PRE_VBLANK_RING.count as usize) < PRE_VBLANK_RING_LEN {
            PRE_VBLANK_RING.count += 1;
        }
    }
}''',
'''fn push_pre_vblank_sample(advance: u32, div: u8, mcycle: u8, host_tick: u64) {
    unsafe {
        let idx = PRE_VBLANK_RING.write as usize;
        PRE_VBLANK_RING.advance[idx] = advance;
        PRE_VBLANK_RING.phase[idx] =
            (((div as u16) << 6) | ((mcycle as u16) & 0x3f)) & 0x3fff;
        PRE_VBLANK_RING.a_tick[idx] = host_tick;
        PRE_VBLANK_RING.aa_delta[idx] = if PRE_VBLANK_LAST_A_TICK != 0 {
            host_tick.saturating_sub(PRE_VBLANK_LAST_A_TICK).min(u32::MAX as u64) as u32
        } else { 0 };
        PRE_VBLANK_RING.ab_delta[idx] = 0;
        PRE_VBLANK_LAST_A_TICK = host_tick;
        PRE_VBLANK_LAST_SLOT = idx as u8;
        PRE_VBLANK_RING.write =
            ((PRE_VBLANK_RING.write as usize + 1) % PRE_VBLANK_RING_LEN) as u8;
        if (PRE_VBLANK_RING.count as usize) < PRE_VBLANK_RING_LEN {
            PRE_VBLANK_RING.count += 1;
        }
    }
}

fn finish_pre_vblank_sample(host_tick: u64) {
    unsafe {
        if PRE_VBLANK_LAST_SLOT == 0xff { return; }
        let idx = PRE_VBLANK_LAST_SLOT as usize;
        let a = PRE_VBLANK_RING.a_tick[idx];
        PRE_VBLANK_RING.ab_delta[idx] =
            host_tick.saturating_sub(a).min(u32::MAX as u64) as u32;
    }
}''','PRE timing capture')

h=rep(h,
'''        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle);''',
'''        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle, host_tick);''','A timing call')

h=rep(h,
'''    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();''',
'''    if RNG_DIV_READ_2.contains(&pc) {
        finish_pre_vblank_sample(host_tick);
        let div = reader.div();''','B timing completion')

# Extra chronological accessor for CSV only.  Existing classifier remains on
# the original advance/phase accessor and therefore cannot accidentally depend
# on host timing.
t=rep(t,
'''fn pre_ring_sample(r: &PreVBlankRing, chronological_index: usize) -> (u32, u16) {
    let start = pre_ring_start(r);
    let idx = (start + chronological_index) % PRE_VBLANK_RING_LEN;
    (r.advance[idx], r.phase[idx])
}
''',
'''fn pre_ring_sample(r: &PreVBlankRing, chronological_index: usize) -> (u32, u16) {
    let start = pre_ring_start(r);
    let idx = (start + chronological_index) % PRE_VBLANK_RING_LEN;
    (r.advance[idx], r.phase[idx])
}

fn pre_ring_timing_sample(r: &PreVBlankRing, chronological_index: usize) -> (u64, u32, u32) {
    let start = pre_ring_start(r);
    let idx = (start + chronological_index) % PRE_VBLANK_RING_LEN;
    (r.a_tick[idx], r.aa_delta[idx], r.ab_delta[idx])
}
''','timing accessor')

# This build is deliberately probe-only.  Y+DOWN still starts an actual-root
# scan, but instead of waiting for a shiny forecast it pauses at the next exact
# A/r10 PRE cell.  A/r10 currently has the richest observed one-to-many POST
# set, so repeated samples maximize information gain without 10k+ shiny waits.
t=rep(t,
'''        // v7.1.8: actual-root scan only. There is no future target queue,
        // search horizon, rolling re-root transport, or open-loop wait.
        self.practical_scan_enabled = true;''',
'''        // v7.2.0 diagnostic build: actual-root A/r10 BranchPhase scan only.
        // No shiny READY is produced by this build.
        self.practical_scan_enabled = true;''','scan comment')

# Replace only the body after PRE classification in live_root_monitor.  The
# existing root de-duplication and PRE classifier are retained.
start=t.find('        let proven = practical::lane_for_pre(proto, rot);')
end=t.find('    fn practical_fail(&mut self, code: u8)', start)
if start<0 or end<0:
    raise SystemExit('v720 live monitor body anchors missing')
old=t[start:end]
# Keep function closing brace by replacing through the text immediately before
# practical_fail.  The body below closes live_root_monitor itself.
new='''        // v7.2.0: isolate one known unstable PRE so every trial answers the
        // same question.  A/r10 has observed A/r2, B/r9, C/r8, B/r14, D/r2
        // and D/r15 outcomes.  Do not evaluate shiny lanes here.
        if proto != b'A' || rot != 10 {
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        }

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
        self.practical_live_found_advance = cur;
        self.practical_live_found_state = state;
        self.practical_live_found_div = div;
        self.practical_live_found_lane = 250; // diagnostic sentinel, never a donor lane
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = ai;
        self.practical_live_found_si = si;
        self.practical_live_scan = false;
        self.practical_scan_enabled = false;
        self.practical_candidate_valid = false;
        self.practical_active = false;
        pnp::request_pause();
    }

'''
t=t[:start]+new+t[end:]

# Add the passive timing ring immediately after PREFP.  Raw ticks are kept so
# offline analysis can test arbitrary periods/moduli without choosing a new
# hypothesis in the 3GX.
needle='''            let _ = write!(line, "\\n\\n");
            pnp::trace_file_write(line.as_bytes());
        }


        // v6.3 authoritative suffix fingerprint.'''
insert='''            let _ = write!(line, "\\n\\n");
            pnp::trace_file_write(line.as_bytes());

            line.clear();
            let _ = write!(line, "branch_phase,version,index,advance,phase,a_tick,aa_delta,ab_delta\\n");
            pnp::trace_file_write(line.as_bytes());
            for i in 0..count {
                let (adv, phase) = pre_ring_sample(&r, i);
                let (a_tick, aa, ab) = pre_ring_timing_sample(&r, i);
                line.clear();
                let _ = write!(line, "BRPHASE,V720,{},{},{:04X},{},{},{}\\n", i, adv, phase, a_tick, aa, ab);
                pnp::trace_file_write(line.as_bytes());
            }
            line.clear();
            let _ = write!(line, "\\n");
            pnp::trace_file_write(line.as_bytes());
        }


        // v6.3 authoritative suffix fingerprint.'''
t=rep(t,needle,insert,'BRPHASE CSV')

# Make the dedicated nature of the build impossible to confuse with production
# EvidenceGate.  The UP+B execution path itself is unchanged.
old_ui='''        if self.practical_scan_enabled {
            pnp::println!("S719 SCAN");
            pnp::println!("FR{} ADV{}", self.practical_live_checked, rng_advance().wrapping_sub(self.practical_live_start_advance));
            pnp::println!("P{} X{}", self.practical_live_lane_frames, self.practical_empirical_cell_frames);
            pnp::println!("EV{} SK{} RJ{}", self.practical_live_exact_eval.saturating_add(self.practical_empirical_eval), self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception), self.practical_evidence_reject);
        } else if self.practical_candidate_valid && !self.probe_session {'''
new_ui='''        if self.practical_scan_enabled {
            pnp::println!("S720 PHASE SCAN");
            pnp::println!("A/r10 ONLY");
            pnp::println!("FR{} ADV{}", self.practical_live_checked, rng_advance().wrapping_sub(self.practical_live_start_advance));
        } else if self.practical_live_found_lane == 250 && !self.probe_session {
            pnp::println!("S720 PROBE A/r10");
            pnp::println!("UP+B DONOR");
        } else if self.practical_candidate_valid && !self.probe_session {'''
t=rep(t,old_ui,new_ui,'phase UI')
t=t.replace('pnp::println!("S719 TEST NO READY");','pnp::println!("S720 PHASE RUN");')
t=t.replace('pnp::println!("S719 IDLE");','pnp::println!("S720 IDLE");')

HOOK.write_text(h)
TRACE.write_text(t)
print('Applied Suicune v7.2.0 BranchPhase Probe: A/r10 actual-root donor scan + passive VBlank host-timing ring')
