#!/usr/bin/env python3
from pathlib import Path
H=Path('reader_core/src/crystal/hook.rs')
h=H.read_text()
old='''        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;'''
new='''        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;\n        RDIV_ANY_WRITE_V750=0;\n        RDIV_ANY_COUNT_V750=0;'''
for fn,next_fn in [('pub fn deep_log_start()','pub fn deep_log_stop()'),('pub fn deep_log_clear()','pub fn deep_log_count()')]:
    a=h.find(fn); b=h.find(next_fn,a)
    if a<0 or b<0: raise SystemExit('v750 reset function range missing')
    seg=h[a:b]
    if 'RDIV_ANY_COUNT_V750=0;' in seg: continue
    if old not in seg: raise SystemExit('v750 reset anchor missing in '+fn)
    seg=seg.replace(old,new,1)
    h=h[:a]+seg+h[b:]
H.write_text(h)
print('Pre-seeded v7.5.0 broad-ring reset anchors')
