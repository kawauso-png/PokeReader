#!/usr/bin/env python3
from pathlib import Path
import re

p=Path('reader_core/src/crystal/practical.rs').read_text()
pat=re.compile(r"EmpLane\{id:(\d+),source:(\d+),pre_proto:b'([A-D])',pre_rot:(\d+),post_proto:b'([A-D])',post_rot:(\d+),route:(\d+),")
rows=[]
for m in pat.finditer(p):
    row=(int(m.group(1)),int(m.group(2)),m.group(3),int(m.group(4)),m.group(5),int(m.group(6)),int(m.group(7)))
    rows.append(row)
print('EMP_LANES',len(rows))
for r in rows:
    print('EMP',*r)
print('A10')
for r in rows:
    if r[2]=='A' and r[3]==10:
        print('A10LANE',*r)
