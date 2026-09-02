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

def normal_inc(i):
    return INC[i & 15]

def full_inc(i):
    i &= 0x3fff
    x = normal_inc(i)
    if i in ADJ:
        x = 0x13 if x == 0x12 else 0x12
    return x

def mismatch_info(raw, idx, align, full=True):
    bad=[]
    for rel in range(1,len(raw)):
        obs=(raw[rel]-raw[rel-1])&0xff
        exp=(full_inc if full else normal_inc)(idx+rel+align)
        if obs!=exp:
            bad.append((rel,obs,exp))
    return bad

print('keys:', sorted(D[0].keys()))
for d in D:
    print('source',d['n'],'pre',d['pp'],d['pr'],'post',d['op'],d['or'],'route',d['route'])
    for key in ('a','s'):
        raw=d[key]
        ranked=[]
        # Full absolute-index candidates. Keep exact score for all 0x4000*2 alignments.
        for align in (0,-1):
            for idx in range(0x4000):
                bad=mismatch_info(raw,idx,align,True)
                ranked.append((len(bad),idx,align,bad[:12]))
        ranked.sort(key=lambda x:(x[0],x[1],x[2]))
        bestscore=ranked[0][0]
        best=[x for x in ranked if x[0]==bestscore]
        # Also infer the best nominal mod16 phase; this is enough to recover the donor
        # exception residual directly from the empirical raw path if absolute index is ambiguous.
        nom=[]
        for align in (0,-1):
            for phase in range(16):
                bad=mismatch_info(raw,phase,align,False)
                nom.append((len(bad),phase,align,bad[:20]))
        nom.sort(key=lambda x:(x[0],x[1],x[2]))
        print(' ',key,'full bestscore',bestscore,'best_count',len(best),'best_sample',[(x[1],x[2]) for x in best[:20]])
        print(' ',key,'full mismatch sample',best[0][3])
        print(' ',key,'nominal best',nom[0][0:3],'nom mismatch sample',nom[0][3])
print('v7.1.2 empirical index inspection complete')
