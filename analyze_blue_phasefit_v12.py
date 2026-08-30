#!/usr/bin/env python3
"""Fit JP VC Blue hidden DIV phase from ordinary ADD/SUB/DIV trace rows.

v12 intentionally needs no direct subtick address. It uses only observable
hRandomAdd/hRandomSub/rDIV transitions and the known LR35902 timing:
- frame: +17556 M = +274 DIV ticks and +20/64 subtick
- Random_ first->second read: 11 M
- normal first-read is around next sampled DIV +0x18/+0x19

The tool reports hidden phase fits and whether all surviving fits produce one
identical +1..+16F ordinary RNG path.
"""
from __future__ import annotations
import argparse, csv
from pathlib import Path

SUB=64
BASE=0x18


def h(s): return int(s,16)&0xff

def carry(a,b,c=0): return int(a+b+c>0xff)

def infer(a,b):
    a0,s0=h(a['rng_add']),h(a['rng_sub'])
    a1,s1=h(b['rng_add']),h(b['rng_sub'])
    first=(a1-a0)&0xff
    c=carry(a0,first,0)
    second=(s0-s1-c)&0xff
    gap=(second-first)&0xff
    if gap not in (0,1): return None
    return first,second,gap

def read_rows(path):
    lines=Path(path).read_text(encoding='utf-8-sig',errors='replace').splitlines()
    i=next(i for i,x in enumerate(lines) if x.startswith('seq,rel,'))
    out=[]
    for r in csv.DictReader(lines[i:]):
        s=(r.get('seq') or '').strip()
        if not s.isdigit(): break
        out.append(r)
    return out

def is_zero(r,k):
    v=(r.get(k) or '').strip()
    if not v:return True
    try:return int(v,16)==0
    except ValueError:return False

def transition(a,b):
    if int(b['seq']) != int(a['seq'])+1:return None
    if int(a.get('rel','0'))>=0 or int(b.get('rel','0'))>0:return None
    for k in ('joy_pressed','joy_held','phys_a','battle'):
        if not is_zero(a,k) or not is_zero(b,k):return None
    x=infer(a,b)
    if x is None:return None
    first,second,gap=x
    d0,d1=h(a['div']),h(b['div'])
    step=(d1-d0)&0xff
    off=(first-d1)&0xff
    if step not in (0x12,0x13) or off not in (0x18,0x19):return None
    return {'step':step,'off':off,'gap':gap}

def longest_block(rows):
    blocks=[]; cur=[]
    for i,(a,b) in enumerate(zip(rows,rows[1:])):
        tr=transition(a,b)
        if tr is None:
            if cur:blocks.append(cur);cur=[]
        else:cur.append((i,tr))
    if cur:blocks.append(cur)
    return max(blocks,key=len) if blocks else []

def fit(block):
    fits=[]
    for p0 in range(64):
        for offm in range(BASE*64-63,BASE*64+64):
            ok=True
            for j,(_,tr) in enumerate(block):
                p=(p0+20*j)&63
                if tr['step'] != 0x12 + int(p>=44):ok=False;break
                pn=(p+20)&63
                total=pn+offm
                if tr['off'] != total//64:ok=False;break
                fp=total%64
                if tr['gap'] != int(fp>=53):ok=False;break
            if ok:fits.append((p0,offm))
    return fits

def apply(add,sub,first,fp):
    second=(first+int(fp>=53))&0xff
    total=add+first
    c=int(total>0xff)
    return total&0xff,(sub-second-c)&0xff,second

def roll(row,p,offm,n=16):
    add,sub,div=h(row['rng_add']),h(row['rng_sub']),h(row['div'])
    out=[]
    for k in range(1,n+1):
        nd=(div+0x12+int(p>=44))&0xff
        pn=(p+20)&63
        total=pn+offm
        first=(nd+total//64)&0xff
        fp=total%64
        add,sub,second=apply(add,sub,first,fp)
        out.append((add,sub,nd,first,second))
        div,p=nd,pn
    return tuple(out)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('trace');ap.add_argument('--horizon',type=int,default=16)
    a=ap.parse_args();rows=read_rows(a.trace);block=longest_block(rows)
    print('pretrigger clean transitions:',len(block))
    if not block:return
    fits=fit(block);print('phase fits:',len(fits))
    print('fits:', ' '.join(f'p{p:02d}/o{o}' for p,o in fits[:32]))
    end_i=block[-1][0]+1
    end=rows[end_i]
    paths={}
    for p0,o in fits:
        p=(p0+20*len(block))&63
        path=roll(end,p,o,a.horizon)
        paths.setdefault(path,[]).append((p0,o))
    print(f'unique +1..+{a.horizon}F paths:',len(paths))
    if len(paths)==1:
        path=next(iter(paths))
        for i,(ad,su,di,r1,r2) in enumerate(path,1):
            print(f'+{i:02d} ADD={ad:02X} SUB={su:02X} DIV={di:02X} R={r1:02X}/{r2:02X}')

if __name__=='__main__':main()
