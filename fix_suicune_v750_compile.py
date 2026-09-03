#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/hook.rs')
s=p.read_text()
old='state:reader.rng_state(),add:reader.rng_add(),sub:reader.rng_sub(),'
new='state:reader.rng_state(),add:0,sub:0,'
if old in s:
    s=s.replace(old,new,1)
elif new not in s:
    raise SystemExit('v750 compile field anchor missing')
p.write_text(s)
print('Fixed v7.5.0 RDIVANY optional add/sub fields')
