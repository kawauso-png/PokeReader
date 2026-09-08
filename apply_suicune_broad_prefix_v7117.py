"""After v7116: inspect neutral PREs with exact-prefix proposals and full verification."""
from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
shutil.copyfile(r/'v7117/gate_runtime.c',r/'3gx/sources/v7113_gate_runtime.c')
shutil.copyfile(r/'v7117/snapshot.c',r/'3gx/sources/v7116_snapshot.c')
shutil.copyfile(r/'v7117/prefix.c',r/'3gx/sources/v7117_prefix.c')
for name in ['prefix.h','prefix_data.h']:shutil.copyfile(r/'v7117'/name,r/'3gx/includes'/name)
p=r/'reader_core/src/crystal/frame.rs';s=p.read_text();assert 'pub fn native_pre_state' not in s
s+='''
pub fn native_pre_state(advance:*mut u32)->u32 {
    if advance.is_null(){return 0;}
    let reader=Gen2Reader::crystal();let state=unsafe {get_state()};
    unsafe {*advance=super::hook::rng_advance();}
    state.trace.native_pre_state(&reader)
}
''';p.write_text(s)
p=r/'reader_core/src/crystal/mod.rs';s=p.read_text();assert 'pub use frame::native_pre_state;' not in s;s+='\npub use frame::native_pre_state;\n';p.write_text(s)
p=r/'reader_core/src/lib.rs';s=p.read_text();a='#[no_mangle]\npub extern "C" fn suicune_rank_pre_state';assert s.count(a)==1
s=s.replace(a,'''#[no_mangle]
pub extern "C" fn suicune_native_pre_state(advance:*mut u32)->u32 {
    if let Ok(LoadedTitle::CrystalJp)=loaded_title(){crystal::native_pre_state(advance)}else{0}
}

'''+a);p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text();a='    pub fn ranked_pre_state(&self,reader:&Gen2Reader)->u32 {';assert s.count(a)==1
s=s.replace(a,'''    // Called only by the frozen native predictor. Its full memory capture and
    // final commit independently revalidate the current guest state.
    pub fn native_pre_state(&self,reader:&Gen2Reader)->u32 {
        if self.probe_session || pnp::current_keys()!=0 {return 0;}
        0x80000000u32 | reader.rng_state() as u32
    }

'''+a);p.write_text(s)
p=r/'reader_core/src/crystal/research.rs';s=p.read_text();a='        PRE_OK=PRE_OK && target.wrapping_sub(root_advance)==3 && actual==expected && ap==0x2a35 && sp==0x2a40;';assert s.count(a)==1
s=s.replace(a,'''        // A broad PRE is accepted only after the C gate committed a full
        // native shiny prediction for this exact target and captured seed.
        extern "C" {fn gate7117_selected_pre(target:u32,state:u32)->i32;}
        let native_checked=gate7117_selected_pre(target,actual as u32)!=0;
        let legacy_checked=target.wrapping_sub(root_advance)==3 && actual==expected && ap==0x2a35 && sp==0x2a40;
        PRE_OK=PRE_OK && (native_checked || legacy_checked);''');p.write_text(s)
p=r/'3gx/sources/main.c';s=p.read_text();a='#include "gate_runtime.h"';assert s.count(a)==1;s=s.replace(a,a+'\nextern unsigned gate7117_offers(void);')
a='''                        suicune_wait_up_after_b=false;suicune_root_lock_ready=false;
                        suicune_root_lock_active=true;suicune_root_lock_failed=false;''';assert s.count(a)==1
s=s.replace(a,'''                        // Move only through genuine input-neutral frames. Periodic
                        // 3-frame steps avoid permanently sampling one parity.
                        suicune_wait_up_after_b=true;suicune_root_lock_ready=true;
                        suicune_root_lock_active=false;suicune_root_lock_failed=false;
                        suicune_neutral_probe_frames=(gate7113_checks()&63U)?2U:3U;
                        suicune_neutral_probe_remaining=suicune_neutral_probe_frames;
                        suicune_neutral_probe_executed=0;suicune_neutral_probe_pending=true;''')
s=s.replace('"CHECK %lu COST %lu",(unsigned long)gate7113_checks(),(unsigned long)rank7108_cycles()', '"CHECK %lu PREFIX %lu",(unsigned long)gate7113_checks(),(unsigned long)gate7117_offers()')
a='void host7113_progress(u32 check,u32 model,u32 frame) {';assert s.count(a)==1
s=s.replace(a,'static u32 gate7117_progress_stage=0;\nvoid host7117_stage(u32 stage){gate7117_progress_stage=stage;}\n'+a)
a='    snprintf(b,sizeof(b),"MODEL %lu/2 FRAME %lu",(unsigned long)(model+1),(unsigned long)frame);';assert s.count(a)==1
s=s.replace(a,'    if(gate7117_progress_stage==2)snprintf(b,sizeof(b),"SPEED TEST FRAME %lu",(unsigned long)frame);\n    else snprintf(b,sizeof(b),"%s %lu/2 FRAME %lu",gate7117_progress_stage?"PRE":"FULL",(unsigned long)(model+1),(unsigned long)frame);')
p.write_text(s)
for name in ['3gx/sources/main.c','reader_core/src/crystal/trace.rs']:
 p=r/name;s=p.read_text();assert 'S7116' in s;s=s.replace('S7116','S7117').replace('STALLPHASE,V7116,','STALLPHASE,V7117,');p.write_text(s)
print('Applied v7117: broader neutral PRE search; prefix proposals never select alone; committed full native DV required')
