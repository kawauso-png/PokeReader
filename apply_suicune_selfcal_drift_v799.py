#!/usr/bin/env python3
from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
t=T.read_text()

def rep(old,new,label):
    global t
    n=t.count(old)
    if n!=1:
        raise SystemExit(f'v799 {label}: expected 1 match, got {n}')
    t=t.replace(old,new,1)

anchor='''static mut V798_JLIN28_10: i32 = 0;\n'''
insert=anchor+'''\n// v7.9.9 lifetime K telemetry.  This is diagnostic only and never gates UP.\n// Keep the v7.9.8 64-byte file/header/checksum compatible: bytes 44..63 were\n// previously unused, so older v7.9.8 builds still read the recent-8 ring.\nconst V799_DRIFT_WARN_ABS10: i32 = 150; // 15.0 M-cycle diagnostic threshold\nstatic mut V799_LIFE_COUNT: u32 = 0;\nstatic mut V799_LIFE_SUM_K: u32 = 0;\nstatic mut V799_LIFE_SUMSQ_K: u64 = 0;\nstatic mut V799_LIFE_MEAN_K10: i32 = 0;\nstatic mut V799_LIFE_VAR_K100: u32 = 0;\nstatic mut V799_DRIFT_D10: i32 = 0;\nstatic mut V799_DRIFT_WARN: bool = false;\n\nunsafe fn v799_life_recompute() {\n    let n=V799_LIFE_COUNT as u128;\n    if n==0 {\n        V799_LIFE_MEAN_K10=0; V799_LIFE_VAR_K100=0;\n        V799_DRIFT_D10=0; V799_DRIFT_WARN=false;\n        return;\n    }\n    V799_LIFE_MEAN_K10=((V799_LIFE_SUM_K as u128)*10/n) as i32;\n    let ss=V799_LIFE_SUMSQ_K as u128;\n    let s=V799_LIFE_SUM_K as u128;\n    let num=ss.saturating_mul(n).saturating_sub(s.saturating_mul(s));\n    V799_LIFE_VAR_K100=(num.saturating_mul(100)/(n.saturating_mul(n))) as u32;\n    V799_DRIFT_D10=V798_CAL_MEAN_K10-V799_LIFE_MEAN_K10;\n    V799_DRIFT_WARN=V799_LIFE_COUNT>V798_CAL_CAP as u32 && V799_DRIFT_D10.abs()>=V799_DRIFT_WARN_ABS10;\n}\n\nunsafe fn v799_life_seed_from_ring() {\n    V799_LIFE_COUNT=0; V799_LIFE_SUM_K=0; V799_LIFE_SUMSQ_K=0;\n    for i in 0..(V798_CAL_COUNT as usize) {\n        let k=V798_CAL_K[i] as i32;\n        if k>=V798_CAL_K_MIN && k<=V798_CAL_K_MAX {\n            V799_LIFE_COUNT=V799_LIFE_COUNT.saturating_add(1);\n            V799_LIFE_SUM_K=V799_LIFE_SUM_K.saturating_add(k as u32);\n            V799_LIFE_SUMSQ_K=V799_LIFE_SUMSQ_K.saturating_add((k as u64)*(k as u64));\n        }\n    }\n    v799_life_recompute();\n}\n\nunsafe fn v799_life_add(k:i32) {\n    if k<V798_CAL_K_MIN || k>V798_CAL_K_MAX { return; }\n    let ku=k as u32;\n    if V799_LIFE_COUNT==u32::MAX || V799_LIFE_SUM_K>u32::MAX-ku { return; }\n    V799_LIFE_COUNT+=1; V799_LIFE_SUM_K+=ku;\n    V799_LIFE_SUMSQ_K=V799_LIFE_SUMSQ_K.saturating_add((ku as u64)*(ku as u64));\n    v799_life_recompute();\n}\n'''
rep(anchor,insert,'globals')

old='''    V798_CAL_COUNT=count as u8; V798_CAL_NEXT=next as u8;\n    v798_cal_recompute();\n    true\n}\n'''
new='''    V798_CAL_COUNT=count as u8; V798_CAL_NEXT=next as u8;\n    v798_cal_recompute();\n    let ext_want=(V798_CAL_RAW[60] as u32)|((V798_CAL_RAW[61] as u32)<<8)|((V798_CAL_RAW[62] as u32)<<16)|((V798_CAL_RAW[63] as u32)<<24);\n    let ext_got=v798_fnv32(&V798_CAL_RAW[44..60]);\n    if ext_want==ext_got {\n        V799_LIFE_COUNT=(V798_CAL_RAW[44] as u32)|((V798_CAL_RAW[45] as u32)<<8)|((V798_CAL_RAW[46] as u32)<<16)|((V798_CAL_RAW[47] as u32)<<24);\n        V799_LIFE_SUM_K=(V798_CAL_RAW[48] as u32)|((V798_CAL_RAW[49] as u32)<<8)|((V798_CAL_RAW[50] as u32)<<16)|((V798_CAL_RAW[51] as u32)<<24);\n        V799_LIFE_SUMSQ_K=0;\n        for j in 0..8 { V799_LIFE_SUMSQ_K|=(V798_CAL_RAW[52+j] as u64)<<(j*8); }\n        if V799_LIFE_COUNT < V798_CAL_COUNT as u32 { v799_life_seed_from_ring(); } else { v799_life_recompute(); }\n    } else {\n        v799_life_seed_from_ring();\n    }\n    true\n}\n'''
rep(old,new,'decode extension')

