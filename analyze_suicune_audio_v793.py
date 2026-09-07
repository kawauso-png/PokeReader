#!/usr/bin/env python3
"""Offline omnibus validator for PokeReader Suicune v7.9.x CSVs.

Usage:
  python3 analyze_suicune_audio_v793.py celebi_trace_*.csv
  python3 analyze_suicune_audio_v793.py traces/ --out report_dir

Outputs runs.csv, channels.csv, pairs.csv, hypotheses.csv and report.md.
No runtime/guest reads are added: all diagnostics are derived from already saved CSV data.
"""
from __future__ import annotations
import argparse, csv, glob, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

CH_LEN=0x32
WAUDIO_OFF=1               # C100=wMusicPlaying, C101=wChannel1
J_OFFSET=3449              # frozen development constant
STOP_BASE={26:12940,27:12904} # frozen stop-live baselines; keep raw stop_exec_m too

def F(s): return next(csv.reader([s]))
def I(x,b=10):
    try: return int(str(x).strip(),b)
    except (ValueError,TypeError): return None
def U16(b,o): return b[o]|(b[o+1]<<8)

def inputs(xs):
    out=[]
    for x in xs:
        p=Path(x)
        if p.is_dir(): out += sorted(p.glob('*.csv'))
        else:
            g=[Path(q) for q in glob.glob(x)]
            out += g if g else ([p] if p.exists() else [])
    seen=set(); ans=[]
    for p in out:
        q=str(p.resolve())
        if q not in seen: seen.add(q); ans.append(p)
    return ans

def sections(lines):
    wanted={'NEUTRALPROBE','EXACT2','POSTFP','PREFP','PHASEUTILITY','SUICUNE'}
    out={}
    for i in range(len(lines)-1):
        if ',' not in lines[i] or ',' not in lines[i+1]: continue
        v=F(lines[i+1])
        if v and v[0] in wanted: out[v[0]]=dict(zip(F(lines[i]),v))
    return out

def frames(lines):
    for i,l in enumerate(lines):
        if l.startswith('frame,rel_adv,'):
            h=F(l); out=[]
            for q in lines[i+1:]:
                if not q.strip(): break
                v=F(q)
                if len(v)<len(h) or not v[0].isdigit(): break
                out.append(dict(zip(h,v)))
            return out
    return []

def audiopre(lines):
    for l in lines:
        if l.startswith('AUDIOPRE,'):
            v=F(l)
            if len(v)<6: return None
            return {'valid':I(v[2]) or 0,'target':I(v[3]),'base':I(v[4],16),'len':I(v[5]),'hex':v[6] if len(v)>6 else ''}
    return None

def channel(a,ch):
    o=WAUDIO_OFF+(ch-1)*CH_LEN; d=a[o:o+CH_LEN]
    if len(d)!=CH_LEN: return {}
    return {
      'channel':ch,'music_id':U16(d,0),'bank':d[2],'flags1':d[3],'flags2':d[4],'flags3':d[5],
      'music_addr':U16(d,6),'last_addr':U16(d,8),'note_flags':d[0x0c],'condition':d[0x0d],
      'duty':d[0x0e],'volume_envelope':d[0x0f],'frequency':U16(d,0x10),'pitch':d[0x12],
      'octave':d[0x13],'transposition':d[0x14],'note_duration':d[0x15],
      'note_duration_modifier':d[0x16],'loop_count':d[0x18],'tempo':U16(d,0x19),'tracks':d[0x1b],
      'duty_pattern':d[0x1c],'vib_delay_count':d[0x1d],'vib_delay':d[0x1e],
      'vib_extent':d[0x1f],'vib_rate':d[0x20],'pitch_slide_target':U16(d,0x21),
      'pitch_slide_amount':d[0x23],'pitch_slide_fraction':d[0x24],'field25':d[0x25],
      'pitch_offset':U16(d,0x27),'subroutine':int(bool(d[3]&2)),'looping':int(bool(d[3]&4)),
      'vibrato':int(bool(d[4]&1)),'pitch_slide':int(bool(d[4]&2)),'duty_loop':int(bool(d[4]&4))}

def stop1(rs):
    c=Counter(I(r.get('rel_adv')) for r in rs if I(r.get('rel_adv')) is not None and I(r.get('rel_adv'))<=40)
    a=[(n,k) for k,n in c.items() if n>=5]
    return sorted(a,key=lambda z:(-z[0],z[1]))[0][1] if a else None

