#!/usr/bin/env python3
from pathlib import Path

T=Path('reader_core/src/crystal/trace.rs')
B=Path('reader_core/src/pnp/bindings.rs')
U=Path('reader_core/src/pnp/utils.rs')
C=Path('3gx/sources/main.c')
t=T.read_text(); b=B.read_text(); u=U.read_text(); c=C.read_text()

def rep(src, old, new, label):
    n=src.count(old)
    if n != 1:
        raise SystemExit(f'v798 {label}: expected 1 match, got {n}')
    return src.replace(old,new,1)

needle='''static mut V797_CONTINUED_NONSHINY: bool = false;\n'''
insert='''static mut V797_CONTINUED_NONSHINY: bool = false;\n\n// v7.9.8 self-calibration.  The active production-facing estimate is the\n// recent-K mean only.  A slope is computed/logged diagnostically, but is NOT\n// used to gate physical UP until it earns blind validation.\nconst V798_CAL_CAP: usize = 8;\nconst V798_CAL_BYTES: usize = 64;\nconst V798_CAL_FALLBACK_K10: i32 = 71089; // 15-run global prior: K=7108.9\nconst V798_CAL_K_MIN: i32 = 7000;\nconst V798_CAL_K_MAX: i32 = 7200;\nstatic mut V798_CAL_RAW: [u8; V798_CAL_BYTES] = [0; V798_CAL_BYTES];\nstatic mut V798_CAL_ATTEMPTED: bool = false;\nstatic mut V798_CAL_FROM_FILE: bool = false;\nstatic mut V798_CAL_LOAD_LEN: u32 = 0;\nstatic mut V798_CAL_COUNT: u8 = 0;\nstatic mut V798_CAL_NEXT: u8 = 0;\nstatic mut V798_CAL_CYCLES: [u16; V798_CAL_CAP] = [0; V798_CAL_CAP];\nstatic mut V798_CAL_K: [i16; V798_CAL_CAP] = [0; V798_CAL_CAP];\nstatic mut V798_CAL_MEAN_K10: i32 = V798_CAL_FALLBACK_K10;\nstatic mut V798_CAL_MEAN_CYCLES10: i32 = 0;\nstatic mut V798_CAL_SLOPE_PPM: i32 = 0; // slope of K vs cycles, diagnostic only\nstatic mut V798_CAL_SLOPE_VALID: bool = false;\nstatic mut V798_CAL_DIRTY: bool = false;\nstatic mut V798_CAL_SAVE_LEN: u32 = 0;\nstatic mut V798_CAL_LAST_TARGET: u32 = 0xffffffff;\nstatic mut V798_CAL_ADDED_THIS_RUN: bool = false;\nstatic mut V798_CAL_PENDING_CYCLES: u16 = 0;\nstatic mut V798_CAL_PENDING_K: i16 = 0;\nstatic mut V798_JMEAN27_10: i32 = 0;\nstatic mut V798_JMEAN28_10: i32 = 0;\nstatic mut V798_JLIN27_10: i32 = 0;\nstatic mut V798_JLIN28_10: i32 = 0;\n\nfn v798_fnv32(data: &[u8]) -> u32 {\n    let mut h = 0x811c9dc5u32;\n    for b in data.iter() {\n        h ^= *b as u32;\n        h = h.wrapping_mul(0x01000193);\n    }\n    h\n}\n\nunsafe fn v798_cal_recompute() {\n    let n = V798_CAL_COUNT as usize;\n    if n == 0 {\n        V798_CAL_MEAN_K10 = V798_CAL_FALLBACK_K10;\n        V798_CAL_MEAN_CYCLES10 = 0;\n        V798_CAL_SLOPE_PPM = 0;\n        V798_CAL_SLOPE_VALID = false;\n        return;\n    }\n    let mut sx: i64 = 0;\n    let mut sy: i64 = 0;\n    let mut sxx: i64 = 0;\n    let mut sxy: i64 = 0;\n    for i in 0..n {\n        let x = V798_CAL_CYCLES[i] as i64;\n        let y = V798_CAL_K[i] as i64;\n        sx += x; sy += y; sxx += x*x; sxy += x*y;\n    }\n    V798_CAL_MEAN_K10 = ((sy * 10 + (n as i64)/2) / n as i64) as i32;\n    V798_CAL_MEAN_CYCLES10 = ((sx * 10 + (n as i64)/2) / n as i64) as i32;\n    let nn = n as i64;\n    let cov = nn*sxy - sx*sy;\n    let var = nn*sxx - sx*sx;\n    if n >= 4 && var != 0 {\n        let ppm = cov.saturating_mul(1_000_000) / var;\n        V798_CAL_SLOPE_PPM = ppm.max(-100_000).min(100_000) as i32;\n        V798_CAL_SLOPE_VALID = true;\n    } else {\n        V798_CAL_SLOPE_PPM = 0;\n        V798_CAL_SLOPE_VALID = false;\n    }\n}\n\nunsafe fn v798_cal_decode() -> bool {\n    if V798_CAL_RAW[0] != b'S' || V798_CAL_RAW[1] != b'7' || V798_CAL_RAW[2] != b'9' || V798_CAL_RAW[3] != b'8' || V798_CAL_RAW[4] != 1 { return false; }\n    let count = V798_CAL_RAW[5] as usize;\n    let next = V798_CAL_RAW[6] as usize;\n    if count > V798_CAL_CAP || next >= V798_CAL_CAP { return false; }\n    let want = (V798_CAL_RAW[40] as u32) | ((V798_CAL_RAW[41] as u32)<<8) | ((V798_CAL_RAW[42] as u32)<<16) | ((V798_CAL_RAW[43] as u32)<<24);\n    let got = v798_fnv32(&V798_CAL_RAW[..40]);\n    if want != got { return false; }\n    for i in 0..V798_CAL_CAP {\n        let o=8+i*4;\n        let x=(V798_CAL_RAW[o] as u16)|((V798_CAL_RAW[o+1] as u16)<<8);\n        let y=((V798_CAL_RAW[o+2] as u16)|((V798_CAL_RAW[o+3] as u16)<<8)) as i16;\n        V798_CAL_CYCLES[i]=x; V798_CAL_K[i]=y;\n    }\n    V798_CAL_COUNT=count as u8; V798_CAL_NEXT=next as u8;\n    v798_cal_recompute();\n    true\n}\n\nunsafe fn v798_cal_encode() {\n    for b in V798_CAL_RAW.iter_mut() { *b=0; }\n    V798_CAL_RAW[0]=b'S'; V798_CAL_RAW[1]=b'7'; V798_CAL_RAW[2]=b'9'; V798_CAL_RAW[3]=b'8';\n    V798_CAL_RAW[4]=1; V798_CAL_RAW[5]=V798_CAL_COUNT; V798_CAL_RAW[6]=V798_CAL_NEXT;\n    for i in 0..V798_CAL_CAP {\n        let o=8+i*4; let x=V798_CAL_CYCLES[i]; let y=V798_CAL_K[i] as u16;\n        V798_CAL_RAW[o]=(x&0xff) as u8; V798_CAL_RAW[o+1]=(x>>8) as u8;\n        V798_CAL_RAW[o+2]=(y&0xff) as u8; V798_CAL_RAW[o+3]=(y>>8) as u8;\n    }\n    let sum=v798_fnv32(&V798_CAL_RAW[..40]);\n    V798_CAL_RAW[40]=(sum&0xff) as u8; V798_CAL_RAW[41]=((sum>>8)&0xff) as u8;\n    V798_CAL_RAW[42]=((sum>>16)&0xff) as u8; V798_CAL_RAW[43]=((sum>>24)&0xff) as u8;\n}\n\nunsafe fn v798_ensure_cal() {\n    if V798_CAL_ATTEMPTED { return; }\n    V798_CAL_ATTEMPTED=true;\n    let dst=core::ptr::addr_of_mut!(V798_CAL_RAW).cast::<u8>();\n    let got=pnp::v798_cal_load(dst,V798_CAL_BYTES as u32);\n    V798_CAL_LOAD_LEN=got;\n    V798_CAL_FROM_FILE=got==V798_CAL_BYTES as u32 && v798_cal_decode();\n    if !V798_CAL_FROM_FILE {\n        V798_CAL_COUNT=0; V798_CAL_NEXT=0;\n        for i in 0..V798_CAL_CAP { V798_CAL_CYCLES[i]=0; V798_CAL_K[i]=0; }\n        v798_cal_recompute();\n    }\n}\n\nunsafe fn v798_predict_from_cycles(c27:u16,c28:u16) {\n    v798_ensure_cal();\n    V798_JMEAN27_10=(c27 as i32)*10-V798_CAL_MEAN_K10;\n    V798_JMEAN28_10=(c28 as i32)*10-V798_CAL_MEAN_K10;\n    let lin_k = |c:u16| -> i32 {\n        if !V798_CAL_SLOPE_VALID { return V798_CAL_MEAN_K10; }\n        let dx10=(c as i32)*10-V798_CAL_MEAN_CYCLES10;\n        V798_CAL_MEAN_K10 + (((V798_CAL_SLOPE_PPM as i64)*(dx10 as i64))/1_000_000) as i32\n    };\n    V798_JLIN27_10=(c27 as i32)*10-lin_k(c27);\n    V798_JLIN28_10=(c28 as i32)*10-lin_k(c28);\n}\n\nunsafe fn v798_add_sample(cycles:u16, actual_j:i32, target:u32) {\n    if target==V798_CAL_LAST_TARGET || cycles==0 { return; }\n    let k=(cycles as i32)-actual_j;\n    if k<V798_CAL_K_MIN || k>V798_CAL_K_MAX { return; }\n    v798_ensure_cal();\n    let idx=V798_CAL_NEXT as usize;\n    V798_CAL_CYCLES[idx]=cycles; V798_CAL_K[idx]=k as i16;\n    if V798_CAL_COUNT < V798_CAL_CAP as u8 { V798_CAL_COUNT += 1; }\n    V798_CAL_NEXT=((idx+1)%V798_CAL_CAP) as u8;\n    V798_CAL_LAST_TARGET=target; V798_CAL_ADDED_THIS_RUN=true;\n    V798_CAL_PENDING_CYCLES=cycles; V798_CAL_PENDING_K=k as i16; V798_CAL_DIRTY=true;\n    v798_cal_recompute();\n}\n\nunsafe fn v798_save_cal_if_dirty() {\n    if !V798_CAL_DIRTY { return; }\n    v798_cal_encode();\n    let src=core::ptr::addr_of!(V798_CAL_RAW).cast::<u8>();\n    V798_CAL_SAVE_LEN=pnp::v798_cal_save(src,V798_CAL_BYTES as u32);\n    if V798_CAL_SAVE_LEN==V798_CAL_BYTES as u32 { V798_CAL_DIRTY=false; V798_CAL_FROM_FILE=true; }\n}\n'''
t=rep(t,needle,insert,'globals/selfcal')

