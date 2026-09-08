"""Join durable PRE predictions, observed DVs, and rejected PRE scan records."""
import argparse,csv,io,json
from pathlib import Path

def analyze(directory):
    predictions={};results=[];scans=[];issues=[]
    for path in sorted(directory.glob('*.csv')):
        raw=path.read_bytes()
        if b'RANK7108_' not in raw:continue
        rows=list(csv.reader(io.StringIO(raw.replace(b'\0',b'').decode())))
        actual=None;local_result=[];local_pre=[]
        for i,r in enumerate(rows):
            if not r:continue
            if r[0]=='SUICUNE':actual=dict(zip(rows[i-1],r))
            elif r[0]=='RANK7108_PRE' and len(r)==17:
                p={'id':r[1],'model':r[2],'advance':int(r[3]),'seed':r[4],'audio_cycles':int(r[5]),
                   'rank_limit':int(r[9]),'predicted_shiny':r[10],'shiny_rank':int(r[11]),'support':int(r[12]),
                   'candidate_count':int(r[13]),'checks':int(r[14]),'pre_hash':r[15],'rom_fnv':r[16]}
                local_pre.append(p)
                if path.name.startswith('rank7108_') and not path.name.startswith('rank7108_scan_'):
                    if p['id'] in predictions:issues.append('duplicate PRE id '+p['id'])
                    predictions[p['id']]={**p,'prediction_file':path.name}
            elif r[0]=='RANK7108_RESULT' and len(r)==6:
                local_result.append({'id':r[1],'target_matches':r[2]=='1','result_present':r[3]=='1',
                                     'raw_dv':r[4],'actual_rank':int(r[5]),'trace_file':path.name})
            elif r[0]=='RANK7108_SCAN' and len(r)==15:
                scans.append({'search_id':r[1],'model':r[2],'check':int(r[3]),'advance':int(r[4]),'seed':r[5],
                              'audio_cycles':int(r[6]),'decision':int(r[7]),'error':r[8],'candidates':int(r[9]),
                              'shiny_dv':r[10],'shiny_rank':int(r[11]),'support':int(r[12]),'file':path.name})
        for r in local_result:
            p=next((p for p in local_pre if p['id']==r['id']),None)
            r['trace_pre']=p
            r['actual_record_matches']=bool(actual and p and actual.get('raw_dv')==r['raw_dv']
                and actual.get('target_state')==p['seed'] and int(actual.get('target','-1'))==p['advance'])
            results.append(r)
    for r in results:
        p=predictions.get(r['id'])
        r['durable_pre_file']=p['prediction_file'] if p else None
        r['durable_prediction_matches']=bool(p and r['trace_pre'] and all(p[k]==v for k,v in r['trace_pre'].items()))
        r['valid_pair']=r['durable_prediction_matches'] and r['target_matches'] and r['result_present'] and r['actual_record_matches']
        r['shiny']=int(r['raw_dv'],16) in (0x2aaa,0x3aaa,0x6aaa,0x7aaa,0xaaaa,0xbaaa,0xeaaa,0xfaaa)
        if not r['valid_pair']:issues.append('unmatched/incomplete trial '+r['trace_file'])
    valid=[r for r in results if r['valid_pair']]
    return {'scope':'Observed candidate-selected trials only; no inferred shiny probability or enrichment.',
            'scan_summary':{'checks':len(scans),'accepted_decisions':sum(s['decision']==1 for s in scans),
                            'rejected':sum(s['decision']==0 for s in scans),'errors':sum(s['decision']<0 for s in scans)},
            'trial_summary':{'valid_pairs':len(valid),'observed_shiny':sum(r['shiny'] for r in valid),
                             'actual_in_candidates':sum(r['actual_rank']>0 for r in valid),
                             'actual_top128':sum(0<r['actual_rank']<=128 for r in valid)},
            'trials':results,'scans':scans,'issues':issues}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=analyze(a.directory);a.output.write_text(json.dumps(r,indent=2))
    print(json.dumps({k:v for k,v in r.items() if k not in ('trials','scans')},indent=2))
if __name__=='__main__':main()