def phase(r):
    d=I(r.get('sample_live_div'),16); s=I(r.get('sample_live_sub'),16)
    if d is None or s is None or d==255 or s==255: return None
    return ((d<<6)|s)&0x3fff

def unwrapped(v):
    if not v:return []
    o=[v[0]]
    for x in v[1:]: o.append(o[-1]+((x-(o[-1]&0x3fff))&0x3fff))
    return o

def pcsig(rs,lo=23,hi=27):
    a=[]; last=None
    for r in rs:
        rel=I(r.get('rel_adv'))
        if rel is None or not lo<=rel<=hi: continue
        t=f"{rel}:{r.get('sample_pc','')}"
        if t!=last:a.append(t);last=t
    return '>'.join(a)

def secint(d,k): return I(d.get(k)) if d else None

def parse(p,joff,base):
    lines=p.read_text(errors='replace').splitlines(); ss=sections(lines); rs=frames(lines)
    m=re.search(r'(\d{4})',p.name); run=int(m.group(1)) if m else None
    st=stop1(rs); sr=[r for r in rs if I(r.get('rel_adv'))==st]
    ph=[x for x in (phase(r) for r in sr) if x is not None]; up=unwrapped(ph)
    ex=up[-1]-up[0] if len(up)>=2 else None
    gp=ex-base[st] if ex is not None and st in base else None
    n=ss.get('NEUTRALPROBE',{}); j=secint(n,'j_a'); js=secint(n,'j_s')
    e=ss.get('EXACT2',{}); polls=secint(e,'polled_up_advances'); relok=secint(e,'release_confirmed')
    ap=audiopre(lines); ch={}
    if ap and ap['valid'] and ap['len'] and len(ap['hex'])>=ap['len']*2:
        try:
            a=bytes.fromhex(ap['hex'][:ap['len']*2]); ch={i:channel(a,i) for i in (1,2,3)}
        except ValueError: pass
    window=st+7 if st in (26,27) else None
    for i,d in ch.items():
        first=max(1,d['note_duration']); d['first_parse_update']=first
        d['parse_before_stop1_end']=int(window is not None and first<=window)
        d['parse_margin']=window-first if window is not None else None
    addrs=tuple(ch[i]['music_addr'] for i in (1,2,3)) if len(ch)==3 else None
    nds=tuple(ch[i]['note_duration'] for i in (1,2,3)) if len(ch)==3 else None
    crossings=sum(d['parse_before_stop1_end'] for d in ch.values())
    sm=sum(1<<(i-1) for i,d in ch.items() if d['subroutine']); lm=sum(1<<(i-1) for i,d in ch.items() if d['looping'])
    err=(gp-joff)-j if gp is not None and j is not None else None
    return {'run':run,'file':p.name,'stop_rel':st,'stop_samples':len(ph),'stop_exec_m':ex,
      'gap_baseline':base.get(st),'gap_proxy':gp,'j_a':j,'j_s':js,'j_equal':int(j is not None and j==js),
      'j_minus_gap':j-gp if j is not None and gp is not None else None,'predicted_j_gap_offset':gp-joff if gp is not None else None,
      'predicted_j_error':err,'post_proto':n.get('post_proto',''),'post_rot':secint(n,'post_rot'),
      'exact2_polls':polls,'exact2_release_confirmed':relok,'pc_signature':pcsig(rs),'audio_valid':int(bool(ch)),
      'audio_target':ap['target'] if ap else None,'audio_base':ap['base'] if ap else None,'audio_len':ap['len'] if ap else None,
      'total_update_window':window,'parse_crossings':crossings,'subroutine_mask':sm,'looping_mask':lm,
      'addr_tuple':addrs,'nd_tuple':nds,'channels':ch}

def A(t): return '/'.join(f'{x:04X}' for x in t) if t else ''
def N(t): return '/'.join(str(x) for x in t) if t else ''

def pairs(rr):
    g=defaultdict(list)
    for r in rr:
        if r['addr_tuple']:g[r['addr_tuple']].append(r)
    out=[]
    for addr,x in g.items():
        x=sorted(x,key=lambda r:r['run'] or 999999)
        for a,b in zip(x,x[1:]):
            na,nb=a['nd_tuple'],b['nd_tuple']
            out.append({'run_a':a['run'],'run_b':b['run'],'music_addr_tuple':A(addr),'nd_a':N(na),'nd_b':N(nb),
              'delta_nd_ch1':nb[0]-na[0],'delta_nd_ch2':nb[1]-na[1],'delta_nd_ch3':nb[2]-na[2],
              'crossings_a':a['parse_crossings'],'crossings_b':b['parse_crossings'],'delta_crossings':b['parse_crossings']-a['parse_crossings'],
              'delta_stop_exec_m':b['stop_exec_m']-a['stop_exec_m'] if a['stop_exec_m'] is not None and b['stop_exec_m'] is not None else None,
              'delta_gap_proxy':b['gap_proxy']-a['gap_proxy'] if a['gap_proxy'] is not None and b['gap_proxy'] is not None else None,
              'delta_j':b['j_a']-a['j_a'] if a['j_a'] is not None and b['j_a'] is not None else None})
    return out

