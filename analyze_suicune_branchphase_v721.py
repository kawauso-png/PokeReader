#!/usr/bin/env python3
from pathlib import Path
import csv, sys, statistics


def rows(path):
    out=[]
    for line in path.read_text(errors='replace').splitlines():
        try: r=next(csv.reader([line]))
        except Exception: continue
        if r: out.append(r)
    return out


def first(rs, tag):
    for r in rs:
        if r and r[0]==tag: return r
    return None


def alltag(rs, tag): return [r for r in rs if r and r[0]==tag]

def dec(x, d=0):
    try:return int(x)
    except:return d

def hexi(x,d=0):
    try:return int(x,16)
    except:return d


def summarize(path):
    rs=rows(path)
    su=first(rs,'SUICUNE'); pre=first(rs,'PREFP'); post=first(rs,'POSTFP')
    live=first(rs,'LIVE_SCAN'); early=first(rs,'EARLY'); v38=first(rs,'V38')
    livep=first(rs,'LIVE'); end=first(rs,'ENDPOINT'); scan=first(rs,'PHASESCAN')
    bp=alltag(rs,'BRPHASE'); fast=alltag(rs,'FASTCALL')
    aa=[dec(r[7]) for r in bp[1:] if len(r)>8 and dec(r[7])>0]
    ab=[dec(r[8]) for r in bp if len(r)>8 and dec(r[8])>0]
    medaa=int(statistics.median(aa)) if aa else 0
    double=sum(1 for x in aa if medaa and x>medaa*3//2)
    bigab=sum(1 for x in ab if x>30000)
    return {
      'file':path.name,
      'target':dec(su[1]) if su else 0,
      'pre':f'{pre[4]}/r{pre[5]}' if pre and len(pre)>5 else '?',
      'post':f'{post[3]}/r{post[4]}' if post and len(post)>4 else '?',
      'route':dec(su[23]) if su and len(su)>24 else 0,
      'dv':su[24] if su and len(su)>24 else '',
      'dv_offset':dec(su[22]) if su and len(su)>23 else 0,
      'stop2_offset':dec(end[3]) if end and len(end)>3 else 0,
      'scan_fr':dec(scan[4]) if scan and len(scan)>5 else (dec(live[4]) if live and len(live)>4 else 0),
      'scan_exact':dec(scan[5]) if scan and len(scan)>5 else 0,
      'fixed_to_hook':dec(v38[9]) if v38 and len(v38)>10 else 0,
      'early_ja':dec(early[26]) if early and len(early)>27 else 0,
      'early_js':dec(early[27]) if early and len(early)>28 else 0,
      'early_live_phase':hexi(livep[7]) if livep and len(livep)>7 else 0,
      'br_aa_median':medaa,
      'br_aa_double':double,
      'br_ab_median':int(statistics.median(ab)) if ab else 0,
      'br_ab_big':bigab,
      'fast_calls':len(fast),
    }


def main():
    paths=[]
    for a in sys.argv[1:]:
        p=Path(a)
        if p.is_dir(): paths += sorted(p.glob('*.csv'))
        elif p.exists(): paths.append(p)
    if not paths: raise SystemExit('usage: analyze_suicune_branchphase_v721.py trace.csv [trace2.csv ... | directory]')
    ss=[summarize(p) for p in paths]
    cols=list(ss[0])
    print(','.join(cols))
    for x in ss: print(','.join(str(x[c]) for c in cols))
    print('\n# grouped PRE -> POST')
    groups={}
    for x in ss: groups.setdefault(x['pre'],{}).setdefault(x['post'],[]).append(x)
    for pre,posts in sorted(groups.items()):
        print(pre)
        for post,xs in sorted(posts.items()):
            aa=[x['br_aa_median'] for x in xs if x['br_aa_median']]
            fh=[x['fixed_to_hook'] for x in xs if x['fixed_to_hook']]
            ja=[x['early_ja'] for x in xs]
            print(f'  {post}: n={len(xs)} aa_med={int(statistics.median(aa)) if aa else 0} fixed_hook_med={int(statistics.median(fh)) if fh else 0} j_a={ja}')

if __name__=='__main__': main()
