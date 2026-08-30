#!/usr/bin/env python3
"""Suicune Exact-3F rel27 branch ranker v4.0.

Ranks historical stop1 branch centres from values known by Y+X arm time:
  1) (fixed_arm_tick-target_atick) mod T_REF
  2) Target advance mod 256
  3) Target AP4 low 6 bits

Current validated envelope: top 4 donor centres, each +/-255 M-cycles.
"""
from __future__ import annotations
import argparse,csv,math,statistics
from pathlib import Path

MOD=16384; FRAME=1172; T_REF=4481151; TOPK=4; WIDTH=255
P={
'A':[1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
'B':[-4,7,-3,0,-2,3,-1,2,1,-3,2,-1,-1,3,0,-3],
'C':[-2,1,1,-2,2,0,-1,0,1,-8,7,1,-4,4,0,0],
'D':[2,0,-2,2,-1,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
}

def hx(x): return int(x,16)
def read(path):
    ls=Path(path).read_text(errors='replace').splitlines()
    probe=next(csv.DictReader(ls[:2]))
    fs=next(i for i,x in enumerate(ls) if x.startswith('frame,rel_adv,'))
    fe=next((i for i in range(fs+1,len(ls)) if not ls[i].strip()),len(ls))
    frames=list(csv.DictReader(ls[fs:fe]))
    obs={}
    for i,x in enumerate(ls):
        if x.startswith('observe_version,'):
            obs=next(csv.DictReader(ls[i:i+2]));break
    return probe,frames,obs

def is3f(frames):
    k={}
    for r in frames:
        k.setdefault(int(r['rel_adv']),r['keys'].upper())
        if all(x in k for x in (0,1,2,3)): break
    return [k.get(x) for x in (0,1,2,3)]==['0040','0040','0040','0000']

def collapse(frames):
    out=[];i=0
    while i<len(frames):
        a=int(frames[i]['advance']);j=i+1
        while j<len(frames) and int(frames[j]['advance'])==a:j+=1
        out.append((a,frames[i],j-i));i=j
    return out

def jit(probe,groups):
    t=int(probe['target']);o={}
    for (a,r,n),(b,s,m) in zip(groups,groups[1:]):
        if n>1:continue
        o[a-t]=((hx(s['ap4'])-hx(r['ap4']))%MOD)-FRAME
    return o

def classify(j):
    fp=[j.get(x) for x in range(40,56)];best=None
    for name,p in P.items():
        for rot in range(16):
            score=sum(fp[i] is not None and fp[i]==p[(i+rot)%16] for i in range(16))
            c=(score,name,rot)
            if best is None or c>best:best=c
    return best

def expected(proto,rot,key): return P[proto][((key-40)+rot)%16]
def cell(proto,rot): return f'{proto}c{(rot+13)%16}'

def period(frames):
    ds=[]
    for a,b in zip(frames,frames[1:]):
        if int(b['rel_adv'])==int(a['rel_adv'])+1 and int(b['advance'])==int(a['advance'])+1:
            d=int(b['atick'])-int(a['atick'])
            if 3500000<d<5500000:ds.append(d)
    return int(statistics.median(ds)) if ds else 0

def parse(path):
    probe,frames,obs=read(path)
    if not is3f(frames):return None
    if obs.get('observe_version')!='V38':raise ValueError('V38 footer missing')
    g=collapse(frames);j=jit(probe,g);score,proto,rot=classify(j)
    rows={int(r['rel_adv']):r for _,r,_ in g}
    stop=next((int(r['rel_adv']) for _,r,n in g if int(r['rel_adv'])<100 and n>2),None)
    a=rows[stop];b=rows[stop+1]
    aj=((hx(b['ap4'])-hx(a['ap4']))%MOD)-FRAME
    sj=((hx(b['sp4'])-hx(a['sp4']))%MOD)-FRAME
    ex=expected(proto,rot,stop+1)
    return dict(name=Path(path).name,target=int(probe['target']),target_ap4=hx(probe['target_ap4']),
      target_atick=int(probe['target_atick']),fixed_arm_tick=int(obs['fixed_arm_tick']),
      cell=cell(proto,rot),score=score,stop=stop,aJ=aj,sJ=sj,branchA=aj-ex,branchS=sj-ex,
      offset=int(probe['offset']),route=int(probe['route']),raw=probe['raw_dv'],true_period=period(frames))

def circ(v,p):
    a=2*math.pi*v/p;return (math.sin(a),math.cos(a))
def vec(r,tref):
    d=(r['fixed_arm_tick']-r['target_atick'])%tref
    return circ(d,tref)+circ(r['target']&255,256)+circ(r['target_ap4']&63,64)
def dist(a,b):return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))
def rank(held,donors,tref):
    h=vec(held,tref)
    return sorted(((dist(h,vec(d,tref)),d) for d in donors),key=lambda x:(x[0],x[1]['name']))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('traces',nargs='+');ap.add_argument('--tref',type=int,default=T_REF);ap.add_argument('--top-k',type=int,default=TOPK);ap.add_argument('--width',type=int,default=WIDTH);a=ap.parse_args()
    runs=[]
    for p in a.traces:
        try:
            r=parse(p)
            if r:runs.append(r)
        except Exception as e:print('ERROR',p,e)
    runs.sort(key=lambda r:r['name'])
    print(f'Exact-3F={len(runs)} T_REF={a.tref} topK={a.top_k} width=+/-{a.width}M')
    print('trace,target,cell,fp,stop,J_A,J_S,branchA,offset,route,rawDV,true_period')
    for r in runs:print(f"{r['name']},{r['target']},{r['cell']},{r['score']}/16,{r['stop']},{r['aJ']},{r['sJ']},{r['branchA']},{r['offset']},{r['route']},{r['raw']},{r['true_period']}")
    print('\nLOO branch-centre ranking')
    passed=0;maxdiff=0
    for h in runs:
        top=rank(h,[d for d in runs if d is not h],a.tref)[:a.top_k]
        md=min(abs(d['aJ']-h['aJ']) for _,d in top);ok=md<=a.width;passed+=ok;maxdiff=max(maxdiff,md)
        names='/'.join(f"{d['name'].replace('celebi_trace_','').replace('.csv','')}:{d['aJ']}" for _,d in top)
        print(f"{h['name']}: {'PASS' if ok else 'FAIL'} min|dJ|={md} top={names}")
    print(f'=> {passed}/{len(runs)} PASS; max min|dJ|={maxdiff}')

if __name__=='__main__':main()