old='''    let sum=v798_fnv32(&V798_CAL_RAW[..40]);\n    V798_CAL_RAW[40]=(sum&0xff) as u8; V798_CAL_RAW[41]=((sum>>8)&0xff) as u8;\n    V798_CAL_RAW[42]=((sum>>16)&0xff) as u8; V798_CAL_RAW[43]=((sum>>24)&0xff) as u8;\n}\n'''
new='''    let sum=v798_fnv32(&V798_CAL_RAW[..40]);\n    V798_CAL_RAW[40]=(sum&0xff) as u8; V798_CAL_RAW[41]=((sum>>8)&0xff) as u8;\n    V798_CAL_RAW[42]=((sum>>16)&0xff) as u8; V798_CAL_RAW[43]=((sum>>24)&0xff) as u8;\n    let n=V799_LIFE_COUNT; let sk=V799_LIFE_SUM_K; let ss=V799_LIFE_SUMSQ_K;\n    for j in 0..4 { V798_CAL_RAW[44+j]=((n>>(j*8))&0xff) as u8; V798_CAL_RAW[48+j]=((sk>>(j*8))&0xff) as u8; }\n    for j in 0..8 { V798_CAL_RAW[52+j]=((ss>>(j*8))&0xff) as u8; }\n    let ext=v798_fnv32(&V798_CAL_RAW[44..60]);\n    V798_CAL_RAW[60]=(ext&0xff) as u8; V798_CAL_RAW[61]=((ext>>8)&0xff) as u8;\n    V798_CAL_RAW[62]=((ext>>16)&0xff) as u8; V798_CAL_RAW[63]=((ext>>24)&0xff) as u8;\n}\n'''
rep(old,new,'encode extension')

old='''        V798_CAL_COUNT=0; V798_CAL_NEXT=0;\n        for i in 0..V798_CAL_CAP { V798_CAL_CYCLES[i]=0; V798_CAL_K[i]=0; }\n        v798_cal_recompute();\n'''
new='''        V798_CAL_COUNT=0; V798_CAL_NEXT=0;\n        for i in 0..V798_CAL_CAP { V798_CAL_CYCLES[i]=0; V798_CAL_K[i]=0; }\n        V799_LIFE_COUNT=0; V799_LIFE_SUM_K=0; V799_LIFE_SUMSQ_K=0;\n        v798_cal_recompute(); v799_life_recompute();\n'''
rep(old,new,'empty init')

old='''    V798_CAL_PENDING_CYCLES=cycles; V798_CAL_PENDING_K=k as i16; V798_CAL_DIRTY=true;\n    v798_cal_recompute();\n}\n'''
new='''    V798_CAL_PENDING_CYCLES=cycles; V798_CAL_PENDING_K=k as i16; V798_CAL_DIRTY=true;\n    v798_cal_recompute();\n    v799_life_add(k);\n}\n'''
rep(old,new,'lifetime add')

t=t.replace('STALLPHASE,V798,rel0-40+vblankirq+cpuctx84+audiopre+jpred+selfcal8+kbranch+finaldv',
            'STALLPHASE,V799,rel0-40+vblankirq+cpuctx84+audiopre+jpred+selfcal8+lifek+kbranch+finaldv')

anchor='''        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");\n'''
insert='''        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _=write!(line,"\\nlifecal,version,count,mean_k_x10,var_k_x100,recent_minus_life_x10,drift_warn\\n");\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        unsafe { let _=write!(line,"LIFECAL,V799,{},{},{},{},{}\\n",V799_LIFE_COUNT,V799_LIFE_MEAN_K10,V799_LIFE_VAR_K100,V799_DRIFT_D10,V799_DRIFT_WARN as u8); }\n        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");\n'''
rep(anchor,insert,'CSV lifetime')

old='''                    if V798_PRED_SLOPE_VALID { pnp::println!("Jlin {} / {} DIAG",V798_JLIN27_10,V798_JLIN28_10); }\n                    pnp::println!("PRESS UP BLIND + FINAL DV");\n'''
new='''                    if V798_PRED_SLOPE_VALID { pnp::println!("Jlin {} / {} DIAG",V798_JLIN27_10,V798_JLIN28_10); }\n                    if V799_DRIFT_WARN { pnp::println!("KDRIFT d10 {} LIFE N{}",V799_DRIFT_D10,V799_LIFE_COUNT); }\n                    pnp::println!("PRESS UP BLIND + FINAL DV");\n'''
rep(old,new,'UI drift warning')

t=t.replace('S798 SELFCAL READY N{}','S799 SELFCAL READY N{}')
T.write_text(t)
print('Applied v7.9.9 lifetime K telemetry: recent-8 predictor unchanged; lifetime count/mean/variance + drift warning persisted compatibly')
