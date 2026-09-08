"""Validate a complete clock capture and locate timing/RNG discrepancies.

This replays measured DIV inputs; it is not a PRE-to-DV predictor.
"""
from pathlib import Path
import argparse,csv,io,json
HEX={'pc','state','div','tima','tma','tac','ie','iflag','stat','lcdc'}

def analyze(path):
    rows=list(csv.reader(io.StringIO(path.read_bytes().replace(b'\0',b'').decode())))
    events=[];meta=None;target=None;research=None;end={};header=None;issues=[]
    for i,r in enumerate(rows):
        if not r:continue
        if r[0]=='record' and len(r)>2 and r[1:3]==['index','kind']:header=r
        elif r[0]=='R7110_CLOCK':
            if header is None or len(r)!=len(header):raise ValueError('invalid clock row shape')
            e={k:(v if k in ('record','kind') else int(v,16 if k in HEX else 10)) for k,v in zip(header,r)}
            if e['index']!=len(events):issues.append('nonconsecutive clock index')
            if not e['stable']:issues.append('unstable clock snapshot '+str(e['index']))
            if 1<=e['remaining']<=64 and 0<=e['elapsed']<e['remaining']:
                e['phase']=(e['div']*64+64-e['remaining']+e['elapsed'])&16383
            else:
                e['phase']=None
                if e['kind']=='DIV':issues.append('invalid DIV countdown '+str(e['index']))
            if events and any(e[k]<events[-1][k] for k in ['lcd_count','lcd_long','timer_count']):issues.append('nonmonotonic IRQ counters')
            events.append(e)
        elif r[0]=='R7110_CLOCKMETA':
            if meta is not None:raise ValueError('duplicate clock metadata')
            meta=dict(zip(['target','ready','count','dropped','lcd','lcd_long','timer'],map(int,r[1:8])))
        elif r[0]=='SUICUNE':target=dict(zip(rows[i-1],r))
        elif r[0]=='R7102_META':research=dict(zip(rows[i-1],r))
        elif r[0]=='R7102_BLOB' and r[1]=='END_HRAM':end[int(r[3])]=bytes.fromhex(r[4])
    if meta is None:return {'file':path.name,'valid':False,'issues':['no R7110 clock capture']}
    if not meta['ready'] or meta['dropped'] or meta['count']!=len(events):issues.append('clock capture is incomplete')
    timers=[e for e in events if e['kind']=='TIMER'];divs=[e for e in events if e['kind']=='DIV']
    if len(timers)!=meta['timer']:issues.append('timer events are missing')
    end_blob=bytearray()
    for off,data in sorted(end.items()):
        if off!=len(end_blob):issues.append('incomplete END HRAM');break
        end_blob.extend(data)
    if len(end_blob)!=127:issues.append('missing END HRAM')
    if target is None or research is None:issues.append('missing main trace metadata')
    if issues:return {'file':path.name,'valid':False,'metadata':meta,'issues':issues}
    if int(target['target'])!=meta['target'] or int(research['target'])!=meta['target']:issues.append('target metadata mismatch')
    if research.get('pre_ok')!='1' or research.get('end_valid')!='1':issues.append('invalid main capture')
    state=int(target['target_state'],16);initial_state=state;pairs=[];normal=0;final=[]
    if len(divs)%2:issues.append('unpaired DIV read')
    for a,s in zip(divs[::2],divs[1::2]):
        if (a['pc'],s['pc']) not in [(0x2b5,0x2bd),(0x2b6,0x2be),(0x2f60,0x2f68)]:
            issues.append('invalid A/S order');break
        if a['state']!=state:issues.append('RNG discontinuity before clock '+str(a['index']))
        # Normal VBlank and BattleRandom enter with carry clear in this route.
        total=(state>>8)+a['div'];mid=((total&255)<<8)|(state&255)
        if s['state']!=mid:issues.append('ADC state mismatch at clock '+str(s['index']))
        state=(mid&0xff00)|(((state&255)-s['div']-(total>>8))&255)
        dl=s['lcd_count']-a['lcd_count'];dt=s['timer_count']-a['timer_count']
        short=s['lcd_long']==a['lcd_long'] and all(e['timer_flag']==0 for e in timers if a['index']<e['index']<s['index'])
        gap=(s['phase']-a['phase'])&16383
        expected=11+22*dl+43*dt if short else None
        if expected is not None and gap!=expected:issues.append('unexplained A/S timing at clock '+str(a['index']))
        pair={'a_index':a['index'],'s_index':s['index'],'pc':f"{a['pc']:04X}",'advance':a['advance'],
              'a_phase':a['phase'],'s_phase':s['phase'],'a_div':a['div'],'s_div':s['div'],
              'state_before':f"{a['state']:04X}",'state_after':f'{state:04X}',
              'gap':gap,'lcd_irqs':dl,'timer_irqs':dt,'expected_short_irq_gap':expected}
        pairs.append(pair)
        if a['pc']==0x2f60:final.append(pair)
        else:
            if a['advance']!=meta['target']+normal:issues.append('missing normal RNG update')
            normal+=1
    if normal!=int(research['end_advance'])-meta['target']:issues.append('normal RNG count mismatch')
    observed_end=int.from_bytes(end_blob[0x61:0x63],'big')
    if state!=observed_end:issues.append('END RNG state mismatch')
    dv=None
    if len(final) not in (3,4):issues.append('expected three or four final random calls')
    else:
        if ((int(final[0]['state_after'],16)&255)>=192)!=(len(final)==4):issues.append('held-item branch mismatch')
        dv=((int(final[-2]['state_after'],16)&255)<<8)|(int(final[-1]['state_after'],16)&255)
        if dv!=int(target['raw_dv'],16):issues.append('final DV mismatch')
    return {'file':path.name,'scope':'Measured-clock replay and diagnostics; not a prospective prediction.',
            'valid':not issues,'metadata':meta,'normal_updates':normal,'final_calls':len(final),
            'initial_state':f'{initial_state:04X}','replayed_dv':f'{dv:04X}' if dv is not None else None,
            'short_timer_events':sum(e['timer_flag']==0 for e in timers),'issues':issues,
            'pairs':pairs,'timer_events':timers}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=analyze(a.trace);a.output.write_text(json.dumps(r,indent=2));print(json.dumps({k:v for k,v in r.items() if k not in ('pairs','timer_events')},indent=2))
