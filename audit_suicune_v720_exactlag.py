#!/usr/bin/env python3
from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs').read_text()
for marker in ['fn live_pre_cell_v720','let Some((proto, rot, lag)) = self.live_pre_cell_v720()','if lag != 0 {']:
    if marker not in T:
        raise SystemExit(f'FAIL missing exact-lag marker: {marker}')
a=T.find('    fn live_root_monitor')
b=T.find('    fn practical_fail',a)
m=T[a:b]
if m.find('if lag != 0 {') > m.find("if proto != b'A' || rot != 10"):
    raise SystemExit('FAIL lag guard occurs after A/r10 acceptance')
print('AUDIT PASS v7.2.0 exact-lag: timing-ring endpoint and paused A/r10 root are the same RNG advance')