def hypotheses(rr,joff):
    o=[]; x=[r for r in rr if r['exact2_polls'] is not None]; bad=[r['run'] for r in x if r['exact2_polls']!=2 or r['exact2_release_confirmed']!=1]
    o.append({'hypothesis':'Exact2 integrity','status':'PASS' if x and not bad else 'ATTN','metric':f'{len(x)-len(bad)}/{len(x)} exact','outliers':';'.join(map(str,bad))})
    x=[r for r in rr if r['j_minus_gap'] is not None]
    if x:
        res=[r['j_minus_gap'] for r in x]; bad=[r['run'] for r in x if abs(r['predicted_j_error'])>5]
        o.append({'hypothesis':f'J = gap_proxy - {joff}','status':'PASS' if not bad else 'ATTN',
          'metric':f"median(J-gap)={statistics.median(res):.1f}; max|err|={max(abs(r['predicted_j_error']) for r in x)}",'outliers':';'.join(map(str,bad))})
    au=[r for r in rr if r['audio_valid']]
    o.append({'hypothesis':'AUDIOPRE coverage','status':'PASS' if au else 'N/A','metric':f'{len(au)}/{len(rr)} traces','outliers':';'.join(str(r['run']) for r in rr if not r['audio_valid'])})
    s=[r for r in au if r['subroutine_mask'] and r['j_minus_gap'] is not None]; n=[r for r in au if not r['subroutine_mask'] and r['j_minus_gap'] is not None]
    if s and n:
        sm=statistics.median(r['j_minus_gap'] for r in s); nm=statistics.median(r['j_minus_gap'] for r in n); d=sm-nm
        o.append({'hypothesis':'generic SUBROUTINE adds ~20 M','status':'REJECT' if abs(abs(d)-20)>8 else 'OPEN','metric':f'median sub={sm:.1f}, non-sub={nm:.1f}, delta={d:.1f}','outliers':''})
    c=Counter(r['stop_rel'] for r in rr if r['stop_rel'] is not None)
    o.append({'hypothesis':'stop1 rel26/27 split','status':'OPEN' if len(c)>1 else 'ONE_CLASS','metric':', '.join(f'rel{k}:{v}' for k,v in sorted(c.items())),'outliers':''})
    return o

def writecsv(p,rows,cols):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader()
        for r in rows:
            q=dict(r)
            if 'addr_tuple' in q:q['addr_tuple']=A(q['addr_tuple'])
            if 'nd_tuple' in q:q['nd_tuple']=N(q['nd_tuple'])
            w.writerow(q)

def table(rows,cols):
    if not rows:return '_none_\n'
    s='| '+' | '.join(cols)+' |\n| '+' | '.join('---' for _ in cols)+' |\n'
    for r in rows:s+='| '+' | '.join(str(r.get(c,'') if r.get(c) is not None else '').replace('|','\\|') for c in cols)+' |\n'
    return s

