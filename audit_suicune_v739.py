#!/usr/bin/env python3
from pathlib import Path

t=Path('reader_core/src/crystal/trace.rs').read_text()

def need(x,msg):
    if not x: raise SystemExit('v739 audit FAIL: '+msg)

need('S739 TURBO PHASE' in t and 'S739 TURBO DONE' in t,'turbo UI missing')
need('turbo_a10_count' in t and 'turbo_freeze_delta' in t,'turbo state missing')
start=t.index('fn live_root_monitor')
end=t.index('fn practical_fail',start)
seg=t[start:end]
need('if rot!=10 { return; }' in seg,'A/r10 filter missing')
need('let da=cur.wrapping_sub(self.turbo_last_advance);' in seg,'advance delta missing')
need('let db=bucket.wrapping_sub(self.turbo_last_bucket);' in seg,'bucket delta missing')
need('if da==16 && db==37' in seg,'+16/+37 hypothesis test missing')
need('self.turbo_a10_count>=64' in seg,'64-sample stop missing')
need('self.practical_live_found_lane=252' in seg,'diagnostic completion lane missing')
# The only request_pause in the A path must be the 64-sample terminal pause.
a=seg.index('if proto0!=b\'A\'')
a_seg=seg[a:]
need(a_seg.count('pnp::request_pause()')==2,'unexpected A-path pause added (expected non-A reset + terminal probe only)')
need('self.turbo_freeze_delta=cur.wrapping_sub(self.practical_live_found_advance);' in t,'freeze delta capture missing')
need('B ARM -> UP' in t,'production code unexpectedly removed; dedicated lane252 must simply not enter it')
print('v7.3.9 audit PASS: free-running A/r10 recurrence probe, 64 samples, +16/+37 metrics, freeze delta; no encounter arm on lane252')
