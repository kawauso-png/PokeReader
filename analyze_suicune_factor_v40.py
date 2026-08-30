#!/usr/bin/env python3
"""
Suicune factor model v4.0 (JP VC Crystal, Exact-3F).

Validation-first offline model:
  * 16-step A/B/C/D backbone + corrected cell index
  * rel40 branch baseline grouped LOW/MID/HIGH
  * six DV-changing site windows
  * neutral carrier trajectory
  * stop2/tail donor
  * exact observed route3/route4 deep profiles (2F60/2F68)

The "core" predictor intentionally uses OBSERVED branch centers only.
The ±255 M-cycle envelope is a validation/coverage guard, not a production
search mode, because it creates too many raw-DV possibilities per Target.
"""
from __future__ import annotations
import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path

MOD=16384
FRAME=1172
SITES=[(217,273),(290,291),(339,377),(387,456),(521,567),(602,657)]
PROTOS={
"A":[1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
"B":[-4,7,-3,0,-2,3,-1,2,1,-3,2,-1,-1,3,0,-3],
"C":[-2,1,1,-2,2,0,-1,0,1,-8,7,1,-4,4,0,0],
"D":[2,0,-2,2,-1,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
}
VALIDATED_CELLS={"A13","D13"}

def hx(x): return int(x,16)
def smod(x,m=MOD):
    x%=m
    return x-m if x>=m//2 else x
def update(state,a,s):
    add=(state>>8)&255; sub=state&255
    z=add+a; carry=1 if z>255 else 0
    return ((z&255)<<8)|((sub-s-carry)&255)
def apply_sums(state,sum_a,sum_s):
    add=(state>>8)&255; sub=state&255
    total=add+sum_a
    return ((total&255)<<8)|((sub-sum_s-total//256)&255)
def shiny(raw):
    a=(raw>>12)&15; d=(raw>>8)&15; sp=(raw>>4)&15; sc=raw&15
    return d==10 and sp==10 and sc==10 and a in (2,3,6,7,10,11,14,15)

def read_sections(path):
    lines=Path(path).read_text(errors="replace").splitlines()
    probe=next(csv.DictReader(lines[:2]))
    fs=next(i for i,l in enumerate(lines) if l.startswith("frame,rel_adv,"))
    fe=next((i for i in range(fs+1,len(lines)) if not lines[i].strip()),len(lines))
    frames=list(csv.DictReader(lines[fs:fe]))
    cs=next(i for i,l in enumerate(lines) if l.startswith("call_index,"))
    ce=next((i for i in range(cs+1,len(lines)) if not lines[i].strip()),len(lines))
    calls=list(csv.DictReader(lines[cs:ce]))
    return probe,frames,calls

def collapse(frames):
    out=[]; i=0
    while i<len(frames):
        a=int(frames[i]["advance"]); j=i+1
        while j<len(frames) and int(frames[j]["advance"])==a: j+=1
        out.append((a,frames[i],j-i)); i=j
    return out

def jitter(probe,groups,field="ap4"):
    t=int(probe["target"]); out={}
    for (a,r,rep),(b,s,_) in zip(groups,groups[1:]):
        if rep>1: continue
        out[a-t]=((hx(s[field])-hx(r[field]))%MOD)-FRAME
    return out

def classify(jit):
    fp=[jit.get(k) for k in range(40,56)]
    best=(-1,None,None)
    for name,p in PROTOS.items():
        for rot in range(16):
            score=sum(fp[i] is not None and fp[i]==p[(i+rot)&15] for i in range(16))
            if score>best[0]: best=(score,name,rot)
    return best

def base_series(proto,rot,start,maxk=740):
    out={0:start}; cur=start
    for j in range(maxk):
        cur=(cur+FRAME+PROTOS[proto][((j-40)+rot)&15])%MOD
        out[j+1]=cur
    return out

def trace_record(path):
    probe,frames,calls=read_sections(path); groups=collapse(frames)
    ja=jitter(probe,groups,"ap4"); score,proto,rot=classify(ja)
    t=int(probe["target"]); off=int(probe["offset"])
    ba=base_series(proto,rot,hx(probe["target_ap4"]),max(740,off+2))
    bs=base_series(proto,rot,hx(probe["target_sp4"]),max(740,off+2))
    actual_a={a-t:hx(row["ap4"]) for a,row,_ in groups}
    actual_s={a-t:hx(row["sp4"]) for a,row,_ in groups}
    ca={k:smod(v-ba[k]) for k,v in actual_a.items() if k in ba}
    cs={k:smod(v-bs[k]) for k,v in actual_s.items() if k in bs}
    stops=[(a-t,rep) for a,row,rep in groups if rep>1]
    stop1=next(k for k,rep in stops if k<100)
    stop2=next(k for k,rep in stops if k>600)
    BA=ca[40]; BS=cs[40]
    fam="LOW" if BA<=100 else ("MID" if BA<=1000 else "HIGH")
    cell=f"{proto}{(rot+13)&15}"
    normal_a=actual_a[off]>>6; normal_s=actual_s[off]>>6
    ars=[r for r in calls if r["pc"].upper()=="2F60" and int(r["advance"])==t+off]
    srs=[r for r in calls if r["pc"].upper()=="2F68" and int(r["advance"])==t+off]
    deep_a=[(hx(r["div"])-normal_a)&255 for r in ars]
    deep_s=[(hx(r["div"])-normal_s)&255 for r in srs]
    return {
      "source":Path(path).stem.replace("celebi_trace_",""),
      "target":t,"target_state":probe["target_state"],"target_ap4":probe["target_ap4"],
      "target_sp4":probe["target_sp4"],"raw_dv":probe["raw_dv"],
      "score":score,"proto":proto,"rot":rot,"cell":cell,"family":fam,
      "BA":BA,"BS":BS,"stop1":stop1,"stop2":stop2,"off":off,
      "route":int(probe["route"]),"deep_a":deep_a,"deep_s":deep_s,
      "ca":[ca.get(k) for k in range(off+1)],
      "cs":[cs.get(k) for k in range(off+1)],
    }

def build_model(paths):
    runs=[trace_record(p) for p in paths]
    return {"version":"SUICUNE-FACTOR-V40-CORE1","frame_m":FRAME,"mod_m":MOD,
            "sites":SITES,"protos":PROTOS,"validated_cells":sorted(VALIDATED_CELLS),
            "runs":runs}

def pdiv(base,corr): return ((base+corr)%MOD)>>6

def deep_raw(state,last_a,last_s,deep_a,deep_s):
    hi=None
    for i,(oa,os) in enumerate(zip(deep_a,deep_s)):
        if i==len(deep_a)-1: hi=state&255
        state=update(state,(last_a+oa)&255,(last_s+os)&255)
    return (hi<<8)|(state&255)

def eval_target(model,state,ap4,sp4,cell):
    """Core observed-center factor enumeration for one target root."""
    rr=model["runs"]; same=[r for r in rr if r["cell"]==cell]
    if cell not in model["validated_cells"] or len(same)<3:
        return {}
    proto=cell[0]; corrected=int(cell[1:]); rot=(corrected-13)&15
    ba=base_series(proto,rot,ap4,740); bs=base_series(proto,rot,sp4,740)
    out=defaultdict(set)
    for pre in rr:
        BA,BS=pre["BA"],pre["BS"]
        preA=preS=0
        for k in range(1,41):
            preA+=pdiv(ba[k],pre["ca"][k]); preS+=pdiv(bs[k],pre["cs"][k])
        for car in same:
            deltas={(0,0)}
            for lo,hi in model["sites"]:
                carA=carS=0
                for k in range(lo,hi+1):
                    carA+=pdiv(ba[k],BA+(car["ca"][k]-car["BA"]))
                    carS+=pdiv(bs[k],BS+(car["cs"][k]-car["BS"]))
                opts=set()
                for d in same:
                    x=y=0
                    for k in range(lo,hi+1):
                        x+=pdiv(ba[k],BA+(d["ca"][k]-d["BA"]))
                        y+=pdiv(bs[k],BS+(d["cs"][k]-d["BS"]))
                    opts.add((x-carA,y-carS))
                deltas={(a+x,b+y) for a,b in deltas for x,y in opts}
            for tail in same:
                bodyA=bodyS=0
                for k in range(41,tail["stop2"]+1):
                    bodyA+=pdiv(ba[k],BA+(car["ca"][k]-car["BA"]))
                    bodyS+=pdiv(bs[k],BS+(car["cs"][k]-car["BS"]))
                tailA=tailS=0; lastA=lastS=0
                for k in range(tail["stop2"]+1,tail["off"]+1):
                    lastA=pdiv(ba[k],BA+(tail["ca"][k]-tail["BA"]))
                    lastS=pdiv(bs[k],BS+(tail["cs"][k]-tail["BS"]))
                    tailA+=lastA; tailS+=lastS
                for da,ds in deltas:
                    st=apply_sums(state,preA+bodyA+tailA+da,preS+bodyS+tailS+ds)
                    for deep in same:
                        raw=deep_raw(st,lastA,lastS,deep["deep_a"],deep["deep_s"])
                        out[raw].add((pre["family"],deep["route"],pre["source"],car["source"],tail["source"],deep["source"]))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("traces",nargs="+")
    ap.add_argument("--model-out")
    ap.add_argument("--eval",nargs=4,metavar=("STATE","AP4","SP4","CELL"))
    args=ap.parse_args()
    model=build_model(args.traces)
    print("runs",len(model["runs"]))
    print("cells",dict(Counter(r["cell"] for r in model["runs"])))
    print("families",dict(Counter(r["family"] for r in model["runs"])))
    if args.model_out:
        Path(args.model_out).write_text(json.dumps(model,separators=(",",":")))
        print("wrote",args.model_out)
    if args.eval:
        st,ap4,sp4,cell=args.eval
        pred=eval_target(model,hx(st),hx(ap4),hx(sp4),cell)
        shiny_rows=[(raw,len(tags),sorted({x[0] for x in tags}),sorted({x[1] for x in tags}))
                    for raw,tags in pred.items() if shiny(raw)]
        print("raw candidates",len(pred),"shiny",len(shiny_rows))
        for row in shiny_rows[:100]:
            print(f"{row[0]:04X} support={row[1]} family={row[2]} route={row[3]}")
if __name__=="__main__": main()
