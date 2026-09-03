#!/usr/bin/env python3
from pathlib import Path
import re

H = Path('reader_core/src/crystal/hook.rs')
T = Path('reader_core/src/crystal/trace.rs')
F = Path('reader_core/src/crystal/frame.rs')
M = Path('3gx/sources/main.c')
B = Path('reader_core/src/pnp/bindings.rs')
PH = Path('reader_core/src/pnp/hook.rs')

h=H.read_text(); t=T.read_text(); f=F.read_text(); m=M.read_text(); b=B.read_text(); ph=PH.read_text()


def need(c,msg):
    if not c: raise SystemExit('v747 '+msg)

def rep(s,old,new,msg):
    n=s.count(old)
    if n!=1: raise SystemExit(f'v747 {msg}: expected 1 got {n}')
    return s.replace(old,new,1)

# ---------------------------------------------------------------------------
# A. Host frame index + raw hook tick. This is independent of any guessed
#    4,481,233-tick period. It gives a drift-free coarse mod16 plus raw fine
#    timing to every recorded VC frame.
# ---------------------------------------------------------------------------
if 'static mut HOST_FRAME_INDEX_V747' not in h:
    anchor='static mut STICKS: u64 = 0;'
    need(anchor in h,'STICKS anchor missing')
    extra=r'''

// v7.4.7 drift-free host-frame telemetry. Updated only from run_frame(), not
// from the rDIV hook, so it does not perturb the intra-frame Random path.
static mut HOST_FRAME_INDEX_V747: u32 = 0;
static mut HOST_FRAME_TICK_V747: u64 = 0;
static mut HOST_FRAME_DELTA_V747: u64 = 0;

pub fn mark_host_frame_v747() {
    let now=pnp::system_tick();
    unsafe {
        HOST_FRAME_DELTA_V747=if HOST_FRAME_TICK_V747==0{0}else{now.wrapping_sub(HOST_FRAME_TICK_V747)};
        HOST_FRAME_TICK_V747=now;
        HOST_FRAME_INDEX_V747=HOST_FRAME_INDEX_V747.wrapping_add(1);
    }
}

pub fn host_frame_metrics_v747()->(u32,u64,u64){
    unsafe{(HOST_FRAME_INDEX_V747,HOST_FRAME_TICK_V747,HOST_FRAME_DELTA_V747)}
}
'''
    h=h.replace(anchor,anchor+extra,1)

