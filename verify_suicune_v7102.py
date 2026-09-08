#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,tempfile,os
from analyze_suicune_v7102 import read,infer_pairs
base=Path(__file__).resolve().parent
code=(base/'v7102/test_collector.rs.in').read_text().replace('RESEARCH_PATH',json.dumps(str(base/'v7102/research.rs')))
with tempfile.TemporaryDirectory(prefix='suicune-v7102-') as d:
    p=Path(d);(p/'test.rs').write_text(code)
    subprocess.run(['rustc','--edition=2021','--test','-O',str(p/'test.rs'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test'),'--test-threads=1'],env={**os.environ,'V7102_TEST_DIR':str(p)},check=True)
    for name,count in [('base',0),('tail',384),('deep',32)]:
        rec,frames,samples,blobs=read(p/(name+'.csv'))
        assert rec['R7102_META']['mode']==name.upper() and len(samples)==count
        assert len(blobs['PRE_RAM'])==8192 and blobs['PRE_HRAM'][0x61:0x63]==bytes.fromhex('C23C')
    for a in range(256):
        for s in (0,1,255):
            for da in (0,1,255):
                for ds in (0,1,170,255):
                    carry=int(a+da>255);mid=(((a+da)&255)<<8)|s
                    end=(mid&0xff00)|((s-ds-carry)&255)
                    boundaries=[dict(pc=0x2f60,state=(a<<8)|s,advance=100),dict(pc=0x2f68,state=mid,advance=100)]
                    pairs,errors=infer_pairs(boundaries,end,100)
                    assert not errors and len(pairs)==1
                    assert (pairs[0]['a_consumed'],pairs[0]['s_consumed'],pairs[0]['carry'])==(da,ds,carry)
    _,errors=infer_pairs([dict(pc=0x2f60,state=0,advance=100)])
    assert errors
print('PASS: Rust CSV -> Python reader; inferred divider bytes across carry/wrap cases; missing boundaries rejected')
t=(base/'reader_core/src/crystal/trace.rs').read_text()
c=(base/'3gx/sources/main.c').read_text()
h=(base/'reader_core/src/crystal/hook.rs').read_text()
assert 'v7101' not in t.lower() and 'root_candidate' not in t
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in t
arm=t[t.index('    pub fn arm_suicune_probe'):t.index('    fn update_suicune_endpoint')]
assert arm.rfind('self.practical_active=false;')>arm.rfind('self.practical_active = self.practical_candidate_valid')
assert 'super::research::mode()==0 { v798_add_sample(' in t
assert 'if super::research::mode()==0 { unsafe { v798_save_cal_if_dirty(); v7100_save_if_dirty(); } }' in t
assert 'suicune_neutral_probe_remaining=3U;' in c and 'const u32 wanted = 14U;' in c
assert 'suicune_neutral_probe_frames++' not in c
assert 'super::research::div_boundary(rng_advance(),pc,regs,_stack_pointer);' in h
# The new module observes memory; it never calls a guest-write primitive.
research=(base/'v7102/research.rs').read_text()
for forbidden in ('host_write_mem','pnp::write','gb_mem::write','write_volatile'):
    assert forbidden not in research,forbidden
print('PASS: observation modes, bounds, snapshot serialization, arm guards, no PRE selection, Exact2/M14, no calibration contamination')
