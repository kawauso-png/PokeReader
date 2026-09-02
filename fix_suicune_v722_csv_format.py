#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/trace.rs')
s=p.read_text()
old='PHASESCAN,V722,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n'
new='PHASESCAN,V722,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n'
if s.count(old)!=1:
    raise SystemExit(f'v722 format fix: expected 1 match, got {s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
print('Fixed v7.2.2 PHASESCAN format: 16 fields / 16 arguments')
