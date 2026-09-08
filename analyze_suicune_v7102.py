#!/usr/bin/env python3
"""Read collector CSVs. Diagnose data sufficiency; never estimate shiny success."""
from pathlib import Path
import argparse,csv,io,json,statistics
from v7102.analyze_tail import analyze as audit_tail
from v7102.analyze_tail import A_FIXED,SITES
TPS=268111856
A_PCS={0x2b5,0x2b6,0x2f60};S_PCS={0x2bd,0x2be,0x2f68}
CENTERS=set(A_FIXED+SITES+[225,241,257,369,42,577,715])
def countdown_phase(div,remaining,elapsed):
    if not (0<=div<=255 and 1<=remaining<=64 and 0<=elapsed<remaining):
        raise ValueError('not a normal instruction-read countdown state')
    return (div*64+64-remaining+elapsed)&0x3fff

def analyze_countdown(samples):
    rows=[]
    for i in range(0,len(samples)-1,2):
        a,s=samples[i:i+2]
        if 'div_remaining_before' not in a or 'div_remaining_before' not in s:continue
        row=dict(sample_a=i,pc=f"{a['pc']:04X}")
        try:
            ap=countdown_phase(a['div_before'],a['div_remaining_before'],a['sub_before'])
            sp=countdown_phase(s['div_before'],s['div_remaining_before'],s['sub_before'])
            row.update(a_phase=f'{ap:04X}',s_phase=f'{sp:04X}',gap=(sp-ap)&0x3fff,
                predicted_s_div=f'{((ap+11)&0x3fff)>>6:02X}',observed_s_div=f"{s['div_before']:02X}",
                fixed_instruction_gap_matches=((sp-ap)&0x3fff)==11,
                s_div_prediction_matches=(((ap+11)&0x3fff)>>6)==s['div_before'])
        except ValueError as e:row['error']=str(e)
        row['stable_during_copy']=all(x['div_remaining_before']==x['div_remaining_after'] for x in (a,s))
        rows.append(row)
    return rows
def wanted(r):return r<=42 or 713<=r<=760 or any(abs(r-c)<=1 for c in CENTERS)
def infer_pairs(samples,end_state=None,end_advance=None):
    """Enumerate ADC carry-in 0/1; boundary states alone do not identify DIV A."""
    out=[];errors=[]
    for i,a in enumerate(samples):
        if a['pc'] not in A_PCS:continue
        if i+1>=len(samples) or samples[i+1]['pc'] not in S_PCS:
            errors.append(f'missing S boundary after sample {i}');continue
        s=samples[i+1]
        if (a['pc']==0x2f60)!=(s['pc']==0x2f68):
            errors.append(f'pair class mismatch at {i}');continue
        st0=a['state'];mid=s['state'];delta=((mid>>8)-(st0>>8))&255
        if (st0&255)!=(mid&255):errors.append(f'S changed before S read at {i}');continue
        if i+2<len(samples) and samples[i+2]['pc'] in A_PCS:
            end=samples[i+2]['state'];source='next_A_boundary'
        elif i+2==len(samples) and end_state is not None and end_advance==s['advance']:
            end=end_state;source='terminal_same_advance'
        else:errors.append(f'missing successor after S sample {i+1}');continue
        if end>>8!=mid>>8:errors.append(f'extra A change after S sample {i+1}');continue
        candidates=[]
        for carry_in in (0,1):
            av=(delta-carry_in)&255
            carry_out=int((st0>>8)+av+carry_in>255)
            sv=((mid&255)-(end&255)-carry_out)&255
            candidates.append(dict(carry_in=carry_in,carry_out=carry_out,a_div=av,s_div=sv))
        out.append(dict(index=i,pc=a['pc'],advance=a['advance'],state_before=st0,
            state_after=end,effective_add_delta=delta,divider_candidates=candidates,successor=source,
            a_observed=a.get('div_before'),s_observed=s.get('div_before')))
    return out,errors

