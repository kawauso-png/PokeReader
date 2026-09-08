"""Read-only trace audit. Phase/state alignment is checked against every call pair."""
from pathlib import Path
import argparse, collections, csv, hashlib, io, json

PROTO = {
 'A':[1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
 'B':[-4,7,-3,0,-2,3,-1,2,1,-3,2,-1,-1,3,0,-3],
 'C':[-2,1,1,-2,2,0,-1,0,1,-8,7,1,-4,4,0,0],
 'D':[2,0,-2,2,-1,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
}
SITES = [231,247,263,343,359,391,407,423,439,535,551,615,631,647]
A_FIXED = [222,238,254,270,350,366,398,414,430,446,526,542,606,622,638,654,702]
assert all(len(p)==16 and sum(p)==0 for p in PROTO.values())
def hx(s): return int(s,16)
def signed(x,mod=256): return (x+mod//2)%mod-mod//2
def step(state,a,s):
    total=(state>>8)+a
    return ((total&255)<<8)|(((state&255)-s-(total>>8))&255)
def closed(state,sa,ss):
    total=(state>>8)+sa
    return ((total&255)<<8)|(((state&255)-ss-(total>>8))&255)
def table(rows, name):
    idx=next(i for i,r in enumerate(rows) if r and r[0]==name)
    header=rows[idx]
    out=[]
    for r in rows[idx+1:]:
        if not r or not r[0].isdigit(): break
        assert len(r)==len(header),(name,len(r),len(header))
        out.append(dict(zip(header,r)))
    return out
def parse(path):
    raw=path.read_bytes()
    # Known NUL is an empty character field in BUCKET738, not a numeric trace field.
    nul_lines=[l.decode(errors='replace') for l in raw.splitlines() if b'\0' in l]
    assert all(l.startswith('BUCKET738,') for l in nul_lines)
    rows=list(csv.reader(io.StringIO(raw.replace(b'\0',b'').decode())))
    records={}
    for i,r in enumerate(rows):
        if r and r[0] in ['SUICUNE','POSTFP','ENDPOINT']:
            assert r[0] not in records
            records[r[0]]=dict(zip(rows[i-1],r))
    frames=table(rows,'frame'); calls=table(rows,'call_index')
    fmap={}
    for f in frames:
        adv=int(f['advance'])
        if adv in fmap:
            assert all(f[k]==fmap[adv][k] for k in ['state','ap4','sp4','rel_adv'])
        else: fmap[adv]=f
    cmap=collections.defaultdict(list)
    for c in calls: cmap[(int(c['advance']),c['pc'])].append(c)
    return raw,records,fmap,cmap,frames,calls
def analyze(path):
    raw,records,fmap,cmap,frames,calls=parse(path)
    su=records['SUICUNE'];ep=records['ENDPOINT'];post=records['POSTFP']
    target=int(su['target']);stop=int(ep['stop2_advance']);anchor=target+41
    assert int(ep['capture_advance'])-stop==11
    assert int(ep['pause_advance'])-stop==11
    assert int(ep['expected_dv_advance'])-stop==13
    if su['result']=='OK': assert int(su['dv_advance'])-stop==13
    assert hx(ep['state'])==hx(fmap[int(ep['capture_advance'])]['state'])
    f40=fmap[anchor];s40=hx(f40['state']);phase=hx(f40['ap4'])
    assert int(f40['rel_adv'])==40
    assert hx(post['p40'])==phase
    rot=int(post['post_rot']);proto=PROTO[post['proto']]
    out=[];state=s40
    for adv in range(anchor+1,stop+1):
        rel=adv-target-1;k=rel-40
        before=fmap[adv-1];after=fmap[adv]
        aa=cmap[(adv-1,'02B6')];ss=cmap[(adv,'02BE')]
        assert len(aa)==len(ss)==1,(path.name,adv,len(aa),len(ss))
        a,s=aa[0],ss[0]
        assert int(s['call_index'])==int(a['call_index'])+1
        av=hx(a['div']);sv=hx(s['div'])
        assert av<=255 and sv<=255
        ap=(av<<6)|hx(a['mcycle']);sp=(sv<<6)|hx(s['mcycle'])
        assert ap==hx(after['ap4']) and sp==hx(after['sp4'])
        assert (hx(a['add'])<<8|hx(a['sub']))==state==hx(before['state'])
        assert hx(s['add'])==((state>>8)+av)&255 and hx(s['sub'])==(state&255)
        state=step(state,av,sv)
        assert state==hx(after['state']),(path.name,rel)
        phase=(phase+1172+proto[(rot+k-1)%16])&0x3fff
        na=phase>>6;ns=((phase+11)&0x3fff)>>6
        out.append(dict(rel=rel,advance=adv,pre_state=hx(before['state']),state=state,
            nominal_phase=phase,ap=ap,sp=sp,gap=(sp-ap)&0x3fff,
            phase_residual=signed(ap-phase,16384),a=av,s=sv,na=na,ns=ns,
            da=av-na,ds=sv-ns,da_mod=signed(av-na),ds_mod=signed(sv-ns),
            s11=((ap+11)&0x3fff)>>6,s11_error=sv-(((ap+11)&0x3fff)>>6),
            call_a=int(a['call_index']),call_s=int(s['call_index'])))
    # All calls in the half-open interval defined by the first and last pair.
    selected=[c for c in calls if out[0]['call_a']<=int(c['call_index'])<=out[-1]['call_s']]
    assert len(selected)==2*len(out)
    assert {c['pc'] for c in selected}=={'02B6','02BE'}
    sa=sum(x['a'] for x in out);ss=sum(x['s'] for x in out)
    assert closed(s40,sa,ss)==state
    nominal=closed(s40,sum(x['na'] for x in out),sum(x['ns'] for x in out))
    result=dict(file=path.name,sha256=hashlib.sha256(raw).hexdigest(),
        target=target,target_state=su['target_state'],cell=f"{post['proto']}/r{rot}",
        result=su['result'],raw_dv=su['raw_dv'],route=su['route'],
        state40=f40['state'],ap4_40=f40['ap4'],stop2=f'{state:04X}',N=len(out),
        stop2_rel=stop-target-1,nominal_stop2=f'{nominal:04X}',
        dadd=signed((state>>8)-(nominal>>8)),dsub=signed((state&255)-(nominal&255)),
        sum_a=sa,sum_s=ss,delta_sum_a=sum(x['da'] for x in out),delta_sum_s=sum(x['ds'] for x in out),
        s11_errors=[x['rel'] for x in out if x['s11_error']],
        gaps_ge64=[x['rel'] for x in out if x['gap']>=64],
        pattern=''.join(str(int(next(x for x in out if x['rel']==r)['phase_residual']==4)) for r in SITES),
        site_phases=[next(x for x in out if x['rel']==r)['phase_residual'] for r in SITES],
        updates=out)
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,default=Path('work/inputs'))
    p.add_argument('--output',type=Path,default=Path('work/audit.json'));args=p.parse_args()
    runs=[analyze(path) for path in sorted(args.inputs.glob('celebi_trace_*.csv'))]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(runs,indent=2))
    for r in runs:
        print(r['file'],r['cell'],r['state40'],r['stop2'],r['N'],
              'res',r['dadd'],r['dsub'],'sums',r['delta_sum_a'],r['delta_sum_s'],
              'pattern',r['pattern'],sum(map(int,r['pattern'])),'site phase',sorted(set(r['site_phases'])),
              'S11 exceptions',r['s11_errors'])
    print('Verified updates',sum(r['N'] for r in runs))
if __name__=='__main__':main()
