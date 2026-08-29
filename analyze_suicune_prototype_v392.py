#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_suicune_prototype_v391 as v391


def strict_group_validation(results):
    groups=defaultdict(list)
    for r in results:
        groups[(r['class']['prototype'],r['class']['rotation'])].append(r)
    rows=[]
    for key,g in sorted(groups.items()):
        proto,rot=key
        for t in g:
            donors=[d for d in g if d is not t]
            if not donors:
                rows.append({'target':t['profile']['source'],'prototype':proto,'rotation':rot,'group_size':len(g),'donors':0,'status':'singleton'})
                continue
            env=v391.branch_envelope_coverage(t,donors)
            ds=[v391.shape_distance(t,d) for d in donors]
            best=min(ds,key=lambda x:(x['errors'],-x['points'],x['first_error_rel'] or 9999))
            branch={x['rel'] for x in env['branch_positions']}
            errs=set(best['error_rels'])
            tp=branch & errs
            precision=(len(tp)/len(branch)) if branch else None
            recall=(len(tp)/len(errs)) if errs else 1.0
            density=(best['errors']/env['branch_count']) if env['branch_count'] else None
            log10_enum=0.0
            for b in env['branch_positions']:
                log10_enum += math.log10(b['options'])
            rows.append({
                'target':t['profile']['source'],'prototype':proto,'rotation':rot,'group_size':len(g),'donors':len(donors),'status':'tested',
                'missing':env['missing'],'points':env['points'],'missing_rels':env['missing_rels'],
                'branch_sites':env['branch_count'],'enumeration_log10':log10_enum,
                'best_donor':best['donor'],'best_errors':best['errors'],'first_error_rel':best['first_error_rel'],
                'tp_sites':len(tp),'precision':precision,'recall':recall,'site_density':density,
            })
    summary=[]
    for (proto,rot),g in sorted(groups.items()):
        tested=[r for r in rows if r['prototype']==proto and r['rotation']==rot and r['status']=='tested']
        summary.append({'prototype':proto,'rotation':rot,'count':len(g),'sources':[x['profile']['source'] for x in g],
                        'tested':len(tested),'missing_zero':sum(x.get('missing')==0 for x in tested),
                        'best_missing':min((x['missing'] for x in tested), default=None),
                        'median_missing':(sorted(x['missing'] for x in tested)[len(tested)//2] if tested else None)})
    return {'groups':summary,'rows':rows}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('traces',nargs='+');ap.add_argument('--model-out');args=ap.parse_args()
    rs=[]
    for x in args.traces:
        try:rs.append(v391.analyze(Path(x)))
        except Exception as e:print('ERROR',x,e)
    base=v391.validate(rs); strict=strict_group_validation(rs)
    print('DIV cycle sum:',v391.DIV_CYCLE_SUM)
    print('LOO raw DV:',base['leave_one_out'])
    print('Exact phase coverage:',base['coverage'])
    print('\n(proto,rotation) groups:')
    for g in strict['groups']:
        print(f"  {g['prototype']} r{g['rotation']}: n={g['count']} {','.join(g['sources'])} tested={g['tested']} best_missing={g['best_missing']}")
    print('\nStrict same-(proto,rot) LOO:')
    for r in strict['rows']:
        if r['status']=='singleton':
            print(f"  {r['target']} {r['prototype']}r{r['rotation']}: singleton")
        else:
            p='-' if r['precision'] is None else f"{100*r['precision']:.1f}%"
            print(f"  {r['target']} {r['prototype']}r{r['rotation']}: missing={r['missing']} branches={r['branch_sites']} best={r['best_donor']} err={r['best_errors']} first={r['first_error_rel']} precision={p} recall={100*r['recall']:.1f}% log10(enum)={r['enumeration_log10']:.2f}")
    if args.model_out:
        m=v391.model_json(rs);m['version']='V39.2-PROTROT-VALIDATION';m['strict_proto_rotation']=strict
        Path(args.model_out).write_text(json.dumps(m,ensure_ascii=False,separators=(',',':')))
        print('wrote',args.model_out)
if __name__=='__main__':main()
