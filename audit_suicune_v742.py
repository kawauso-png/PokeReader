#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(x,msg):
    if not x: raise SystemExit('v742 audit FAIL: '+msg)

# v7.4.1 absolute START M0 must survive unchanged.
need('const u32 wanted_start_cycle = 0U;' in m,'absolute START M0 missing')
need('while (((u32)cycle & 15U) != wanted_start_cycle) cycle++;' in m,'START mod16 wait missing')
need('suicune_start_phase_slot = wanted_start_cycle;' in m,'START slot stamp missing')

# Full 16-phase resume actuator.
need('suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending' in m,'READY-gated resume selector missing')
need('suicune_phase_slot = (suicune_phase_slot + 1U) & 15U;' in m,'X +1 full16 missing')
need('suicune_phase_slot = (suicune_phase_slot + 15U) & 15U;' in m,'Y -1 full16 missing')
need('u32 wanted = suicune_phase_slot & 15U;' in m,'full resume wanted mod16 missing')
need('while (((u32)cycle & 15U) != wanted) cycle++;' in m,'resume absolute mod16 wait missing')
need('cycle += 16ULL;' in m,'resume 16-cycle rollover missing')

# Preserve causal transport.
need('suicune_wait_up_after_b = true;' in m,'B->release->UP TwoStageArm lost')
need('if (suicune_phase_slot >= 8U) suicune_phase_slot = 0U;' in m,'sweep READY base M0 reset missing')
need('SUICUNE_ROOT_LOCK_MAX_STEPS 200000U' in m,'root-lock watchdog missing')

# User-visible status and actual telemetry.
need('S742 B{} TURBO' in p and 'S742 B{} SWEEP FOUND' in p,'v742 UI missing')
need('RESUME M{:02} X+1 Y-1' in p,'dynamic M0..M15 UI missing')
need('SWEEP,V742' in p,'v742 CSV row missing')
need('wanted_resume_mod16' in p and 'actual_resume_mod16' in p,'full resume CSV columns missing')
need('resume_remainder' in p and 'resume_error_ticks' in p,'resume boundary diagnostics missing')
need('start_cycle_mod16' in p and 'start_remainder' in p,'absolute START diagnostics lost')
need('let sweep_post=classify_post_entries(self.entries,self.len,self.probe_target.advance);' in p,'actual POST classifier lost')

print('v7.4.2 audit PASS: START M0 fixed; full Resume M0..M15 actuator; actual POST/DV telemetry; TwoStage retained')