# ---------------------------------------------------------------------------
# B. Lightweight paired Random-phase log.
# Existing DeepEntry is intentionally preserved: it remains the expensive
# 2F60 CPU/WRAM/HRAM snapshot. RANDOM_PHASE_LOG only stores the timing/phase
# values needed to solve deep base/gap quantization and captures BOTH 2F60/2F68.
# ---------------------------------------------------------------------------
if 'pub struct RandomPhaseEntryV747' not in h:
    anchor='static mut DEEP_LOG: [DeepEntry; DEEP_LOG_LEN]'
    pos=h.find(anchor)
    need(pos>=0,'DEEP_LOG anchor missing')
    block=r'''
pub const RANDOM_PHASE_LOG_LEN_V747: usize = 256;

#[derive(Clone,Copy,Default)]
pub struct RandomPhaseEntryV747 {
    pub index:u32,
    pub advance:u32,
    pub pre_state:u16,
    pub pre_ap4:u16,
    pub pre_sp4:u16,
    pub normal_adiv:u8,
    pub normal_sdiv:u8,
    pub a_pc:u16,
    pub s_pc:u16,
    pub a_rdiv:u8,
    pub s_rdiv:u8,
    pub ap4:u16,
    pub sp4:u16,
    pub a_tick:u64,
    pub s_tick:u64,
    pub a_mcycle:u8,
    pub s_mcycle:u8,
    pub adiv_index:u16,
    pub sdiv_index:u16,
}

impl RandomPhaseEntryV747 {
    const EMPTY:Self=Self{
        index:0,advance:0,pre_state:0,pre_ap4:0,pre_sp4:0,
        normal_adiv:0,normal_sdiv:0,a_pc:0,s_pc:0,a_rdiv:0,s_rdiv:0,
        ap4:0,sp4:0,a_tick:0,s_tick:0,a_mcycle:0,s_mcycle:0,
        adiv_index:0,sdiv_index:0,
    };
}

static mut RANDOM_PHASE_LOG_V747:[RandomPhaseEntryV747;RANDOM_PHASE_LOG_LEN_V747]=
    [RandomPhaseEntryV747::EMPTY;RANDOM_PHASE_LOG_LEN_V747];
static mut RANDOM_PHASE_WRITE_V747:usize=0;
static mut RANDOM_PHASE_COUNT_V747:u32=0;
static mut RANDOM_PHASE_PENDING_V747:bool=false;
static mut RANDOM_PHASE_WORK_V747:RandomPhaseEntryV747=RandomPhaseEntryV747::EMPTY;

pub fn random_phase_count_v747()->u32{unsafe{RANDOM_PHASE_COUNT_V747}}
pub fn random_phase_entry_v747(index:usize)->RandomPhaseEntryV747{
    unsafe{
        let total=RANDOM_PHASE_COUNT_V747 as usize;
        let shown=total.min(RANDOM_PHASE_LOG_LEN_V747);
        if index>=shown{return RandomPhaseEntryV747::EMPTY}
        let start=if total>RANDOM_PHASE_LOG_LEN_V747{RANDOM_PHASE_WRITE_V747}else{0};
        RANDOM_PHASE_LOG_V747[(start+index)%RANDOM_PHASE_LOG_LEN_V747]
    }
}

fn capture_random_phase_v747(reader:&Gen2Reader,pc:u16,host_tick:u64,mcycle:u8){
    unsafe{if !DEEP_LOGGING{return;}}
    let phase=(((reader.div() as u16)<<6)|((mcycle as u16)&0x3f))&0x3fff;
    if pc==0x2f60{
        let pre_ap4=unsafe{(((ADIV as u16)<<6)|((ASUB as u16)&0x3f))&0x3fff};
        let pre_sp4=unsafe{(((SDIV as u16)<<6)|((SSUB as u16)&0x3f))&0x3fff};
        let normal_adiv=unsafe{ADIV}; let normal_sdiv=unsafe{SDIV};
        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747{
            index:unsafe{RANDOM_PHASE_COUNT_V747},
            advance:rng_advance(),pre_state:reader.rng_state(),pre_ap4,pre_sp4,
            normal_adiv,normal_sdiv,a_pc:pc,s_pc:0,a_rdiv:reader.div(),s_rdiv:0,
            ap4:phase,sp4:0,a_tick:host_tick,s_tick:0,a_mcycle:mcycle,s_mcycle:0,
            adiv_index:add_div_tracker().index().unwrap_or(0) as u16,
            sdiv_index:sub_div_tracker().index().unwrap_or(0) as u16,
        };
        unsafe{RANDOM_PHASE_PENDING_V747=true;}
    }else if pc==0x2f68{
        unsafe{
            if !RANDOM_PHASE_PENDING_V747{return;}
            let mut e=RANDOM_PHASE_WORK_V747;
            e.s_pc=pc;e.s_rdiv=reader.div();e.sp4=phase;e.s_tick=host_tick;e.s_mcycle=mcycle;
            RANDOM_PHASE_LOG_V747[RANDOM_PHASE_WRITE_V747]=e;
            RANDOM_PHASE_WRITE_V747=(RANDOM_PHASE_WRITE_V747+1)%RANDOM_PHASE_LOG_LEN_V747;
            RANDOM_PHASE_COUNT_V747=RANDOM_PHASE_COUNT_V747.wrapping_add(1);
            RANDOM_PHASE_PENDING_V747=false;
        }
    }
}

'''
    h=h[:pos]+block+h[pos:]

# Reset paired log whenever the existing deep log starts or is cleared.
if 'RANDOM_PHASE_COUNT_V747=0;' not in h[h.find('pub fn deep_log_start()'):h.find('pub fn deep_log_stop()')]:
    old='''        DEEP_WRITE = 0;\n        DEEP_COUNT = 0;\n        DEEP_LOGGING = true;'''
    new='''        DEEP_WRITE = 0;\n        DEEP_COUNT = 0;\n        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;\n        RANDOM_PHASE_PENDING_V747=false;\n        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;\n        DEEP_LOGGING = true;'''
    h=rep(h,old,new,'deep start random-phase reset')
if 'RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;' not in h[h.find('pub fn deep_log_clear()'):h.find('pub fn deep_log_count()')]:
    old='''        DEEP_WRITE = 0;\n        DEEP_COUNT = 0;\n        DEEP_LOGGING = false;'''
    new='''        DEEP_WRITE = 0;\n        DEEP_COUNT = 0;\n        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;\n        RANDOM_PHASE_PENDING_V747=false;\n        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;\n        DEEP_LOGGING = false;'''
    h=rep(h,old,new,'deep clear random-phase reset')

# Hook all rDIV reads once; capture function itself filters 2F60/2F68.
if 'capture_random_phase_v747(&reader, pc, host_tick, mcycle);' not in h:
    anchor='    capture_deep_random(&reader, regs, _stack_pointer, pc, host_tick, mcycle);'
    need(anchor in h,'capture_deep_random call anchor missing')
    h=h.replace(anchor,'    capture_random_phase_v747(&reader, pc, host_tick, mcycle);\n'+anchor,1)

