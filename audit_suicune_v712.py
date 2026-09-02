#!/usr/bin/env python3
from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
t=T.read_text()

def need(x,label):
    if x not in t: raise SystemExit('missing '+label)
def forbid(x,label):
    if x in t: raise SystemExit('forbidden '+label)

need('S712 SCAN','S712 scan')
need('"FR{} ADV{}"','actionable/root counter labels')
need('"P{} X{}"','PRE coverage counters')
need('"EV{} SK{}"','evaluation/skip counters')
need('self.practical_live_checked','actionable frame counter')
need('rng_advance().wrapping_sub(self.practical_live_start_advance)','advance delta')
need('self.practical_empirical_cell_frames','empirical PRE hit counter')
need('self.practical_live_exact_eval.saturating_add(self.practical_empirical_eval)','combined eval counter')
need('self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception)','combined skip counter')
need('fn practical_wait_monitor','live monitor retained')
need('practical::evaluate_exact','exact proven evaluator retained')
need('practical::evaluate_empirical','empirical evaluator retained')
need('self.practical_expected40_state','rel40 hard guard retained')
need('self.practical_expected716_state','rel716 hard guard retained')
need('self.practical_expected717_state','rel717 hard guard retained')
need('STAGE3,V710','stage3 telemetry retained')
need('BRANCH710,V710','branch telemetry retained')
need('S712 READY UP+B','READY UI bumped')
need('S712 LEARN D15','D15 learn UI bumped')
need('S658 TEST','fast validate retained')
forbid('S711 ','stale S711 UI')
forbid('"A{} C{} P{}"','ambiguous old scan labels')
print('v7.1.2 AUDIT PASS: FR/ADV semantics explicit; v7.1 exact/empirical search and hard guards retained')
