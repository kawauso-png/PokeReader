#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, re, statistics
from pathlib import Path

DEV_CYCLES = {
    4: 6773, 5: 7141, 6: 8471, 7: 7089, 8: 8156,
    9: 8287, 10: 7292, 11: 7140, 12: 7122, 13: 7964,
}
DEFAULT_K = 7101.9

def run_id(p: Path) -> int:
    m = re.search(r'_(\d{4})', p.name)
    if not m: raise ValueError(f'cannot parse run id: {p}')
    return int(m.group(1))

def parse_record(lines, prefix):
    vals=[ln for ln in lines if ln.startswith(prefix+',')]
    return vals[-1].split(',') if vals else None

def parse_trace(p: Path):
    lines=p.read_text(errors='ignore').splitlines()
    rid=run_id(p)
    pre=parse_record(lines,'PREFP')
    neu=parse_record(lines,'NEUTRALPROBE')
    post=parse_record(lines,'POSTFP')
    aud=parse_record(lines,'AUDIOPRE')
    d={'run':rid,'file':p.name}
    if pre:
        d.update(pre_proto=pre[4], pre_rot=int(pre[5]), pre_target=int(pre[18]))
    if neu:
        d.update(root=int(neu[2]), target=int(neu[3]), neutral_f=int(neu[4]),
                 state=neu[6], target_div=neu[8], root_bucket=int(neu[9]),
                 j=int(neu[13]), neutral_post_proto=neu[15], neutral_post_rot=int(neu[16]))
    if post:
        d.update(post_proto=post[3], post_rot=int(post[4]))
    if aud:
        d.update(audio_valid=int(aud[2]), audio_target=int(aud[3]), audio_hex=aud[6])
    else:
        d.update(audio_valid=0, audio_target=None, audio_hex='')
    return d

def load_cycles(path: Path|None):
    if path is None: return DEV_CYCLES.copy()
    out={}
    with path.open(newline='') as f:
        for r in csv.DictReader(f): out[int(r['run'])]=int(r['cycles'])
    return out

def main():
    ap=argparse.ArgumentParser(description='Suicune v7.9.6 mechanistic-J validator')
    ap.add_argument('traces', nargs='+', type=Path)
    ap.add_argument('--cycles-csv', type=Path, help='CSV with columns run,cycles from LR35902 emulator')
    ap.add_argument('--k', type=float, default=DEFAULT_K, help='single additive constant cycles-J')
    ap.add_argument('--out', type=Path, default=Path('suicune_v796_j_report'))
    args=ap.parse_args()
    rows=[parse_trace(p) for p in args.traces]
    cycles=load_cycles(args.cycles_csv)
    args.out.mkdir(parents=True,exist_ok=True)

    errs=[]; ks=[]
    for r in rows:
        c=cycles.get(r['run'])
        r['cycles']=c
        if c is not None and 'j' in r:
            r['pred_j']=c-args.k
            r['err']=r['j']-r['pred_j']
            r['K']=c-r['j']
            errs.append(abs(r['err'])); ks.append(r['K'])
        else:
            r['pred_j']=r['err']=r['K']=''

    cols=['run','target','state','pre_proto','pre_rot','root','root_bucket','target_div','j','post_proto','post_rot','audio_valid','cycles','pred_j','err','K','file']
    with (args.out/'runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

    lines=['# Suicune v7.9.6 mechanistic-J validation','']
    all_ar13=[r for r in rows if r.get('pre_proto')=='A' and r.get('pre_rot')==13]
    lines.append(f'- PREFP A/r13: {len(all_ar13)}/{len(rows)}')
    a8a9=[r for r in rows if r.get('target_div')=='A8A9']
    lines.append(f'- target_div A8A9: {len(a8a9)}/{len(rows)}')
    if errs:
        lines += [f'- evaluated: {len(errs)}',f'- max |J error|: {max(errs):.1f} M',f'- mean |J error|: {statistics.mean(errs):.1f} M',f'- median K: {statistics.median(ks):.1f}',f'- K range: {min(ks)}..{max(ks)}']
    by={}
    for r in rows:
        key=(r.get('target'),r.get('state'))
        by.setdefault(key,[]).append(r)
    dups=[v for k,v in by.items() if None not in k and len(v)>1]
    for v in dups:
        lines.append('- duplicate target/state: ' + ', '.join(f"{r['run']:04d}(J={r.get('j')},POST={r.get('post_proto')}/r{r.get('post_rot')})" for r in v))
    lines += ['','|run|target|PRE|J|cycles|pred J|err|K|POST|audio|','|---:|---:|:---:|---:|---:|---:|---:|---:|:---:|:---:|']
    for r in rows:
        def fmt(x): return '' if x=='' or x is None else (f'{x:.1f}' if isinstance(x,float) else str(x))
        lines.append(f"|{r['run']:04d}|{r.get('target','')}|{r.get('pre_proto','')}/r{r.get('pre_rot','')}|{r.get('j','')}|{fmt(r['cycles'])}|{fmt(r['pred_j'])}|{fmt(r['err'])}|{fmt(r['K'])}|{r.get('post_proto','')}/r{r.get('post_rot','')}|{r.get('audio_valid',0)}|")
    (args.out/'report.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:12]))

if __name__=='__main__': main()