# ---------------------------------------------------------------------------
# C. Frame-side mark: exactly one raw host tick per run_frame.
# ---------------------------------------------------------------------------
if 'mark_host_frame_v747' not in f:
    old='    hook::{measured_div, reset_rng_advance},'
    new='    hook::{mark_host_frame_v747, measured_div, reset_rng_advance},'
    f=rep(f,old,new,'frame hook import')
if '    mark_host_frame_v747();' not in f:
    sig='pub fn run_frame() {'
    p=f.find(sig); need(p>=0,'run_frame missing')
    br=f.find('{',p)
    f=f[:br+1]+'\n    mark_host_frame_v747();'+f[br+1:]

# ---------------------------------------------------------------------------
# D. TraceEntry stores raw hook frame/tick but legacy frame CSV is NOT changed.
# Values are emitted only in the appended FRAME2 section.
# ---------------------------------------------------------------------------
# import hook helpers
if 'random_phase_count_v747' not in t.split('};',1)[0]:
    old='    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, measured_div, rng_advance,'
    new='    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, host_frame_metrics_v747, measured_div, random_phase_count_v747, random_phase_entry_v747, rng_advance,'
    t=rep(t,old,new,'trace hook imports')

if 'pub hook_frame_index_v747: u32,' not in t:
    old='''    pub atick: u64,\n    pub stick: u64,\n}'''
    new='''    pub atick: u64,\n    pub stick: u64,\n    pub hook_frame_index_v747: u32,\n    pub hook_tick_v747: u64,\n    pub ticks_since_last_hook_v747: u64,\n}'''
    t=rep(t,old,new,'TraceEntry fields')
if 'hook_frame_index_v747: 0,' not in t:
    old='''        atick: 0,\n        stick: 0,\n    };'''
    new='''        atick: 0,\n        stick: 0,\n        hook_frame_index_v747: 0,\n        hook_tick_v747: 0,\n        ticks_since_last_hook_v747: 0,\n    };'''
    t=rep(t,old,new,'TraceEntry empty fields')

# Only patch the per-frame TraceEntry initializer, not ProbeTarget.
if 'let (hook_frame_index_v747,hook_tick_v747,ticks_since_last_hook_v747)=host_frame_metrics_v747();' not in t:
    anchor='        self.entries[self.len] = TraceEntry {'
    need(anchor in t,'TraceEntry record initializer missing')
    t=t.replace(anchor,'        let (hook_frame_index_v747,hook_tick_v747,ticks_since_last_hook_v747)=host_frame_metrics_v747();\n'+anchor,1)
    start=t.find(anchor)
    end=t.find('        };',start)
    need(end>start,'TraceEntry initializer end missing')
    block=t[start:end]
    needle='            stick: sdiv_tick(),\n'
    need(needle in block,'TraceEntry stick initializer missing')
    block=block.replace(needle,needle+'''            hook_frame_index_v747,\n            hook_tick_v747,\n            ticks_since_last_hook_v747,\n''',1)
    t=t[:start]+block+t[end:]

# ---------------------------------------------------------------------------
# E. C-side root-lock telemetry getters. No control behavior changes.
# ---------------------------------------------------------------------------
if 'u32 host_suicune_root_lock_steps(void)' not in m:
    mm=re.search(r'(#define\s+SUICUNE_ROOT_LOCK_MAX_STEPS\s+\d+U\s*)',m)
    need(mm is not None,'root-lock max define missing')
    add=r'''

u32 host_suicune_root_lock_steps(void)
{
    return suicune_root_lock_steps;
}

u32 host_suicune_root_lock_state(void)
{
    return ((u32)suicune_root_lock_active)
        | ((u32)suicune_root_lock_ready << 1)
        | ((u32)suicune_root_lock_failed << 2)
        | ((u32)suicune_wait_up_after_b << 3);
}
'''
    m=m[:mm.end()]+add+m[mm.end():]

if 'pub fn host_suicune_root_lock_steps() -> u32;' not in b:
    anchor='    pub fn host_fixed_run_id() -> u32;\n'
    need(anchor in b,'bindings fixed run declaration missing')
    b=b.replace(anchor,anchor+'    pub fn host_suicune_root_lock_steps() -> u32;\n    pub fn host_suicune_root_lock_state() -> u32;\n',1)
