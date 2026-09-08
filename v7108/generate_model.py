from pathlib import Path
import json,math,hashlib
base=Path(__file__).resolve().parent
raw=(base/'model.json').read_bytes();paths=json.loads(raw)
out=['/* Derived empirical DIV timing paths; no ROM bytes. */',
     '#include <stdint.h>',
     '#define RANK7108_MODEL "'+hashlib.sha256(raw).hexdigest()[:16]+'"',
     'typedef struct {int cost,n,f,sa,ss;const uint16_t (*normal)[2];uint16_t final[4][2];} RankPath;']
for i,p in enumerate(paths):
    assert p['pre']==['2A35','2A40','0000'] and all(c==0 for a,s,c in p['prefix'])
    pairs=p['normal_phase'][28:]
    out.append('static const uint16_t normal%d[][2]={%s};'%(i,','.join('{%d,%d}'%tuple(q) for q in pairs)))
out.append('static const RankPath paths[]={')
for i,p in enumerate(paths):
    sa=sum(a for a,s,c in p['prefix'][:28]);ss=sum(s for a,s,c in p['prefix'][:28])
    final=p['final_phase']+[[0,0]]*(4-len(p['final_phase']))
    out.append('{%d,%d,%d,%d,%d,normal%d,{%s}},'%(p['cost'],len(p['normal_phase'])-28,len(p['final_phase']),sa,ss,i,','.join('{%d,%d}'%tuple(q) for q in final)))
out.append('};')
for name,scale,maximum in [('time_weight',8,32),('shared_weight',4,8)]:
    out.append('static const double %s[]={%s};'%(name,','.join('%.17g'%math.exp(-k/scale) for k in range(maximum+1))))
(base/'rank_model.h').write_text('\n'.join(out)+'\n')
print('model',hashlib.sha256(raw).hexdigest(),'paths',len(paths))
