#!/usr/bin/env python3
from pathlib import Path
s=Path('reader_core/src/crystal/trace.rs').read_text()
req=[
 'S722 ADAPTIVE PHASE','FALLBACK ANY EXACT','self.practical_live_checked>=3000',
 'self.phase_best_score=best','self.phase_target_count','self.practical_live_index_wait',
 'self.practical_live_found_lane=252','PHASESCAN,V722','PRECOUNT,V722',
 'pnp::request_pause()'
]
for x in req:
    if x not in s: raise SystemExit('v722 audit missing: '+x)
# Pause must not require a shiny evaluator/prediction.
mon=s[s.find('    fn live_root_monitor'):s.find('    fn practical_fail',s.find('    fn live_root_monitor'))]
for bad in ['evaluate_empirical(','evaluate_exact(','bind_practical_prediction(']:
    if bad in mon: raise SystemExit('v722 audit production evaluator leaked into probe: '+bad)
print('v7.2.2 adaptive probe audit PASS')
