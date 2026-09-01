#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/trace.rs')
t=p.read_text()
for needle in ['fn practical_wait_monitor', 'practical_search_error = 4', 'practical_skipped', 'S64 ERR']:
    print('\n===== ',needle,' =====')
    pos=t.find(needle)
    if pos<0:
        print('NOT FOUND')
        continue
    lo=max(0,pos-1800); hi=min(len(t),pos+4200)
    print(t[lo:hi])