def read(path):
    raw=path.read_bytes();nul=[l for l in raw.splitlines() if b'\0' in l]
    if any(not l.startswith(b'BUCKET738,') for l in nul):raise ValueError('NUL outside legacy BUCKET738 field')
    rows=list(csv.reader(io.StringIO(raw.replace(b'\0',b'').decode())))
    rec={};samples=[];blobs={};frames=[]
    frame_header=None
    for i,r in enumerate(rows):
        if not r:continue
        if r[0] in ('SUICUNE','POSTFP','ENDPOINT','EXACT2','NEUTRALPROBE','R7102_META'):
            if r[0] in rec:raise ValueError('duplicate record '+r[0])
            rec[r[0]]=dict(zip(rows[i-1],r))
        if r[0]=='frame':frame_header=r
        elif frame_header is not None and r[0].isdigit() and len(r)==len(frame_header):frames.append(dict(zip(frame_header,r)))
        else:frame_header=None
        if r[0]=='R7102_BLOB':
            if len(r)!=5:raise ValueError('bad blob row length')
            tag=r[1];off=int(r[3]);b=bytes.fromhex(r[4]);parts=blobs.setdefault(tag,{})
            if off in parts:raise ValueError('duplicate blob chunk')
            parts[off]=b
        elif r[0]=='R7102_SAMPLE':
            if len(r) not in (20,22):raise ValueError('bad sample row length')
            s=dict(kind=r[1],index=int(r[2]),frame=int(r[3]),advance=int(r[4]),rel=int(r[5]),
                pc=int(r[6],16),state=int(r[7],16),div_before=int(r[8],16),sub_before=int(r[9],16),
                div_after=int(r[10],16),sub_after=int(r[11],16),tick_begin=int(r[12]),tick_end=int(r[13]),
                cpu=bytes.fromhex(r[14]),audio=bytes.fromhex(r[15]),hram=bytes.fromhex(r[16]),
                regs=r[17],stack=r[18],gb_stack=bytes.fromhex(r[19]))
            if [len(s[k]) for k in ('cpu','audio','hram','regs','stack','gb_stack')]!=[64,448,127,120,64,256]:raise ValueError('bad sample payload size')
            if s['state']!=(s['hram'][0x61]<<8|s['hram'][0x62]):raise ValueError('HRAM/state mismatch')
            if len(r)==22:s.update(div_remaining_before=int(r[20]),div_remaining_after=int(r[21]))
            samples.append(s)
    bdata={}
    for tag,parts in blobs.items():
        buf=bytearray()
        for off,b in sorted(parts.items()):
            if off!=len(buf):raise ValueError('missing blob chunk '+tag)
            buf.extend(b)
        bdata[tag]=bytes(buf)
    return rec,frames,samples,bdata

