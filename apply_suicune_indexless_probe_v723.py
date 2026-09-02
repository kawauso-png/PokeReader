#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/trace.rs')
s = P.read_text()


def rep(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'v723 {label}: expected 1 match, got {n}')
    s = s.replace(old, new, 1)

# v7.2.3: the diagnostic BranchPhase probe does not consume Add/Sub tracker
# indices.  arm_suicune_probe() already captures current indices with
# unwrap_or(0), and the phase/POST/DV trace does not need a pre-pause index.
# Keeping this gate in the scanner caused valid exact roots to be rejected
# indefinitely when AI/SI were WAIT.
old = '''        let Some(ai0)=add_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1); return;
        };
        let Some(si0)=sub_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1); return;
        };
        let ai=(ai0 as u32)&0x3fff; let si=(si0 as u32)&0x3fff;
        self.practical_live_lane_frames=self.practical_live_lane_frames.saturating_add(1);
        self.phase_target_proto=proto0; self.phase_target_rot=rot;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=252;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai; self.practical_live_found_si=si;
        self.practical_live_scan=false; self.practical_scan_enabled=false;
        pre_vblank_timing_capture_stop();
        self.practical_candidate_valid=false; self.practical_active=false;
        pnp::request_pause();'''
new = '''        // Diagnostic capture is intentionally indexless.  The selected current
        // root is already exact (best=0, lag=0); AI/SI are not needed to pause
        // or to record BRPHASE -> POST -> route -> DV.
        self.practical_live_lane_frames=self.practical_live_lane_frames.saturating_add(1);
        self.phase_target_proto=proto0; self.phase_target_rot=rot;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=253;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=0; self.practical_live_found_si=0;
        self.practical_live_scan=false; self.practical_scan_enabled=false;
        pre_vblank_timing_capture_stop();
        self.practical_candidate_valid=false; self.practical_active=false;
        pnp::request_pause();'''
rep(old, new, 'remove scan index gate')

# Version the exported diagnostic rows so mixed v7.2 datasets remain explicit.
s = s.replace('PHASESCAN,V722', 'PHASESCAN,V723')
s = s.replace('PRECOUNT,V722', 'PRECOUNT,V723')

# Compact UI: no misleading IW counter because this scanner no longer waits on
# tracker indices.  Preserve priority-first / fallback-after-3000 behavior.
rep('''            pnp::println!("S722 ADAPTIVE PHASE");''',
    '''            pnp::println!("S723 INDEXLESS");''', 'scan title')
rep('''            pnp::println!("FR{} EX{} TG{} IW{}", self.practical_live_checked, self.phase_exact_count, self.phase_target_count, self.practical_live_index_wait);''',
    '''            pnp::println!("FR{} EX{} TG{}", self.practical_live_checked, self.phase_exact_count, self.phase_target_count);''', 'scan counters')
rep('''        } else if self.practical_live_found_lane == 252 && !self.probe_session {
            pnp::println!("S722 PROBE {}/r{}", self.phase_target_proto as char, self.phase_target_rot);''',
    '''        } else if self.practical_live_found_lane == 253 && !self.probe_session {
            pnp::println!("S723 PROBE {}/r{}", self.phase_target_proto as char, self.phase_target_rot);''', 'probe sentinel UI')
s = s.replace('S722 PHASE RUN', 'S723 PHASE RUN').replace('S722 IDLE', 'S723 IDLE')

P.write_text(s)
print('Applied v7.2.3 Indexless Phase Probe: diagnostic scan no longer depends on AI/SI tracker indices')