needle='''        V796_JPRED_MIN10 = center_min - V796_RESID10;\n        V796_JPRED_MAX10 = center_max + V796_RESID10;\n        V796_JPRED_VALID = true;\n'''
insert='''        V796_JPRED_MIN10 = center_min - V796_RESID10;\n        V796_JPRED_MAX10 = center_max + V796_RESID10;\n        v798_predict_from_cycles(c27,c28);\n        V796_JPRED_VALID = true;\n'''
t=rep(t,needle,insert,'predict selfcal')

needle='''            V797_TAIL_VALID = false;\n            V797_TAIL_CANDIDATES = 0;\n            V797_TAIL_SHINY_COUNT = 0;\n            V797_CONTINUED_NONSHINY = false;\n'''
insert='''            V797_TAIL_VALID = false;\n            V797_TAIL_CANDIDATES = 0;\n            V797_TAIL_SHINY_COUNT = 0;\n            V797_CONTINUED_NONSHINY = false;\n            V798_CAL_ADDED_THIS_RUN = false;\n            V798_CAL_PENDING_CYCLES = 0;\n            V798_CAL_PENDING_K = 0;\n            V798_CAL_SAVE_LEN = 0;\n'''
t=rep(t,needle,insert,'per-run reset')

needle='''                self.early_post1 = early_point(e);\n                self.early_j_a = phase_step_m(self.early_pre.ap4, self.early_post1.ap4) - 1172;\n                self.early_j_s = phase_step_m(self.early_pre.sp4, self.early_post1.sp4) - 1172;\n'''
insert='''                self.early_post1 = early_point(e);\n                self.early_j_a = phase_step_m(self.early_pre.ap4, self.early_post1.ap4) - 1172;\n                self.early_j_s = phase_step_m(self.early_pre.sp4, self.early_post1.sp4) - 1172;\n                unsafe {\n                    // early_pre rel is the actual s1 branch (27 or 28).\n                    // Update RAM only; SD persistence waits until final DV is locked.\n                    let s1=self.early_pre.advance.wrapping_sub(self.probe_target.advance);\n                    let cyc=if s1==27 {V796_JPRED_C27} else if s1==28 {V796_JPRED_C28} else {0};\n                    if V796_JPRED_VALID { v798_add_sample(cyc,self.early_j_a,self.probe_target.advance); }\n                }\n'''
t=rep(t,needle,insert,'learn at actual J')

