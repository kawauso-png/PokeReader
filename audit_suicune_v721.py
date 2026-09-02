#!/usr/bin/env python3
from pathlib import Path
s=Path('reader_core/src/crystal/trace.rs').read_text()
req=[
'S721 MULTI PHASE','NOW {}/r{} L{}','TGT A3 A10 B1 B11 D12','RESET SUGGESTED',
'S721 PROBE {}/r{}','PHASESCAN,V721','PRECOUNT,V721','phase_counts: [u32; 64]',
'proto == b\'A\' && (rot == 3 || rot == 10)','proto == b\'B\' && (rot == 1 || rot == 11)',
'proto == b\'D\' && rot == 12','if lag != 0','practical_live_found_lane = 251',
'pre_vblank_timing_capture_stop()','BRPHASE,V720'
]
for x in req:
    if x not in s: raise SystemExit(f'v721 audit missing: {x}')
# Diagnostic monitor must not invoke shiny donor evaluators.
a=s.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader)')
b=s.index('    fn practical_fail(&mut self, code: u8)',a)
body=s[a:b]
for bad in ['practical::evaluate(', 'evaluate_exact(', 'evaluate_empirical(', 'bind_practical_prediction(']:
    if bad in body: raise SystemExit(f'v721 diagnostic monitor must not call {bad}')
# Do not regress to A/r10-only behavior.
if 'A/r10 ONLY' in s: raise SystemExit('v721 old A/r10-only UI remains')
# Timing ring must remain separate from production PRE ring.
h=Path('reader_core/src/crystal/hook.rs').read_text()
p0=h.index('pub struct PreVBlankRing')
p1=h.index('impl PreVBlankRing',p0)
if 'u64' in h[p0:p1] or 'a_tick' in h[p0:p1] or 'b_tick' in h[p0:p1]:
    raise SystemExit('v721 timing leaked into production PreVBlankRing')
print('AUDIT v7.2.1 PASS: multi-cell diagnostic targets, live identity, distribution export, no shiny evaluator')
