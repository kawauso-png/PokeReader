#!/usr/bin/env python3
from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
t=T.read_text()

def rep(old,new,label):
    global t
    n=t.count(old)
    if n!=1: raise SystemExit(f'v798b {label}: expected 1, got {n}')
    t=t.replace(old,new,1)

rep('''static mut V798_CAL_PENDING_K: i16 = 0;\nstatic mut V798_JMEAN27_10: i32 = 0;\n''','''static mut V798_CAL_PENDING_K: i16 = 0;\n// Freeze the exact calibration state used before physical UP so the saved CSV\n// remains a true blind record even after this run adds its own K sample.\nstatic mut V798_PRED_COUNT: u8 = 0;\nstatic mut V798_PRED_K10: i32 = V798_CAL_FALLBACK_K10;\nstatic mut V798_PRED_SLOPE_PPM: i32 = 0;\nstatic mut V798_PRED_SLOPE_VALID: bool = false;\nstatic mut V798_JMEAN27_10: i32 = 0;\n''','pred statics')

rep('''unsafe fn v798_predict_from_cycles(c27:u16,c28:u16) {\n    v798_ensure_cal();\n    V798_JMEAN27_10=(c27 as i32)*10-V798_CAL_MEAN_K10;\n    V798_JMEAN28_10=(c28 as i32)*10-V798_CAL_MEAN_K10;\n    let lin_k = |c:u16| -> i32 {\n        if !V798_CAL_SLOPE_VALID { return V798_CAL_MEAN_K10; }\n        let dx10=(c as i32)*10-V798_CAL_MEAN_CYCLES10;\n        V798_CAL_MEAN_K10 + (((V798_CAL_SLOPE_PPM as i64)*(dx10 as i64))/1_000_000) as i32\n    };\n''','''unsafe fn v798_predict_from_cycles(c27:u16,c28:u16) {\n    v798_ensure_cal();\n    V798_PRED_COUNT=V798_CAL_COUNT;\n    V798_PRED_K10=V798_CAL_MEAN_K10;\n    V798_PRED_SLOPE_PPM=V798_CAL_SLOPE_PPM;\n    V798_PRED_SLOPE_VALID=V798_CAL_SLOPE_VALID;\n    V798_JMEAN27_10=(c27 as i32)*10-V798_PRED_K10;\n    V798_JMEAN28_10=(c28 as i32)*10-V798_PRED_K10;\n    let lin_k = |c:u16| -> i32 {\n        if !V798_PRED_SLOPE_VALID { return V798_PRED_K10; }\n        let dx10=(c as i32)*10-V798_CAL_MEAN_CYCLES10;\n        V798_PRED_K10 + (((V798_PRED_SLOPE_PPM as i64)*(dx10 as i64))/1_000_000) as i32\n    };\n''','freeze predictor state')

rep('''selfcal,version,from_file,load_len,count,next,mean_k_x10,mean_cycles_x10,slope_ppm,slope_valid,jmean27_x10,jmean28_x10,jlin27_x10,jlin28_x10,added_this_run,added_cycles,added_k,dirty,save_len''','''selfcal,version,from_file,load_len,pred_count,pred_k_x10,pred_slope_ppm,pred_slope_valid,jmean27_x10,jmean28_x10,jlin27_x10,jlin28_x10,post_count,post_next,post_mean_k_x10,added_this_run,added_cycles,added_k,dirty,save_len''','csv header')

rep('''            let _=write!(line,"SELFCAL,V798,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n",\n                V798_CAL_FROM_FILE as u8,V798_CAL_LOAD_LEN,V798_CAL_COUNT,V798_CAL_NEXT,\n                V798_CAL_MEAN_K10,V798_CAL_MEAN_CYCLES10,V798_CAL_SLOPE_PPM,V798_CAL_SLOPE_VALID as u8,\n                V798_JMEAN27_10,V798_JMEAN28_10,V798_JLIN27_10,V798_JLIN28_10,\n                V798_CAL_ADDED_THIS_RUN as u8,V798_CAL_PENDING_CYCLES,V798_CAL_PENDING_K,\n                V798_CAL_DIRTY as u8,V798_CAL_SAVE_LEN);\n''','''            let _=write!(line,"SELFCAL,V798,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n",\n                V798_CAL_FROM_FILE as u8,V798_CAL_LOAD_LEN,V798_PRED_COUNT,V798_PRED_K10,\n                V798_PRED_SLOPE_PPM,V798_PRED_SLOPE_VALID as u8,\n                V798_JMEAN27_10,V798_JMEAN28_10,V798_JLIN27_10,V798_JLIN28_10,\n                V798_CAL_COUNT,V798_CAL_NEXT,V798_CAL_MEAN_K10,\n                V798_CAL_ADDED_THIS_RUN as u8,V798_CAL_PENDING_CYCLES,V798_CAL_PENDING_K,\n                V798_CAL_DIRTY as u8,V798_CAL_SAVE_LEN);\n''','csv row')

rep('''                    pnp::println!("S798 SELFCAL READY N{}", V798_CAL_COUNT);\n                    pnp::println!("Kx10 {} {}", V798_CAL_MEAN_K10, if V798_CAL_COUNT==0 {"PRIOR"} else {"MEAN"});\n''','''                    pnp::println!("S798 SELFCAL READY N{}", V798_PRED_COUNT);\n                    pnp::println!("Kx10 {} {}", V798_PRED_K10, if V798_PRED_COUNT==0 {"PRIOR"} else {"MEAN"});\n''','overlay state')
rep('''                    if V798_CAL_SLOPE_VALID { pnp::println!("Jlin {} / {} DIAG",V798_JLIN27_10,V798_JLIN28_10); }\n''','''                    if V798_PRED_SLOPE_VALID { pnp::println!("Jlin {} / {} DIAG",V798_JLIN27_10,V798_JLIN28_10); }\n''','overlay slope')

T.write_text(t)
print('Applied v7.9.8b blind-field freeze: pre-UP calibration state preserved separately from post-run update')