def report(rr,pp,hh,joff):
    s=['# Suicune Audio Omnibus Validator v7.9.3','',f'Traces: {len(rr)}','','## Hypotheses','',table(hh,['hypothesis','status','metric','outliers']),'## Runs','']
    x=[]
    for r in rr:x.append({'run':r['run'],'stop':r['stop_rel'],'execM':r['stop_exec_m'],'gapProxy':r['gap_proxy'],'J':r['j_a'],'J-gap':r['j_minus_gap'],'err':r['predicted_j_error'],'parse':r['parse_crossings'],'subMask':r['subroutine_mask'],'addr':A(r['addr_tuple']),'ND':N(r['nd_tuple']),'POST':f"{r['post_proto']}/{r['post_rot']}",'Exact2':r['exact2_polls']})
    s += [table(x,['run','stop','execM','gapProxy','J','J-gap','err','parse','subMask','addr','ND','POST','Exact2']),'## Same-address natural experiments','',table(pp,['run_a','run_b','music_addr_tuple','nd_a','nd_b','delta_crossings','delta_stop_exec_m','delta_j']),'## Boundary signatures','']
    sg=defaultdict(list)
    for r in rr:sg[(r['stop_rel'],r['pc_signature'])].append(r['run'])
    s.append(table([{'stop_rel':k[0],'runs':';'.join(map(str,v)),'signature':k[1]} for k,v in sg.items()],['stop_rel','runs','signature']))
    bad=[r for r in rr if r['predicted_j_error'] is not None and abs(r['predicted_j_error'])>5]
    s += ['## Priority outliers','']
    s += [f"- run {r['run']:04d}: J error {r['predicted_j_error']:+d} M, stop rel{r['stop_rel']}, subMask={r['subroutine_mask']}, addr={A(r['addr_tuple'])}, ND={N(r['nd_tuple'])}" for r in bad] or ['- none above +/-5 M.']
    s += ['','## Notes','', '- `stop_exec_m` is raw unwrapped guest-phase progress across the dense stop1 cluster.', '- `gap_proxy` subtracts a frozen rel-specific baseline; blind traces never refit it.', f'- `predicted_j_gap_offset = gap_proxy - {joff}`.', '- `parse` is only the first NoteDuration->ParseMusic crossing count; command-by-command simulation is the next layer.', '- `channels.csv` keeps exact PRE Flags/MusicAddress/LastMusicAddress/Loop/Vibrato fields.','']
    return '\n'.join(s)

def main():
    a=argparse.ArgumentParser();a.add_argument('inputs',nargs='+');a.add_argument('--out',default='suicune_v793_report');a.add_argument('--j-offset',type=int,default=J_OFFSET);a.add_argument('--rel26-base',type=int,default=STOP_BASE[26]);a.add_argument('--rel27-base',type=int,default=STOP_BASE[27]);z=a.parse_args()
    ps=inputs(z.inputs)
    if not ps:raise SystemExit('no CSV inputs found')
    base={26:z.rel26_base,27:z.rel27_base}; rr=[parse(p,z.j_offset,base) for p in ps];rr.sort(key=lambda r:(r['run'] is None,r['run'] or 0,r['file']))
    pp=pairs(rr);hh=hypotheses(rr,z.j_offset);out=Path(z.out);out.mkdir(parents=True,exist_ok=True)
    rc=['run','file','stop_rel','stop_samples','stop_exec_m','gap_baseline','gap_proxy','j_a','j_s','j_equal','j_minus_gap','predicted_j_gap_offset','predicted_j_error','post_proto','post_rot','exact2_polls','exact2_release_confirmed','audio_valid','audio_target','audio_base','audio_len','total_update_window','parse_crossings','subroutine_mask','looping_mask','addr_tuple','nd_tuple','pc_signature'];writecsv(out/'runs.csv',rr,rc)
    cr=[]
    for r in rr:
        for i,d in r['channels'].items():cr.append({'run':r['run'],'file':r['file'],'stop_rel':r['stop_rel'],**d})
    cc=['run','file','stop_rel','channel','music_id','bank','flags1','flags2','flags3','music_addr','last_addr','note_flags','condition','duty','volume_envelope','frequency','pitch','octave','transposition','note_duration','note_duration_modifier','loop_count','tempo','tracks','duty_pattern','vib_delay_count','vib_delay','vib_extent','vib_rate','pitch_slide_target','pitch_slide_amount','pitch_slide_fraction','field25','pitch_offset','subroutine','looping','vibrato','pitch_slide','duty_loop','first_parse_update','parse_before_stop1_end','parse_margin'];writecsv(out/'channels.csv',cr,cc)
    pc=['run_a','run_b','music_addr_tuple','nd_a','nd_b','delta_nd_ch1','delta_nd_ch2','delta_nd_ch3','crossings_a','crossings_b','delta_crossings','delta_stop_exec_m','delta_gap_proxy','delta_j'];writecsv(out/'pairs.csv',pp,pc);writecsv(out/'hypotheses.csv',hh,['hypothesis','status','metric','outliers']);(out/'report.md').write_text(report(rr,pp,hh,z.j_offset))
    print(f'wrote {out}');print(f"traces={len(rr)} audio={sum(r['audio_valid'] for r in rr)} pairs={len(pp)}")
    for h in hh:print(f"{h['status']:>9}  {h['hypothesis']}: {h['metric']}")
if __name__=='__main__':main()