if 'pub extern "C" fn host_suicune_root_lock_steps()' not in b:
    anchor='''    pub extern "C" fn host_fixed_run_id() -> u32 {\n        0\n    }\n'''
    need(anchor in b,'bindings fixed run stub missing')
    b=b.replace(anchor,anchor+'''    #[no_mangle]\n    pub extern "C" fn host_suicune_root_lock_steps() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_root_lock_state() -> u32 { 0 }\n''',1)
if 'pub fn suicune_root_lock_steps_v747()' not in ph:
    ph += r'''

pub fn suicune_root_lock_steps_v747()->u32{
    unsafe{bindings::host_suicune_root_lock_steps()}
}
pub fn suicune_root_lock_state_v747()->u32{
    unsafe{bindings::host_suicune_root_lock_state()}
}
'''

# ---------------------------------------------------------------------------
# F. Append-only CSV schema V2. No existing header or section is edited.
# ---------------------------------------------------------------------------
if 'SCHEMA,SUICUNE_TRACE,V2' not in t:
    close='        pnp::trace_file_close();'
    need(t.count(close)==1,f'trace_file_close count {t.count(close)}')
    sec=r'''        // v7.4.7 append-only telemetry schema. Legacy frame/call/deep/
        // PREFP/POSTFP sections above remain byte-compatible with 0124-0140 parsers.
        line.clear();
        let _=write!(line,"\nschema,name,version,compat\nSCHEMA,SUICUNE_TRACE,V2,LEGACY_APPEND_ONLY\n");
        pnp::trace_file_write(line.as_bytes());

        let rp_count=random_phase_count_v747() as usize;
        line.clear();
        let _=write!(line,"deep_phase_index,version,advance,pre_state,pre_ap4,pre_sp4,normal_adiv,normal_sdiv,a_pc,s_pc,a_rdiv,s_rdiv,ap4,sp4,a_tick,s_tick,a_mcycle,s_mcycle,adiv_index,sdiv_index\n");
        pnp::trace_file_write(line.as_bytes());
        for i in 0..rp_count.min(super::hook::RANDOM_PHASE_LOG_LEN_V747){
            let e=random_phase_entry_v747(i);
            line.clear();
            let _=write!(line,"DEEP2,V747,{},{:04X},{},{},{},{},{:04X},{:04X},{},{},{},{},{},{},{},{},{},{}\n",
                e.advance,e.pre_state,e.pre_ap4,e.pre_sp4,e.normal_adiv,e.normal_sdiv,
                e.a_pc,e.s_pc,e.a_rdiv,e.s_rdiv,e.ap4,e.sp4,e.a_tick,e.s_tick,
                e.a_mcycle,e.s_mcycle,e.adiv_index,e.sdiv_index);
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _=write!(line,"predeep,version,advance,state,ap4,sp4,a_div,s_div,adiv_index,sdiv_index\n");
        pnp::trace_file_write(line.as_bytes());
        if rp_count>0{
            let e=random_phase_entry_v747(0);
            line.clear();
            let _=write!(line,"PREDEEP2,V747,{},{:04X},{},{},{},{},{},{}\n",
                e.advance,e.pre_state,e.pre_ap4,e.pre_sp4,e.normal_adiv,e.normal_sdiv,e.adiv_index,e.sdiv_index);
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _=write!(line,"frame2,version,index,advance,hook_frame_index,hook_frame_mod16,hook_tick,ticks_since_last_hook,phase_a,phase_s\n");
        pnp::trace_file_write(line.as_bytes());
        for i in 0..self.len{
            let e=&self.entries[i];
            line.clear();
            let _=write!(line,"FRAME2,V747,{},{},{},{},{},{},{},{}\n",i,e.advance,
                e.hook_frame_index_v747,e.hook_frame_index_v747&15,e.hook_tick_v747,
                e.ticks_since_last_hook_v747,e.adiv&15,e.sdiv&15);
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _=write!(line,"control2,version,scan_lane,scan_checked,root_lock_steps,root_lock_state\nCONTROL2,V747,{},{},{},{}\n",
            self.practical_live_found_lane,self.practical_live_checked,
            pnp::suicune_root_lock_steps_v747(),pnp::suicune_root_lock_state_v747());
        pnp::trace_file_write(line.as_bytes());

'''
    t=t.replace(close,sec+close,1)

# Safety checks.
for marker in ['POSTFP','NPJT,V746','deep_index,pc','BRPHASE','FRAME2,V747','DEEP2,V747']:
    need(marker in t,f'expected compatibility marker missing: {marker}')

H.write_text(h);T.write_text(t);F.write_text(f);M.write_text(m);B.write_text(b);PH.write_text(ph)
print('Applied Suicune v7.4.7 Telemetry V2: paired deep 2F60/2F68 phases, predeep direct capture, drift-free frame tick/index, append-only CSV')
