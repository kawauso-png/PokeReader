#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/trace.rs')
s=p.read_text()
old='BENCH,V744,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X}'
new='BENCH,V744,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X}'
if s.count(old)!=1:
    raise SystemExit(f'v744 csv format anchor count {s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
print('Fixed v7.4.4 BENCH CSV format: 26 fields / 26 arguments')
