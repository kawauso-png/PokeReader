#!/usr/bin/env python3
"""Suicune prototype/rotation analyzer v3.9.

Builds a low-dimensional empirical model from JP VC Crystal Suicune traces:
  * four 16-step micro-jitter prototypes (A/B/C/D)
  * best circular rotation and fingerprint score
  * structural/local-window mismatch statistics
  * exact replay profiles regenerated directly from each Trace CSV

The exact replay profile format is compatible with the historical v24 JS predictor,
but the analyzer groups profiles by prototype/rotation instead of pretending that
each whole-run profile is an independent physical family.
"""
from __future__ import annotations
import argparse, csv, json, hashlib
from collections import Counter
from pathlib import Path

MOD_M=16384
FRAME_M=1172
DIV_INC=[0x12,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13]
FP_START=40
FP_LEN=16
LOCAL_WINDOWS=[(220,269),(340,459),(520,559),(600,659)]
STABLE_RANGES=[(40,219),(270,339),(460,519),(560,599),(660,700)]
PROTOTYPES={
    "A":[1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
    "B":[-4,7,-3,0,-2,3,-1,2,1,-3,2,-1,-1,3,0,-3],
    "C":[-2,1,1,-2,2,0,-1,0,1,-8,7,1,-4,4,0,0],
    "D":[2,0,-2,2,-1,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
}

def hx(s): return int(s,16)
def signed8(v):
    v &= 0xff
    return v-256 if v>=128 else v

def div_delta(index,k):
    full,rem=divmod(k,16)
    total=full*sum(DIV_INC)
    i=index%16
    for t in range(rem): total += DIV_INC[(i+t)%16]
    return total & 0xff

def read_sections(path:Path):
    lines=path.read_text(errors='replace').splitlines()
    if not lines or not lines[0].startswith('probe,'): raise ValueError('probe header missing')
    probe=next(csv.DictReader(lines[:2]))
    fs=next(i for i,l in enumerate(lines) if l.startswith('frame,rel_adv,'))
    fe=next((i for i in range(fs+1,len(lines)) if not lines[i].strip()),len(lines))
    frames=list(csv.DictReader(lines[fs:fe]))
    try:
        cs=next(i for i,l in enumerate(lines) if l.startswith('call_index,'))
        ce=next((i for i in range(cs+1,len(lines)) if not lines[i].strip()),len(lines))
        calls=list(csv.DictReader(lines[cs:ce]))
    except StopIteration:
        calls=[]
    return probe,frames,calls

def collapse(frames):
    out=[];i=0
    while i<len(frames):
        adv=int(frames[i]['advance']);j=i+1
        while j<len(frames) and int(frames[j]['advance'])==adv:j+=1
        out.append((adv,frames[i],j-i));i=j
    return out

def jitter_map(probe,groups):
    target=int(probe['target']); out={}
    for (a,r,rep),(b,s,rep2) in zip(groups,groups[1:]):
        if rep>1: continue
        step=(hx(s['ap4'])-hx(r['ap4']))%MOD_M
        out[a-target]=step-FRAME_M
    return out

def stops(probe,groups):
    target=int(probe['target']);out=[]
    for (a,r,rep),(b,s,_) in zip(groups,groups[1:]):
        if rep<=1:continue
        step=(hx(s['ap4'])-hx(r['ap4']))%MOD_M
        out.append({'rel':a-target,'repeat':rep,'step_m':step,'extra_m':step-FRAME_M})
    return out

def fingerprint(jit): return [jit.get(r) for r in range(FP_START,FP_START+FP_LEN)]
def classify(fp):
    best=None
    for name,proto in PROTOTYPES.items():
        for rot in range(16):
            score=sum(fp[i] is not None and fp[i]==proto[(i+rot)%16] for i in range(16))
            cand=(score,name,rot)
            if best is None or cand>best:best=cand
    return {'score':best[0],'prototype':best[1],'rotation':best[2]}
def expected_jitter(proto,rot,rel): return PROTOTYPES[proto][((rel-FP_START)+rot)%16]
def local_stats(jit,cls):
    proto,rot=cls['prototype'],cls['rotation']
    def stat(lo,hi):
        pairs=[(r,jit[r],expected_jitter(proto,rot,r)) for r in range(lo,hi+1) if r in jit]
        same=sum(v==p for _,v,p in pairs)
        return {'lo':lo,'hi':hi,'same':same,'total':len(pairs),'pct':(same/len(pairs) if pairs else 0)}
    return [stat(*x) for x in STABLE_RANGES],[stat(*x) for x in LOCAL_WINDOWS]
def regular_residuals(probe,groups):
    target=int(probe['target']);div=hx(probe['target_div']);baseA=div>>8;baseS=div&255
    ai=int(probe['target_adiv']);si=int(probe['target_sdiv']);out={}
    for adv,row,rep in groups:
        k=adv-target
        if k<1:continue
        d=hx(row['div']);a=d>>8;s=d&255
        out[k]=(signed8(a-((baseA+div_delta(ai,k))&255)),signed8(s-((baseS+div_delta(si,k))&255)),rep)
    return out
def exact_profile(path,probe,groups,calls,cls):
    target=int(probe['target']);off=int(probe['offset']);route=int(probe['route'])
    div=hx(probe['target_div']);baseA=div>>8;baseS=div&255;ai=int(probe['target_adiv']);si=int(probe['target_sdiv'])
    resid=regular_residuals(probe,groups);flat=[]
    for k in range(2,off+1):
        if k not in resid: raise ValueError(f'missing regular advance k={k}')
        ra,rs,_=resid[k]; flat += [k,ra,k,rs]
    arows=[r for r in calls if r['pc'].upper()=='2F60' and int(r['advance'])==target+off]
    srows=[r for r in calls if r['pc'].upper()=='2F68' and int(r['advance'])==target+off]
    if len(arows)!=route or len(srows)!=route: raise ValueError(f'Random call count mismatch route={route}: {len(arows)}/{len(srows)}')
    ba=(baseA+div_delta(ai,off))&255;bs=(baseS+div_delta(si,off))&255
    for a,s in zip(arows,srows): flat += [off,signed8((hx(a['div'])&255)-ba),off,signed8((hx(s['div'])&255)-bs)]
    q=len(flat)//4
    return {'source':Path(path).stem.replace('celebi_trace_',''),'prototype':cls['prototype'],'rotation':cls['rotation'],'fp_score':cls['score'],'offset':off,'route':route,'flat':flat,'n1':q-1,'n2':q,'raw_dv':probe.get('raw_dv',''),'target':target,'target_state':probe.get('target_state',''),'target_div':probe.get('target_div',''),'target_adiv':int(probe['target_adiv']),'target_sdiv':int(probe['target_sdiv']),'target_ap4':probe.get('target_ap4',''),'target_sp4':probe.get('target_sp4',''),'target_asub':probe.get('target_asub',''),'target_ssub':probe.get('target_ssub',''),'phase_a':int(probe.get('phase_a') or 0),'phase_s':int(probe.get('phase_s') or 0)}
def branch_hash(jit,lo,hi):
    vals=[jit.get(r) for r in range(lo,hi+1)];blob=','.join('x' if v is None else str(v) for v in vals).encode();return hashlib.sha1(blob).hexdigest()[:8]
def analyze(path):
    probe,frames,calls=read_sections(path);groups=collapse(frames);jit=jitter_map(probe,groups);cls=classify(fingerprint(jit));stable,windows=local_stats(jit,cls)
    return {'path':str(path),'name':Path(path).name,'probe':probe,'jitter':jit,'class':cls,'stops':stops(probe,groups),'stable':stable,'windows':windows,'profile':exact_profile(path,probe,groups,calls,cls),'window_hashes':[branch_hash(jit,*w) for w in LOCAL_WINDOWS]}
def print_result(r):
    p=r['probe'];c=r['class'];stable_same=sum(x['same'] for x in r['stable']); stable_total=sum(x['total'] for x in r['stable']);win_same=sum(x['same'] for x in r['windows']); win_total=sum(x['total'] for x in r['windows'])
    print(f"{r['name']}: T{p['target']} root={p['target_state']}/{p['target_div']} AP4={p.get('target_ap4','')} P={c['prototype']} rot={c['rotation']:02d} fp={c['score']}/16 route={p.get('route')} DV={p.get('raw_dv')}")
    print(f"  stable {stable_same}/{stable_total}={100*stable_same/stable_total:.1f}%  local {win_same}/{win_total}={100*win_same/win_total:.1f}%  hashes={'/'.join(r['window_hashes'])}")
    print('  stops:', ', '.join(f"rel{s['rel']} x{s['repeat']} extra={s['extra_m']}M" for s in r['stops']))
def model_json(results): return {'version':'V39-PROTOTYPE-1','frame_m':FRAME_M,'mod_m':MOD_M,'fp_start':FP_START,'fp_len':FP_LEN,'prototypes':PROTOTYPES,'local_windows':LOCAL_WINDOWS,'stable_ranges':STABLE_RANGES,'profiles':[r['profile'] | {'window_hashes':r['window_hashes']} for r in results]}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('traces',nargs='+');ap.add_argument('--model-out');args=ap.parse_args();rs=[]
    for x in args.traces:
        try:r=analyze(Path(x));rs.append(r);print_result(r)
        except Exception as e:print(f'ERROR {x}: {e}')
    if not rs:raise SystemExit(2)
    print('\nprototype counts:',Counter(r['class']['prototype'] for r in rs));print('fingerprint score:',Counter(r['class']['score'] for r in rs))
    if args.model_out:Path(args.model_out).write_text(json.dumps(model_json(rs),ensure_ascii=False,separators=(',',':')));print('wrote',args.model_out)
if __name__=='__main__':main()
