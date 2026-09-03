#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(x,msg):
    if not x: raise SystemExit('v740 audit FAIL: '+msg)

start=t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
end=t.index('\n    fn practical_fail',start)
seg=t[start:end]
need('if rot!=10 { return; }' in seg,'live scan is not A/r10-only')
need('evaluate_adaptive_bucket(' in seg and '6144' in seg,'live R16 confidence evaluator missing')
need('bind_practical_prediction' not in seg,'live scan binds prediction before frozen recheck')
need('self.practical_live_found_lane=253;' in seg,'turbo candidate does not request authoritative pause-root path')
need('self.practical_candidate_valid=false;' in seg,'live candidate exposed as valid before recheck')
need('self.bucket_scan_steps=6144;' in seg,'pause-side R16 envelope not primed')
need('pnp::request_pause();' in seg,'live candidate never requests pause')

cstart=t.index('    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {')
cend=t.index('\n    pub fn status_line',cstart)
cseg=t[cstart:cend]
need('self.turbo_freeze_delta=cur.wrapping_sub(self.turbo_candidate_advance);' in cseg,'freeze delta diagnostic missing')
need('self.turbo_recheck_count=self.turbo_recheck_count.saturating_add(1);' in cseg,'frozen recheck accounting missing')
need('evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div()' in cseg,'authoritative frozen evaluator missing')
need('self.bind_practical_prediction(bp.prediction);' in cseg,'frozen successful recheck does not bind prediction')
need('out|=1u32<<27;' in cseg,'frozen shiny_ready bit missing')
need('self.turbo_recheck_miss=self.turbo_recheck_miss.saturating_add(1);' in cseg,'failed frozen recheck not tracked')

# Retain final v738 model safety properties.
pstart=p.index('pub fn evaluate_adaptive_bucket(')
pend=p.index('\n}',pstart)+2
pseg=p[pstart:pend]
need('ai==0 || si==0 || !empirical_window_safe(ai,si)' in pseg,'tracker safety guard lost')
need('if DEEP_A[i] == l.primary_a && DEEP_S[i] == l.primary_s { continue; }' in pseg,'deep dedup lost')
need('d<=4' in pseg and 'd<=8' in pseg and 'd<=16' in pseg,'distance confidence gate lost')
need('false' in pseg[pseg.index('let accept='):pseg.index('if !accept')],'distance >16 rejection lost')

# Host must still require frozen shiny_ready before arm, preserve two-stage input
# and absolute SLOT1 behavior.
need('bool shiny_ready = (cell & 0x08000000U) != 0;' in m,'C shiny_ready decode missing')
need("if (shiny_ready && valid && bucket_valid && proto == (u32)'A' && rot == 10U)" in m,'C frozen root lock gate missing')
need('suicune_wait_up_after_b = true;' in m and 'if (suicune_wait_up_after_b)' in m,'B->release->UP TwoStageArm lost')
need('suicune_phase_slot = 1;' in m,'SLOT1 fixed path lost')
need('S740 TURBO SHINY' in t and 'S740 SHINY LOCK' in t and 'S740 TURBO RECHECK' in t,'v740 UI markers missing')
need('TURBO,V740' in t and 'BUCKET740,V740' in t,'v740 CSV diagnostics missing')
print('v7.4.0 audit PASS: free-run A/r10 scan, frozen-root recheck, v738 confidence safety, TwoStage/SLOT1 retained')