needle='''        line.clear();\n        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");\n'''
insert='''        line.clear();\n        let _ = write!(line, "\\nselfcal,version,from_file,load_len,count,next,mean_k_x10,mean_cycles_x10,slope_ppm,slope_valid,jmean27_x10,jmean28_x10,jlin27_x10,jlin28_x10,added_this_run,added_cycles,added_k,dirty,save_len\\n");\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        unsafe {\n            let _=write!(line,"SELFCAL,V798,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n",\n                V798_CAL_FROM_FILE as u8,V798_CAL_LOAD_LEN,V798_CAL_COUNT,V798_CAL_NEXT,\n                V798_CAL_MEAN_K10,V798_CAL_MEAN_CYCLES10,V798_CAL_SLOPE_PPM,V798_CAL_SLOPE_VALID as u8,\n                V798_JMEAN27_10,V798_JMEAN28_10,V798_JLIN27_10,V798_JLIN28_10,\n                V798_CAL_ADDED_THIS_RUN as u8,V798_CAL_PENDING_CYCLES,V798_CAL_PENDING_K,\n                V798_CAL_DIRTY as u8,V798_CAL_SAVE_LEN);\n        }\n        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");\n'''
t=rep(t,needle,insert,'SELFCAL csv')

needle='''        pnp::trace_file_close();\n        set_vblank_context_capture(true);\n'''
insert='''        pnp::trace_file_close();\n        unsafe { v798_save_cal_if_dirty(); }\n        set_vblank_context_capture(true);\n'''
t=rep(t,needle,insert,'persist after result')

