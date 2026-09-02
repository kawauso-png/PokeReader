#!/usr/bin/env python3
from pathlib import Path
import re, json, zlib, base64

src = Path('apply_suicune_stage3_v710.py').read_text()
m = re.search(r"DATA_B85='([^']+)'", src)
if not m:
    raise SystemExit('DATA_B85 not found')
D = json.loads(zlib.decompress(base64.b85decode(m.group(1))).decode())
INC = [0x12,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13]
ADJ = {0x8,0x9,0x562,0x563,0x22b5,0x22b6}

def full_inc(i):
    i &= 0x3fff
    x = INC[i & 15]
    if i in ADJ:
        x = 0x13 if x == 0x12 else 0x12
    return x

def score(raw, idx, align):
    # Compare consecutive raw DIV offsets. align=0 means diff at rel k uses index+rel;
    # align=-1 means it uses index+rel-1. Ignore raw[0] because the root->rel0
    # convention differs across older generators.
    bad = 0
    for rel in range(1, len(raw)):
        obs = (raw[rel] - raw[rel-1]) & 0xff
        exp = full_inc(idx + rel + align)
        if obs != exp:
            bad += 1
            if bad > 3:
                break
    return bad

print('keys:', sorted(D[0].keys()))
for d in D:
    print('source', d['n'], 'pre', d['pp'], d['pr'], 'post', d['op'], d['or'], 'route', d['route'])
    for key in ('a','s'):
        raw=d[key]
        best=[]; bestscore=999
        for align in (0,-1):
            for idx in range(0x4000):
                sc=score(raw,idx,align)
                if sc<bestscore:
                    bestscore=sc; best=[(idx,align)]
                elif sc==bestscore and len(best)<32:
                    best.append((idx,align))
        print(' ', key, 'bestscore', bestscore, 'matches', len(best), 'sample', best[:16])
print('v7.1.2 empirical index inspection complete')
