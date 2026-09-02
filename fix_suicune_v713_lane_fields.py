#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs')
s=p.read_text()
old="if id>=1&&id<=LANE_COUNT{let l=lane(id);return Some((l.pre_proto,l.pre_rot))}"
new="if id>=1&&id<=LANE_COUNT{let l=lane(id);return Some((l.proto,l.rot))}"
if s.count(old)!=1:
    raise SystemExit(f'v713 lane field fix expected 1 match, found {s.count(old)}')
p.write_text(s.replace(old,new,1))
print('Fixed v7.1.3 proven Lane PRE fields: proto/rot')