old='''                if V796_JPRED_VALID {\n                    pnp::println!("S797 JPRED READY");\n                    pnp::println!("C27 {} C28 {}", V796_JPRED_C27, V796_JPRED_C28);\n                    pnp::println!("Jx10 {} / {}", V796_JPRED_J27_10, V796_JPRED_J28_10);\n                    pnp::println!("WINx10 {}..{}", V796_JPRED_MIN10, V796_JPRED_MAX10);\n                    pnp::println!("PRESS UP BLIND + FINAL DV");\n'''
new='''                if V796_JPRED_VALID {\n                    pnp::println!("S798 SELFCAL READY N{}", V798_CAL_COUNT);\n                    pnp::println!("Kx10 {} {}", V798_CAL_MEAN_K10, if V798_CAL_COUNT==0 {"PRIOR"} else {"MEAN"});\n                    pnp::println!("Jmean {} / {}", V798_JMEAN27_10, V798_JMEAN28_10);\n                    if V798_CAL_SLOPE_VALID { pnp::println!("Jlin {} / {} DIAG",V798_JLIN27_10,V798_JLIN28_10); }\n                    pnp::println!("PRESS UP BLIND + FINAL DV");\n'''
t=rep(t,old,new,'overlay')

t=rep(t,
    'STALLPHASE,V797,rel0-40+vblankirq+cpuctx84+audiopre+jpred-sd+kbranch+finaldv',
    'STALLPHASE,V798,rel0-40+vblankirq+cpuctx84+audiopre+jpred+selfcal8+kbranch+finaldv',
    'version marker')

