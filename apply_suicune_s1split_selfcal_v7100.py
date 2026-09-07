#!/usr/bin/env python3
from pathlib import Path

T=Path('reader_core/src/crystal/trace.rs')
B=Path('reader_core/src/pnp/bindings.rs')
U=Path('reader_core/src/pnp/utils.rs')
C=Path('3gx/sources/main.c')
t=T.read_text(); b=B.read_text(); u=U.read_text(); c=C.read_text()

def rep(src, old, new, label):
    n=src.count(old)
    if n!=1:
        raise SystemExit(f'v7100 {label}: expected 1 match, got {n}')
    return src.replace(old,new,1)

needle='''unsafe fn v798_save_cal_if_dirty() {
    if !V798_CAL_DIRTY { return; }
    v798_cal_encode();
    let src=core::ptr::addr_of!(V798_CAL_RAW).cast::<u8>();
    V798_CAL_SAVE_LEN=pnp::v798_cal_save(src,V798_CAL_BYTES as u32);
    if V798_CAL_SAVE_LEN==V798_CAL_BYTES as u32 { V798_CAL_DIRTY=false; V798_CAL_FROM_FILE=true; }
}

'''
insert=needle+'''// v7.10.0: s1-stratified self-calibration.  s1=27 and s1=28 have
// measurably different K distributions, so they must never share one recent
// mean.  Prediction remains blind: both branch means are frozen before UP.
const V7100_CAL_CAP: usize = 8;
const V7100_CAL_BYTES: usize = 128;
const V7100_K_MIN: i32 = 7000;
const V7100_K_MAX: i32 = 7200;
const V7100_FALLBACK_K27_10: i32 = 70917;
const V7100_FALLBACK_K28_10: i32 = 71091;
const V7100_DRIFT_WARN_ABS10: i32 = 150;
static mut V7100_RAW: [u8; V7100_CAL_BYTES] = [0; V7100_CAL_BYTES];
static mut V7100_ATTEMPTED: bool = false;
static mut V7100_FROM_FILE: bool = false;
static mut V7100_LOAD_LEN: u32 = 0;
static mut V7100_SAVE_LEN: u32 = 0;
static mut V7100_DIRTY: bool = false;
static mut V7100_LAST_TARGET: u32 = 0xffffffff;
static mut V7100_N27: u8 = 0;
static mut V7100_NEXT27: u8 = 0;
static mut V7100_N28: u8 = 0;
static mut V7100_NEXT28: u8 = 0;
static mut V7100_C27: [u16; V7100_CAL_CAP] = [0; V7100_CAL_CAP];
static mut V7100_K27: [i16; V7100_CAL_CAP] = [0; V7100_CAL_CAP];
static mut V7100_C28: [u16; V7100_CAL_CAP] = [0; V7100_CAL_CAP];
static mut V7100_K28: [i16; V7100_CAL_CAP] = [0; V7100_CAL_CAP];
static mut V7100_MEAN_K27_10: i32 = V7100_FALLBACK_K27_10;
static mut V7100_MEAN_K28_10: i32 = V7100_FALLBACK_K28_10;
static mut V7100_PRED_N27: u8 = 0;
static mut V7100_PRED_N28: u8 = 0;
static mut V7100_PRED_K27_10: i32 = V7100_FALLBACK_K27_10;
static mut V7100_PRED_K28_10: i32 = V7100_FALLBACK_K28_10;
static mut V7100_J27_10: i32 = 0;
static mut V7100_J28_10: i32 = 0;
static mut V7100_LIFE_N27: u32 = 0;
static mut V7100_LIFE_SUM27: u32 = 0;
static mut V7100_LIFE_SQ27: u64 = 0;
static mut V7100_LIFE_N28: u32 = 0;
static mut V7100_LIFE_SUM28: u32 = 0;
static mut V7100_LIFE_SQ28: u64 = 0;
static mut V7100_LIFE_MEAN27_10: i32 = 0;
static mut V7100_LIFE_MEAN28_10: i32 = 0;
static mut V7100_LIFE_VAR27_100: u32 = 0;
static mut V7100_LIFE_VAR28_100: u32 = 0;
static mut V7100_DRIFT27_10: i32 = 0;
static mut V7100_DRIFT28_10: i32 = 0;
static mut V7100_WARN27: bool = false;
static mut V7100_WARN28: bool = false;
static mut V7100_ADDED: bool = false;
static mut V7100_ADDED_S1: u8 = 0;
static mut V7100_ADDED_CYCLES: u16 = 0;
static mut V7100_ADDED_K: i16 = 0;

unsafe fn v7100_recompute_recent() {
    if V7100_N27==0 { V7100_MEAN_K27_10=V7100_FALLBACK_K27_10; }
    else { let mut s:i64=0; for i in 0..V7100_N27 as usize { s+=V7100_K27[i] as i64; } V7100_MEAN_K27_10=((s*10+(V7100_N27 as i64)/2)/(V7100_N27 as i64)) as i32; }
    if V7100_N28==0 { V7100_MEAN_K28_10=V7100_FALLBACK_K28_10; }
    else { let mut s:i64=0; for i in 0..V7100_N28 as usize { s+=V7100_K28[i] as i64; } V7100_MEAN_K28_10=((s*10+(V7100_N28 as i64)/2)/(V7100_N28 as i64)) as i32; }
}

unsafe fn v7100_recompute_life() {
    let calc=|n:u32,sum:u32,sq:u64| -> (i32,u32) { if n==0 { return (0,0); } let nn=n as u128; let ss=sq as u128; let s=sum as u128; let mean=((s*10)/nn) as i32; let num=nn.saturating_mul(ss).saturating_sub(s.saturating_mul(s)); let var=(num.saturating_mul(100)/(nn.saturating_mul(nn))) as u32; (mean,var) };
    let a=calc(V7100_LIFE_N27,V7100_LIFE_SUM27,V7100_LIFE_SQ27); let d=calc(V7100_LIFE_N28,V7100_LIFE_SUM28,V7100_LIFE_SQ28);
    V7100_LIFE_MEAN27_10=a.0; V7100_LIFE_VAR27_100=a.1; V7100_LIFE_MEAN28_10=d.0; V7100_LIFE_VAR28_100=d.1;
    V7100_DRIFT27_10=V7100_MEAN_K27_10-V7100_LIFE_MEAN27_10; V7100_DRIFT28_10=V7100_MEAN_K28_10-V7100_LIFE_MEAN28_10;
    V7100_WARN27=V7100_N27>0 && V7100_LIFE_N27>V7100_CAL_CAP as u32 && V7100_DRIFT27_10.abs()>=V7100_DRIFT_WARN_ABS10;
    V7100_WARN28=V7100_N28>0 && V7100_LIFE_N28>V7100_CAL_CAP as u32 && V7100_DRIFT28_10.abs()>=V7100_DRIFT_WARN_ABS10;
}

unsafe fn v7100_seed_life_from_rings() {
    V7100_LIFE_N27=0; V7100_LIFE_SUM27=0; V7100_LIFE_SQ27=0; V7100_LIFE_N28=0; V7100_LIFE_SUM28=0; V7100_LIFE_SQ28=0;
    for i in 0..V7100_N27 as usize { let k=V7100_K27[i] as i32; if k>=V7100_K_MIN&&k<=V7100_K_MAX { V7100_LIFE_N27+=1; V7100_LIFE_SUM27+=k as u32; V7100_LIFE_SQ27+=(k as u64)*(k as u64); } }
    for i in 0..V7100_N28 as usize { let k=V7100_K28[i] as i32; if k>=V7100_K_MIN&&k<=V7100_K_MAX { V7100_LIFE_N28+=1; V7100_LIFE_SUM28+=k as u32; V7100_LIFE_SQ28+=(k as u64)*(k as u64); } }
    v7100_recompute_life();
}

unsafe fn v7100_decode() -> bool {
    if V7100_RAW[0]!=b'S'||V7100_RAW[1]!=b'7'||V7100_RAW[2]!=b'1'||V7100_RAW[3]!=b'0'||V7100_RAW[4]!=1 { return false; }
    let n27=V7100_RAW[5] as usize; let x27=V7100_RAW[6] as usize; let n28=V7100_RAW[7] as usize; let x28=V7100_RAW[8] as usize;
    if n27>V7100_CAL_CAP||n28>V7100_CAL_CAP||x27>=V7100_CAL_CAP||x28>=V7100_CAL_CAP { return false; }
    let want=(V7100_RAW[112] as u32)|((V7100_RAW[113] as u32)<<8)|((V7100_RAW[114] as u32)<<16)|((V7100_RAW[115] as u32)<<24); if want!=v798_fnv32(&V7100_RAW[..112]) { return false; }
    V7100_N27=n27 as u8; V7100_NEXT27=x27 as u8; V7100_N28=n28 as u8; V7100_NEXT28=x28 as u8;
    for i in 0..V7100_CAL_CAP { let a=16+i*4; V7100_C27[i]=(V7100_RAW[a] as u16)|((V7100_RAW[a+1] as u16)<<8); V7100_K27[i]=((V7100_RAW[a+2] as u16)|((V7100_RAW[a+3] as u16)<<8)) as i16; let d=48+i*4; V7100_C28[i]=(V7100_RAW[d] as u16)|((V7100_RAW[d+1] as u16)<<8); V7100_K28[i]=((V7100_RAW[d+2] as u16)|((V7100_RAW[d+3] as u16)<<8)) as i16; }
    V7100_LIFE_N27=(V7100_RAW[80] as u32)|((V7100_RAW[81] as u32)<<8)|((V7100_RAW[82] as u32)<<16)|((V7100_RAW[83] as u32)<<24);
    V7100_LIFE_SUM27=(V7100_RAW[84] as u32)|((V7100_RAW[85] as u32)<<8)|((V7100_RAW[86] as u32)<<16)|((V7100_RAW[87] as u32)<<24); V7100_LIFE_SQ27=0; for j in 0..8 {V7100_LIFE_SQ27|=(V7100_RAW[88+j] as u64)<<(j*8);}
    V7100_LIFE_N28=(V7100_RAW[96] as u32)|((V7100_RAW[97] as u32)<<8)|((V7100_RAW[98] as u32)<<16)|((V7100_RAW[99] as u32)<<24);
    V7100_LIFE_SUM28=(V7100_RAW[100] as u32)|((V7100_RAW[101] as u32)<<8)|((V7100_RAW[102] as u32)<<16)|((V7100_RAW[103] as u32)<<24); V7100_LIFE_SQ28=0; for j in 0..8 {V7100_LIFE_SQ28|=(V7100_RAW[104+j] as u64)<<(j*8);}
    v7100_recompute_recent(); if V7100_LIFE_N27<V7100_N27 as u32 || V7100_LIFE_N28<V7100_N28 as u32 { v7100_seed_life_from_rings(); } else { v7100_recompute_life(); } true
}

unsafe fn v7100_encode() {
    for b in V7100_RAW.iter_mut(){*b=0;} V7100_RAW[0]=b'S';V7100_RAW[1]=b'7';V7100_RAW[2]=b'1';V7100_RAW[3]=b'0';V7100_RAW[4]=1; V7100_RAW[5]=V7100_N27;V7100_RAW[6]=V7100_NEXT27;V7100_RAW[7]=V7100_N28;V7100_RAW[8]=V7100_NEXT28;
    for i in 0..V7100_CAL_CAP { let a=16+i*4; let x=V7100_C27[i]; let y=V7100_K27[i] as u16; V7100_RAW[a]=(x&255) as u8;V7100_RAW[a+1]=(x>>8) as u8;V7100_RAW[a+2]=(y&255) as u8;V7100_RAW[a+3]=(y>>8) as u8; let d=48+i*4; let x=V7100_C28[i]; let y=V7100_K28[i] as u16; V7100_RAW[d]=(x&255) as u8;V7100_RAW[d+1]=(x>>8) as u8;V7100_RAW[d+2]=(y&255) as u8;V7100_RAW[d+3]=(y>>8) as u8; }
    for j in 0..4 {V7100_RAW[80+j]=((V7100_LIFE_N27>>(j*8))&255) as u8;V7100_RAW[84+j]=((V7100_LIFE_SUM27>>(j*8))&255) as u8;V7100_RAW[96+j]=((V7100_LIFE_N28>>(j*8))&255) as u8;V7100_RAW[100+j]=((V7100_LIFE_SUM28>>(j*8))&255) as u8;} for j in 0..8 {V7100_RAW[88+j]=((V7100_LIFE_SQ27>>(j*8))&255) as u8;V7100_RAW[104+j]=((V7100_LIFE_SQ28>>(j*8))&255) as u8;}
    let h=v798_fnv32(&V7100_RAW[..112]); for j in 0..4 {V7100_RAW[112+j]=((h>>(j*8))&255) as u8;}
}

unsafe fn v7100_ensure() { if V7100_ATTEMPTED{return;} V7100_ATTEMPTED=true; let dst=core::ptr::addr_of_mut!(V7100_RAW).cast::<u8>(); V7100_LOAD_LEN=pnp::v7100_cal_load(dst,V7100_CAL_BYTES as u32); V7100_FROM_FILE=V7100_LOAD_LEN==V7100_CAL_BYTES as u32 && v7100_decode(); if !V7100_FROM_FILE { V7100_N27=0;V7100_NEXT27=0;V7100_N28=0;V7100_NEXT28=0; for i in 0..V7100_CAL_CAP {V7100_C27[i]=0;V7100_K27[i]=0;V7100_C28[i]=0;V7100_K28[i]=0;} V7100_LIFE_N27=0;V7100_LIFE_SUM27=0;V7100_LIFE_SQ27=0;V7100_LIFE_N28=0;V7100_LIFE_SUM28=0;V7100_LIFE_SQ28=0; v7100_recompute_recent();v7100_recompute_life(); } }
unsafe fn v7100_predict_from_cycles(c27:u16,c28:u16) { v7100_ensure(); V7100_PRED_N27=V7100_N27;V7100_PRED_N28=V7100_N28;V7100_PRED_K27_10=V7100_MEAN_K27_10;V7100_PRED_K28_10=V7100_MEAN_K28_10;V7100_J27_10=(c27 as i32)*10-V7100_PRED_K27_10;V7100_J28_10=(c28 as i32)*10-V7100_PRED_K28_10; }
unsafe fn v7100_life_add(s1:u8,k:i32) { let ku=k as u32; let sq=(ku as u64)*(ku as u64); if s1==27 {if V7100_LIFE_N27!=u32::MAX&&V7100_LIFE_SUM27<=u32::MAX-ku{V7100_LIFE_N27+=1;V7100_LIFE_SUM27+=ku;V7100_LIFE_SQ27=V7100_LIFE_SQ27.saturating_add(sq);}} else if s1==28 {if V7100_LIFE_N28!=u32::MAX&&V7100_LIFE_SUM28<=u32::MAX-ku{V7100_LIFE_N28+=1;V7100_LIFE_SUM28+=ku;V7100_LIFE_SQ28=V7100_LIFE_SQ28.saturating_add(sq);}} v7100_recompute_life(); }
unsafe fn v7100_add_sample(cycles:u16,actual_j:i32,s1:u8,target:u32) { if target==V7100_LAST_TARGET||cycles==0||(s1!=27&&s1!=28){return;} let k=(cycles as i32)-actual_j;if k<V7100_K_MIN||k>V7100_K_MAX{return;}v7100_ensure();if s1==27{let i=V7100_NEXT27 as usize;V7100_C27[i]=cycles;V7100_K27[i]=k as i16;if V7100_N27<V7100_CAL_CAP as u8{V7100_N27+=1;}V7100_NEXT27=((i+1)%V7100_CAL_CAP) as u8;}else{let i=V7100_NEXT28 as usize;V7100_C28[i]=cycles;V7100_K28[i]=k as i16;if V7100_N28<V7100_CAL_CAP as u8{V7100_N28+=1;}V7100_NEXT28=((i+1)%V7100_CAL_CAP) as u8;}V7100_LAST_TARGET=target;V7100_ADDED=true;V7100_ADDED_S1=s1;V7100_ADDED_CYCLES=cycles;V7100_ADDED_K=k as i16;V7100_DIRTY=true;v7100_recompute_recent();v7100_life_add(s1,k); }
unsafe fn v7100_save_if_dirty() {if !V7100_DIRTY{return;}v7100_encode();let src=core::ptr::addr_of!(V7100_RAW).cast::<u8>();V7100_SAVE_LEN=pnp::v7100_cal_save(src,V7100_CAL_BYTES as u32);if V7100_SAVE_LEN==V7100_CAL_BYTES as u32{V7100_DIRTY=false;V7100_FROM_FILE=true;}}

'''
t=rep(t,needle,insert,'insert split calibration')
t=rep(t,'        v798_predict_from_cycles(c27,c28);\n        V796_JPRED_VALID = true;\n','        v798_predict_from_cycles(c27,c28);\n        v7100_predict_from_cycles(c27,c28);\n        V796_JPRED_VALID = true;\n','split predict call')
t=rep(t,'            V798_CAL_SAVE_LEN = 0;\n            for i in 0..V792_AUDIO_PRE_LEN {\n','            V798_CAL_SAVE_LEN = 0;\n            V7100_ADDED=false; V7100_ADDED_S1=0; V7100_ADDED_CYCLES=0; V7100_ADDED_K=0; V7100_SAVE_LEN=0;\n            for i in 0..V792_AUDIO_PRE_LEN {\n','split run reset')
t=rep(t,'                    if V796_JPRED_VALID { v798_add_sample(cyc,self.early_j_a,self.probe_target.advance); }\n','                    if V796_JPRED_VALID { v798_add_sample(cyc,self.early_j_a,self.probe_target.advance); v7100_add_sample(cyc,self.early_j_a,s1 as u8,self.probe_target.advance); }\n','split learn call')
t=rep(t,'        unsafe { v798_save_cal_if_dirty(); }\n        set_vblank_context_capture(true);\n','        unsafe { v798_save_cal_if_dirty(); v7100_save_if_dirty(); }\n        set_vblank_context_capture(true);\n','split save call')
needle='''        unsafe { let _=write!(line,"LIFECAL,V799,{},{},{},{},{}\\n",V799_LIFE_COUNT,V799_LIFE_MEAN_K10,V799_LIFE_VAR_K100,V799_DRIFT_D10,V799_DRIFT_WARN as u8); }
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");
'''
insert='''        unsafe { let _=write!(line,"LIFECAL,V799,{},{},{},{},{}\\n",V799_LIFE_COUNT,V799_LIFE_MEAN_K10,V799_LIFE_VAR_K100,V799_DRIFT_D10,V799_DRIFT_WARN as u8); }
        pnp::trace_file_write(line.as_bytes());
        line.clear(); let _=write!(line,"\\ns1cal,version,from_file,load_len,pred_n27,pred_k27_x10,pred_n28,pred_k28_x10,j27_x10,j28_x10,post_n27,post_k27_x10,post_n28,post_k28_x10,added,added_s1,added_cycles,added_k,life_n27,life_mean27_x10,life_var27_x100,drift27_x10,warn27,life_n28,life_mean28_x10,life_var28_x100,drift28_x10,warn28,dirty,save_len\\n"); pnp::trace_file_write(line.as_bytes()); line.clear();
        unsafe { let _=write!(line,"S1CAL,V7100,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n",V7100_FROM_FILE as u8,V7100_LOAD_LEN,V7100_PRED_N27,V7100_PRED_K27_10,V7100_PRED_N28,V7100_PRED_K28_10,V7100_J27_10,V7100_J28_10,V7100_N27,V7100_MEAN_K27_10,V7100_N28,V7100_MEAN_K28_10,V7100_ADDED as u8,V7100_ADDED_S1,V7100_ADDED_CYCLES,V7100_ADDED_K,V7100_LIFE_N27,V7100_LIFE_MEAN27_10,V7100_LIFE_VAR27_100,V7100_DRIFT27_10,V7100_WARN27 as u8,V7100_LIFE_N28,V7100_LIFE_MEAN28_10,V7100_LIFE_VAR28_100,V7100_DRIFT28_10,V7100_WARN28 as u8,V7100_DIRTY as u8,V7100_SAVE_LEN); }
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");
'''
t=rep(t,needle,insert,'split csv')
needle='''                    pnp::println!("S799 SELFCAL READY N{}", V798_PRED_COUNT);
                    pnp::println!("Kx10 {} {}", V798_PRED_K10, if V798_PRED_COUNT==0 {"PRIOR"} else {"MEAN"});
                    pnp::println!("Jmean {} / {}", V798_JMEAN27_10, V798_JMEAN28_10);
                    if V798_PRED_SLOPE_VALID { pnp::println!("Jlin {} / {} DIAG",V798_JLIN27_10,V798_JLIN28_10); }
                    if V799_DRIFT_WARN { pnp::println!("KDRIFT d10 {} LIFE N{}",V799_DRIFT_D10,V799_LIFE_COUNT); }
                    pnp::println!("PRESS UP BLIND + FINAL DV");
'''
insert='''                    pnp::println!("S710 S1CAL N27{} N28{}",V7100_PRED_N27,V7100_PRED_N28);
                    pnp::println!("K27 {} K28 {}",V7100_PRED_K27_10,V7100_PRED_K28_10);
                    pnp::println!("J27 {} J28 {}",V7100_J27_10,V7100_J28_10);
                    if V7100_WARN27||V7100_WARN28 { pnp::println!("KDRIFT27 {} KDRIFT28 {}",V7100_DRIFT27_10,V7100_DRIFT28_10); }
                    pnp::println!("PRESS UP BLIND + FINAL DV");
'''
t=rep(t,needle,insert,'split UI')
t=t.replace('STALLPHASE,V799,rel0-40+vblankirq+cpuctx84+audiopre+jpred+selfcal8+lifek+kbranch+finaldv','STALLPHASE,V7100,rel0-40+vblankirq+cpuctx84+audiopre+jpred+s1cal8x2+lifek2+kbranch+finaldv')
needle='''    pub fn host_v798_cal_load(dst: *mut u8, len: u32) -> u32;
    pub fn host_v798_cal_save(src: *const u8, len: u32) -> u32;
'''; b=rep(b,needle,needle+'''    pub fn host_v7100_cal_load(dst: *mut u8, len: u32) -> u32;
    pub fn host_v7100_cal_save(src: *const u8, len: u32) -> u32;
''','binding declarations')
needle='''    pub extern "C" fn host_v798_cal_load(_dst: *mut u8, _len: u32) -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_v798_cal_save(_src: *const u8, _len: u32) -> u32 { 0 }
'''; b=rep(b,needle,needle+'''    #[no_mangle]
    pub extern "C" fn host_v7100_cal_load(_dst: *mut u8, _len: u32) -> u32 { 0 }
    #[no_mangle]
    pub extern "C" fn host_v7100_cal_save(_src: *const u8, _len: u32) -> u32 { 0 }
''','binding stubs')
needle='''pub unsafe fn v798_cal_load(dst:*mut u8,len:u32)->u32 { bindings::host_v798_cal_load(dst,len) }
pub unsafe fn v798_cal_save(src:*const u8,len:u32)->u32 { bindings::host_v798_cal_save(src,len) }
'''; u=rep(u,needle,needle+'''pub unsafe fn v7100_cal_load(dst:*mut u8,len:u32)->u32 { bindings::host_v7100_cal_load(dst,len) }
pub unsafe fn v7100_cal_save(src:*const u8,len:u32)->u32 { bindings::host_v7100_cal_save(src,len) }
''','utils wrappers')
needle='''u32 host_trace_request(void)
{
'''; insert='''u32 host_v7100_cal_load(void *dst, u32 len)
{
    FS_Archive sdmc; Handle file=0; u64 size=0; u32 bytes_read=0; Result res;
    if (dst==NULL || len==0) return 0; res=fsInit(); if (R_FAILED(res)) return 0; res=FSUSER_OpenArchive(&sdmc,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")); if (R_FAILED(res)) { fsExit(); return 0; }
    res=FSUSER_OpenFile(&file,sdmc,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/suicune_j_cal_v7100.bin"),FS_OPEN_READ,0); if (R_SUCCEEDED(res)) res=FSFILE_GetSize(file,&size); if (R_SUCCEEDED(res) && size==(u64)len) res=FSFILE_Read(file,&bytes_read,0,dst,len); if (file!=0) FSFILE_Close(file); FSUSER_CloseArchive(sdmc); fsExit(); if (R_FAILED(res) || size!=(u64)len || bytes_read!=len) return 0; return bytes_read;
}
u32 host_v7100_cal_save(const void *src, u32 len)
{
    FS_Archive sdmc; Handle file=0; u32 written=0; Result res;
    if (src==NULL || len==0) return 0; res=fsInit(); if (R_FAILED(res)) return 0; res=FSUSER_OpenArchive(&sdmc,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")); if (R_FAILED(res)) { fsExit(); return 0; }
    FSUSER_CreateDirectory(sdmc,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader"),0); res=FSUSER_OpenFile(&file,sdmc,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/suicune_j_cal_v7100.bin"),FS_OPEN_WRITE|FS_OPEN_CREATE,0); if (R_SUCCEEDED(res)) res=FSFILE_SetSize(file,0); if (R_SUCCEEDED(res)) res=FSFILE_Write(file,&written,0,src,len,FS_WRITE_FLUSH); if (file!=0) FSFILE_Close(file); FSUSER_CloseArchive(sdmc); fsExit(); if (R_FAILED(res) || written!=len) return 0; return written;
}

u32 host_trace_request(void)
{
'''; c=rep(c,needle,insert,'host fs functions')
T.write_text(t);B.write_text(b);U.write_text(u);C.write_text(c)
print('Applied v7.10.0 s1-split self-calibration')
