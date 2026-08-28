#!/usr/bin/env python3
import csv, sys
from collections import Counter
from pathlib import Path

MOD = 16384
EXPECTED_FRAME_M = 1172
EXPECTED_PAIR_M = 11

def parse_int(s, base=10):
    return int(s, base)

def load_frames(path):
    lines = Path(path).read_text(errors='replace').splitlines()
    start = next(i for i,l in enumerate(lines) if l.startswith('frame,rel_adv,'))
    end = next((i for i in range(start+1,len(lines)) if not lines[i].strip()), len(lines))
    return list(csv.DictReader(lines[start:end]))

def counters(row):
    div = int(row['div'],16)
    ad = (div >> 8) & 0xff
    sd = div & 0xff
    a = ((ad << 6) | int(row['asub'],16)) % MOD
    s = ((sd << 6) | int(row['ssub'],16)) % MOD
    return a,s

def summarize(path):
    rows=load_frames(path)
    print(f'== {path} ==')
    print(f'frames: {len(rows)}')
    if not rows: return []
    pair=[]; astep=[]; sstep=[]; jitter=[]
    prev=None
    for r in rows:
        a,s=counters(r)
        pair.append((s-a)%MOD)
        if prev is not None:
            da=(a-prev[0])%MOD; ds=(s-prev[1])%MOD
            astep.append(da); sstep.append(ds); jitter.append(da-EXPECTED_FRAME_M)
        prev=(a,s)
    print('pair gap M most common:', Counter(pair).most_common(8))
    print('pair==11:', sum(x==EXPECTED_PAIR_M for x in pair), '/', len(pair))
    if astep:
        print('A step M: min/max/avg =', min(astep), max(astep), f'{sum(astep)/len(astep):.3f}')
        print('A jitter vs 1172:', Counter(jitter).most_common(12))
        print('S step M: min/max/avg =', min(sstep), max(sstep), f'{sum(sstep)/len(sstep):.3f}')
    bad=[(i,x) for i,x in enumerate(pair) if x!=EXPECTED_PAIR_M]
    if bad[:10]: print('first non-11 pair gaps:', bad[:10])
    return jitter

def compare(a,b):
    n=min(len(a),len(b))
    same=sum(a[i]==b[i] for i in range(n))
    print(f'jitter compare: {same}/{n} identical ({same/n*100:.2f}%)' if n else 'no comparable jitter rows')
    diffs=[(i,a[i],b[i]) for i in range(n) if a[i]!=b[i]]
    if diffs: print('first mismatches:', diffs[:20])

if __name__=='__main__':
    if len(sys.argv)<2:
        raise SystemExit('usage: analyze_div_subtick.py trace.csv [trace2.csv]')
    j1=summarize(sys.argv[1])
    if len(sys.argv)>=3:
        j2=summarize(sys.argv[2]); compare(j1,j2)