b=rep(b,
'''    pub fn host_v796_table_load(dst: *mut u8, len: u32) -> u32;\n    pub fn get_remaster_version() -> u16;\n''',
'''    pub fn host_v796_table_load(dst: *mut u8, len: u32) -> u32;\n    pub fn host_v798_cal_load(dst: *mut u8, len: u32) -> u32;\n    pub fn host_v798_cal_save(src: *const u8, len: u32) -> u32;\n    pub fn get_remaster_version() -> u16;\n''','binding decl')
b=rep(b,
'''    pub extern "C" fn host_v796_table_load(_dst: *mut u8, _len: u32) -> u32 {\n        0\n    }\n    #[no_mangle]\n    pub extern "C" fn osGetTime() -> u64 {\n''',
'''    pub extern "C" fn host_v796_table_load(_dst: *mut u8, _len: u32) -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_v798_cal_load(_dst: *mut u8, _len: u32) -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_v798_cal_save(_src: *const u8, _len: u32) -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn osGetTime() -> u64 {\n''','binding stubs')
if 'pub unsafe fn v798_cal_load' in u: raise SystemExit('v798 utils already present')
u += '''\n/// v7.9.8 calibration persistence. No guest memory is modified.\npub unsafe fn v798_cal_load(dst:*mut u8,len:u32)->u32 { bindings::host_v798_cal_load(dst,len) }\npub unsafe fn v798_cal_save(src:*const u8,len:u32)->u32 { bindings::host_v798_cal_save(src,len) }\n'''

anchor='''u32 host_trace_request(void)\n{\n'''
cfunc=r'''u32 host_v798_cal_load(void *dst, u32 len)
{
    FS_Archive sdmc; Handle file=0; u64 size=0; u32 bytes_read=0; Result res;
    if (dst==NULL || len==0) return 0;
    res=fsInit(); if (R_FAILED(res)) return 0;
    res=FSUSER_OpenArchive(&sdmc,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,""));
    if (R_FAILED(res)) { fsExit(); return 0; }
    res=FSUSER_OpenFile(&file,sdmc,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/suicune_j_cal_v798.bin"),FS_OPEN_READ,0);
    if (R_SUCCEEDED(res)) res=FSFILE_GetSize(file,&size);
    if (R_SUCCEEDED(res) && size==(u64)len) res=FSFILE_Read(file,&bytes_read,0,dst,len);
    if (file!=0) FSFILE_Close(file); FSUSER_CloseArchive(sdmc); fsExit();
    if (R_FAILED(res) || size!=(u64)len || bytes_read!=len) return 0;
    return bytes_read;
}

u32 host_v798_cal_save(const void *src, u32 len)
{
    FS_Archive sdmc; Handle file=0; u32 written=0; Result res;
    if (src==NULL || len==0) return 0;
    res=fsInit(); if (R_FAILED(res)) return 0;
    res=FSUSER_OpenArchive(&sdmc,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,""));
    if (R_FAILED(res)) { fsExit(); return 0; }
    FSUSER_CreateDirectory(sdmc,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader"),0);
    res=FSUSER_OpenFile(&file,sdmc,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/suicune_j_cal_v798.bin"),FS_OPEN_WRITE|FS_OPEN_CREATE,0);
    if (R_SUCCEEDED(res)) res=FSFILE_SetSize(file,0);
    if (R_SUCCEEDED(res)) res=FSFILE_Write(file,&written,0,src,len,FS_WRITE_FLUSH);
    if (file!=0) FSFILE_Close(file); FSUSER_CloseArchive(sdmc); fsExit();
    if (R_FAILED(res) || written!=len) return 0;
    return written;
}

'''
if c.count(anchor)!=1: raise SystemExit(f'v798 C anchor expected 1 got {c.count(anchor)}')
c=c.replace(anchor,cfunc+anchor,1)

T.write_text(t); B.write_text(b); U.write_text(u); C.write_text(c)
print('Applied v7.9.8 self-cal J: recent-8 K mean persisted after final DV; slope diagnostic only')
