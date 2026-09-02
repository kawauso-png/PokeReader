#!/usr/bin/env python3
from pathlib import Path
import re,base64,zlib,json
s=Path('apply_suicune_stage3_v710.py').read_text()
m=re.search(r"DATA_B85='([^']+)'",s)
if not m: raise SystemExit('DATA_B85 not found')
d=json.loads(zlib.decompress(base64.b85decode(m.group(1))).decode())
out=[]
for x in d:
    out.append({k:x.get(k) for k in sorted(x.keys()) if k not in ('a','s')})
print(json.dumps(out,indent=2,sort_keys=True))
