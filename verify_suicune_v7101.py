#!/usr/bin/env python3
"""Exhaustive host check of preimage lookup; not hardware validation."""
from pathlib import Path
import hashlib,json,subprocess,tempfile

base=Path(__file__).resolve().parent
paths=json.loads((base/'v7101/paths.json').read_text())
bits=(base/'v7101/roots.bin').read_bytes()
assert len(bits)==8192 and sum(bin(b).count('1') for b in bits)==5887
assert len(paths)==3159
arrays=','.join('['+','.join(map(str,p))+']' for p in paths)
source='''#[path = MODEL] mod model;
const PATHS: &[[u32;4]] = &[ARRAYS];
fn step(st:u16,a:u32,s:u32)->u16 {
    let sum=(st>>8) as u32+a;
    (((sum&255) as u16)<<8)|((st as u8).wrapping_sub(s as u8).wrapping_sub((sum>>8) as u8) as u16)
}
fn shiny(raw:u16)->bool {
    let attack=raw>>12; let defense=(raw>>8)&15;
    let speed=(raw>>4)&15; let special=raw&15;
    [2,3,6,7,10,11,14,15].contains(&attack) && defense==10 && speed==10 && special==10
}
fn forward(target:u16,path:&[u32;4])->u16 {
    let before=step(target,path[0],path[1]);
    let after=step(before,path[2],path[3]);
    ((before&255)<<8)|(after&255)
}
fn main() {
    let mut count=0;
    for root in 0..=65535u32 {
        let r=root as u16;
        let target=step(step(step(r,132,132),150,150),168,169);
        assert_eq!(target,model::after_neutral3(r),"neutral {:04X}",r);
        let expected=PATHS.iter().any(|p|shiny(forward(target,p)));
        assert_eq!(expected,model::root_candidate(r),"root {:04X}",r);
        if expected {
            count+=1;
            assert!(model::arm_matches(r,target,3,0x2a35,0x2a40,3));
            assert!(!model::arm_matches(r,target^1,3,0x2a35,0x2a40,3));
            assert!(!model::arm_matches(r,target,2,0x2a35,0x2a40,3));
            assert!(!model::arm_matches(r,target,3,0x2a34,0x2a40,3));
            assert!(!model::arm_matches(r,target,3,0x2a35,0x2a3f,3));
            assert!(!model::arm_matches(r,target,3,0x2a35,0x2a40,1));
        }
    }
    assert_eq!(count,5887);
    println!("PASS: all 65536 roots, all neutral projections, 5887 accepted, arm mismatch guards");
}
'''.replace('MODEL',json.dumps(str(base/'v7101/model.rs'))).replace('ARRAYS',arrays)
with tempfile.TemporaryDirectory(prefix='suicune-v7101-') as tmp:
    p=Path(tmp);(p/'test.rs').write_text(source)
    subprocess.run(['rustc','--edition=2021','-O',str(p/'test.rs'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)

t=(base/'reader_core/src/crystal/trace.rs').read_text();c=(base/'3gx/sources/main.c').read_text()
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in t
assert 'let phase_ready = candidate;' in t
assert 'if !v7101_check_root(cur,reader.rng_state()) { return; }' in t
arm=t[t.index('    pub fn arm_suicune_probe'):t.index('    fn update_suicune_endpoint')]
assert arm.rfind('self.practical_active = false;')>arm.rfind('self.practical_active = self.practical_candidate_valid')
assert '(suicune_control_pause_cell() & (1U << 25)) == 0' in c
assert 'suicune_neutral_probe_remaining = 3U;' in c
assert 'suicune_neutral_probe_frames++' not in c
assert 'const u32 wanted = 14U;' in c
# Hook provenance is pinned by the checked-in baseline manifest below.
manifest=json.loads((base/'v7101/baseline_hashes.json').read_text())
for rel,sha in manifest.items():
    if rel not in ('reader_core/src/crystal/trace.rs','3gx/sources/main.c'):
        assert hashlib.sha256((base/rel).read_bytes()).hexdigest()==sha,rel
print('PASS: unchanged input/Random hook, exact2 + M14, final-DV observation lane')
