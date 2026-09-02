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
# Keep the production PRE classifier ring byte-for-byte unchanged.  Timing is
# collected in a separate ring only while the diagnostic scan is active.  The
# rDIV hook already sampled `host_tick`; this patch only stores that existing
# value. No extra timer/DIV/RNG/emulator-memory read is introduced.
# ---------------------------------------------------------------------------

# Separate timing ring.  It is deliberately NOT embedded in PreVBlankRing,
# because live_pre_cell() copies PreVBlankRing by value on every actionable
# root. Enlarging it would perturb the production scan cadence.
h=rep(h,
'''static mut PRE_VBLANK_RING: PreVBlankRing = PreVBlankRing::EMPTY;

pub fn latest_pre_vblank_ring() -> PreVBlankRing {
    unsafe { PRE_VBLANK_RING }
}

fn push_pre_vblank_sample(advance: u32, div: u8, mcycle: u8) {''',
'''static mut PRE_VBLANK_RING: PreVBlankRing = PreVBlankRing::EMPTY;

#[derive(Clone, Copy)]
pub struct PreVBlankTimingRing {
    pub count: u8,
    pub write: u8,
    pub a_tick: [u64; PRE_VBLANK_RING_LEN],
    pub b_tick: [u64; PRE_VBLANK_RING_LEN],
}

impl PreVBlankTimingRing {
    pub const EMPTY: Self = Self {
        count: 0,
        write: 0,
        a_tick: [0; PRE_VBLANK_RING_LEN],
        b_tick: [0; PRE_VBLANK_RING_LEN],
    };
}

static mut PRE_VBLANK_TIMING_RING: PreVBlankTimingRing = PreVBlankTimingRing::EMPTY;
static mut PRE_VBLANK_TIMING_CAPTURE: bool = false;
static mut PRE_VBLANK_TIMING_LAST_SLOT: u8 = 0xff;

pub fn latest_pre_vblank_ring() -> PreVBlankRing {
    unsafe { PRE_VBLANK_RING }
}

pub fn latest_pre_vblank_timing_ring() -> PreVBlankTimingRing {
    unsafe { PRE_VBLANK_TIMING_RING }
}

pub fn pre_vblank_timing_capture_start() {
    unsafe {
        PRE_VBLANK_TIMING_RING = PreVBlankTimingRing::EMPTY;
        PRE_VBLANK_TIMING_LAST_SLOT = 0xff;
        PRE_VBLANK_TIMING_CAPTURE = true;
    }
}

pub fn pre_vblank_timing_capture_stop() {
    unsafe { PRE_VBLANK_TIMING_CAPTURE = false; }
}

fn push_pre_vblank_sample(advance: u32, div: u8, mcycle: u8, host_tick: u64) {''','separate timing ring')

# Add two static stores to the already-existing A hook only while the probe
# scan is active. AA/AB deltas are computed later, after the game is frozen.
h=rep(h,
'''fn push_pre_vblank_sample(advance: u32, div: u8, mcycle: u8, host_tick: u64) {
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
        if PRE_VBLANK_TIMING_CAPTURE {
            let ti = PRE_VBLANK_TIMING_RING.write as usize;
            PRE_VBLANK_TIMING_RING.a_tick[ti] = host_tick;
            PRE_VBLANK_TIMING_RING.b_tick[ti] = 0;
            PRE_VBLANK_TIMING_LAST_SLOT = ti as u8;
            PRE_VBLANK_TIMING_RING.write =
                ((ti + 1) % PRE_VBLANK_RING_LEN) as u8;
            if (PRE_VBLANK_TIMING_RING.count as usize) < PRE_VBLANK_RING_LEN {
                PRE_VBLANK_TIMING_RING.count += 1;
            }
        }

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
}

fn finish_pre_vblank_timing_sample(host_tick: u64) {
    unsafe {
        if !PRE_VBLANK_TIMING_CAPTURE || PRE_VBLANK_TIMING_LAST_SLOT == 0xff {
            return;
        }
        PRE_VBLANK_TIMING_RING.b_tick[PRE_VBLANK_TIMING_LAST_SLOT as usize] = host_tick;
    }
}''','passive A/B timing stores')

h=rep(h,
'''        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle);''',
'''        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle, host_tick);''','A timing call')

h=rep(h,
'''    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();''',
'''    if RNG_DIV_READ_2.contains(&pc) {
        finish_pre_vblank_timing_sample(host_tick);
        let div = reader.div();''','B timing completion')

# Import and persist the separate timing snapshot only when UP+B arms the run.
t=rep(t,
'''    set_vblank_context_capture,
    latest_pre_vblank_ring, PreVBlankRing, PRE_VBLANK_RING_LEN,
};''',
'''    set_vblank_context_capture,
    latest_pre_vblank_ring, latest_pre_vblank_timing_ring,
    pre_vblank_timing_capture_start, pre_vblank_timing_capture_stop,
    PreVBlankRing, PreVBlankTimingRing, PRE_VBLANK_RING_LEN,
};''','timing imports')