def analyze(path):
    rec,frames,samples,blobs=read(path);meta=rec.get('R7102_META')
    result=dict(file=path.name,collector=bool(meta),mode=meta.get('mode') if meta else 'LEGACY',issues=[])
    if not meta:return result
    issue=result['issues'];target=int(meta['target']);mode=meta['mode']
    if 'native_ok' in meta:
        result['native_diagnostic_valid']=meta['native_ok']=='1' and meta.get('emu_ok')=='1' and len(blobs.get('NATIVE_CODE',b''))==0xb1000 and len(blobs.get('PRE_EMU',b''))==int(meta.get('emu_len','0')) and int(meta.get('emu_len','0')) in (0x230,0x480)
        if not result['native_diagnostic_valid']:issue.append('incomplete native emulator diagnostic')
    for key,n in [('PRE_RAM',8192),('PRE_HRAM',127),('PRE_CPU',64),('END_RAM',8192),('END_HRAM',127),('END_CPU',64)]:
        if len(blobs.get(key,b''))!=n:issue.append('incomplete '+key)
    for k in ('pre_ok','map_ok','end_valid'):
        if meta[k]!='1':issue.append(k+' false')
    for k in ('dropped_frames','dropped_deep'):
        if int(meta[k]):issue.append(k+'='+meta[k])
    fs=[s for s in samples if s['kind']=='FRAME'];ds=[s for s in samples if s['kind']=='DIV'];ls=[s for s in samples if s['kind']=='LCD']
    if 'lcd_samples' in meta:
        if len(ls)!=int(meta['lcd_samples']):issue.append('LCD sample count mismatch')
        if int(meta['dropped_lcd']):issue.append('LCD samples dropped')
        result['lcd_events']=[]
        for s in ls:
            row=dict(index=s['index'],advance=s['advance'],tick=s['tick_begin'],ffc6=s['hram'][0x46],pc=f"{s['pc']:04X}")
            try:row['phase']=f"{countdown_phase(s['div_before'],s['div_remaining_before'],s['sub_before']):04X}"
            except ValueError as e:row['error']=str(e)
            result['lcd_events'].append(row)
        final_as=[s for s in ds if s['pc']==0x2f60]
        result['dv_call_interval_checks']=[]
        for a,b in zip(final_as,final_as[1:]):
            def caller(s):
                off=int.from_bytes(s['cpu'][30:32],'little')-0xc000
                return int.from_bytes(s['gb_stack'][off+6:off+8],'little') if 0<=off<=248 else None
            if (caller(a),caller(b))!=(0x69b2,0x69b6):continue
            events=[s for s in ls if a['tick_begin']<s['tick_begin']<b['tick_begin']]
            try:
                gap=(countdown_phase(b['div_before'],b['div_remaining_before'],b['sub_before'])-countdown_phase(a['div_before'],a['div_remaining_before'],a['sub_before']))&0x3fff
                expected=109+22*len(events) if all(s['hram'][0x46]==0 for s in events) else None
                result['dv_call_interval_checks'].append(dict(observed_gap=gap,short_lcd_events=len(events),expected_if_only_short_lcd_interrupts=expected,matches=gap==expected if expected is not None else None))
            except ValueError as e:issue.append('invalid countdown in DV interval: '+str(e))
    if len(fs)!=int(meta['frames']) or len(ds)!=int(meta['deep']):issue.append('sample count mismatch')
    for ss in (fs,ds,ls):
        if [s['index'] for s in ss]!=list(range(len(ss))):issue.append('sample index gap')
    for s in samples:
        if s['rel']!=(s['advance']-target-1)&0xffffffff:issue.append('relative-advance mismatch')
        if s['tick_end']<s['tick_begin']:issue.append('negative capture duration')
    if mode=='BASE' and samples:issue.append('BASE has active samples')
    if mode=='TAIL':
        expected={i for i,f in enumerate(frames) if wanted(int(f['advance'])-target-1)}
        got={s['frame'] for s in fs};missing=sorted(expected-got)
        result['missing_frame_snapshots']=missing
        if missing:issue.append('missing targeted frame snapshots')
        for s in fs:
            i=s['frame']
            if i>=len(frames) or int(frames[i]['advance'])!=s['advance'] or int(frames[i]['state'],16)!=s['state']:
                issue.append('frame join mismatch');break
    if mode=='DEEP' and not ds:issue.append('no final-window DIV boundaries')
    neu=rec.get('NEUTRALPROBE',{});ex=rec.get('EXACT2',{});su=rec.get('SUICUNE',{})
    if neu.get('advance_delta')!='3' or neu.get('neutral_requested')!='3':issue.append('neutral3 not confirmed')
    if neu.get('resume_actual_mod16')!='14':issue.append('M14 not confirmed')
    if ex.get('polled_up_advances')!='2' or ex.get('release_confirmed')!='1':issue.append('physical Exact2 not confirmed')
    if su.get('result')!='OK':issue.append('no final DV')
    result['collection_complete']=not issue
    result['divider_observation_valid']=meta.get('div_source')=='indirect'
    if samples and not result['divider_observation_valid']:
        issue.append('v7102 direct DIV columns are pointer-slot bytes, not DIV; exclude them from inference')
    result['raw_dv']=su.get('raw_dv');result['post']=rec.get('POSTFP',{})
    result['capture_count']=len(samples)
    costs=[(s['tick_end']-s['tick_begin'])*1e6/TPS for s in samples]
    result['capture_cost_us']={'median':statistics.median(costs),'max':max(costs)} if costs else None
    result['subtick_changed_during_copy']=sum(s['sub_before']!=s['sub_after'] for s in samples)
    result['divider_changed_during_copy']=sum((s['div_before'],s['sub_before'])!=(s['div_after'],s['sub_after']) for s in samples)
    if not result['divider_observation_valid']:result['divider_changed_during_copy']=None
    if ds:
        result['countdown_clock_pairs']=analyze_countdown(ds)
        if not result['divider_observation_valid']:
            ds=[{k:v for k,v in sample.items() if k not in ('div_before','div_after')} for sample in ds]
        end=blobs.get('END_HRAM',b'');st=(end[0x61]<<8)|end[0x62] if len(end)==127 else None
        pairs,errs=infer_pairs(ds,st,int(meta['end_advance']) if meta.get('end_valid')=='1' else None)
        result['inferred_pairs']=pairs;result['pair_issues']=errs
        if errs:issue.append('incomplete or inconsistent DIV boundary chain')
        deep=[p for p in pairs if p['pc']==0x2f60]
        result['deep_pair_count']=len(deep)
        if len(deep)>=2:
            dv=((deep[-2]['state_after']&255)<<8)|(deep[-1]['state_after']&255)
            result['reconstructed_raw_dv']=f'{dv:04X}'
            result['deep_raw_matches']=su.get('raw_dv')==f'{dv:04X}'
            if not result['deep_raw_matches']:issue.append('deep boundary reconstruction disagrees with final DV')
    if su.get('result')=='OK':
        try:
            a=audit_tail(path)
            result['tail_audit']=dict(valid=True,cell=a['cell'],N=a['N'],pattern=a['pattern'],
                dadd=a['dadd'],dsub=a['dsub'],s11_errors=a['s11_errors'],
                nonzero_phase_residuals=[{'rel':x['rel'],'residual':x['phase_residual']} for x in a['updates'] if x['phase_residual']])
        except (AssertionError,KeyError,ValueError,StopIteration) as e:
            result['tail_audit']=dict(valid=False,error=repr(e));issue.append('tail recurrence/alignment needs investigation')
    result['data_quality']='needs_attention' if issue else 'complete_for_this_mode'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    reports=[]
    for path in sorted(a.inputs.glob('celebi_trace_*.csv')):
        try:reports.append(analyze(path))
        except Exception as e:reports.append(dict(file=path.name,error=repr(e),data_quality='unreadable'))
    modes={m:sum(r.get('mode')==m and r.get('data_quality')=='complete_for_this_mode' for r in reports) for m in ('BASE','TAIL','DEEP')}
    out=dict(runs=reports,complete_mode_counts=modes,next_step='まず各モードの欠落・入力条件・観測負荷を確認し、POST条件を合わせて分岐変数を比較する。3本だけで法則確定や観測無影響とは判定しない。')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({'complete_mode_counts':modes,'files':len(reports)},ensure_ascii=False))
if __name__=='__main__':main()