t=rep(t,
'''    pre_vblank_ring: PreVBlankRing,
    // Timing-compat observation retained because current donor/model data was captured''',
'''    pre_vblank_ring: PreVBlankRing,
    pre_vblank_timing_ring: PreVBlankTimingRing,
    // Timing-compat observation retained because current donor/model data was captured''','Trace timing field')

t=rep(t,
'''            pre_vblank_ring: PreVBlankRing::EMPTY,
            early_rel26_count: 0,''',
'''            pre_vblank_ring: PreVBlankRing::EMPTY,
            pre_vblank_timing_ring: PreVBlankTimingRing::EMPTY,
            early_rel26_count: 0,''','Trace timing default')

# Start timing capture with the diagnostic epoch. It is reset here, so require
# 17 newly observed roots before accepting A/r10; this guarantees the timing
# ring and the production PRE ring describe the same 17 post-start samples.
t=rep(t,
'''        self.practical_rebound = false;

        // v7.1.8: actual-root scan only. There is no future target queue,
        // search horizon, rolling re-root transport, or open-loop wait.
        self.practical_scan_enabled = true;''',
'''        self.practical_rebound = false;
        pre_vblank_timing_capture_start();

        // v7.2.0 diagnostic build: actual-root A/r10 BranchPhase scan only.
        // No shiny READY is produced by this build.
        self.practical_scan_enabled = true;''','start timing epoch')

# Snapshot timing after capture has already been stopped at the selected root.
t=rep(t,
'''        set_vblank_context_capture(false);
        self.pre_vblank_ring = latest_pre_vblank_ring();
        self.probe_target = ProbeTarget {''',
'''        set_vblank_context_capture(false);
        self.pre_vblank_ring = latest_pre_vblank_ring();
        self.pre_vblank_timing_ring = latest_pre_vblank_timing_ring();
        self.probe_target = ProbeTarget {''','arm timing snapshot')

# Replace production predictor portion of live_root_monitor with the diagnostic
# exact A/r10 gate. All de-duplication and PRE classification before this span
# remains unchanged.
start=t.find('        let proven = practical::lane_for_pre(proto, rot);')
end=t.find('    fn practical_fail(&mut self, code: u8)', start)
if start<0 or end<0:
    raise SystemExit('v720 live monitor body anchors missing')
new='''        // Wait until 17 new post-start roots have filled the separate timing
        // ring. This avoids mixing pre-scan timing with the selected PRE cell.
        if self.practical_live_checked < PRE_VBLANK_RING_LEN as u32 {
            return;
        }

        // A/r10 currently has the richest one-to-many POST evidence. Do not
        // evaluate any shiny donor here; this build is phase collection only.
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
        pre_vblank_timing_capture_stop();
        self.practical_candidate_valid = false;
        self.practical_active = false;
        pnp::request_pause();
    }

'''
t=t[:start]+new+t[end:]

# CSV: compute AA/AB deltas offline from the frozen timing snapshot. No delta
# arithmetic is performed in the rDIV hook itself.
needle='''            let _ = write!(line, "\n\n");
            pnp::trace_file_write(line.as_bytes());
        }


        // v6.3 authoritative suffix fingerprint.'''
insert='''            let _ = write!(line, "\n\n");
            pnp::trace_file_write(line.as_bytes());

            let tr = self.pre_vblank_timing_ring;
            let tc = (tr.count as usize).min(PRE_VBLANK_RING_LEN);
            let ts = if tc == PRE_VBLANK_RING_LEN { tr.write as usize } else { 0 };
            line.clear();
            let _ = write!(line, "branch_phase,version,index,advance,phase,a_tick,b_tick,aa_delta,ab_delta\n");
            pnp::trace_file_write(line.as_bytes());
            let mut prev_a = 0u64;
            for i in 0..count.min(tc) {
                let (adv, phase) = pre_ring_sample(&r, i);
                let ti = (ts + i) % PRE_VBLANK_RING_LEN;
                let a = tr.a_tick[ti];
                let b = tr.b_tick[ti];
                let aa = if prev_a != 0 { a.saturating_sub(prev_a) } else { 0 };
                let ab = if b >= a { b - a } else { 0 };
                prev_a = a;
                line.clear();
                let _ = write!(line, "BRPHASE,V720,{},{},{:04X},{},{},{},{}\n", i, adv, phase, a, b, aa, ab);
                pnp::trace_file_write(line.as_bytes());
            }
            line.clear();
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());
        }


        // v6.3 authoritative suffix fingerprint.'''
t=rep(t,needle,insert,'BRPHASE CSV')

# Dedicated diagnostic UI. The physical UP+B/Exact2F execution path is unchanged.
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
print('Applied Suicune v7.2.0 BranchPhase Probe: slim PRE classifier + separate gated host-timing ring + A/r10 donor scan')
