#!/usr/bin/env python3
from pathlib import Path

H=Path('reader_core/src/crystal/hook.rs')
T=Path('reader_core/src/crystal/trace.rs')
h=H.read_text(); t=T.read_text()

def need(c,msg):
    if not c: raise SystemExit('v748 '+msg)
def rep(s,old,new,msg):
    n=s.count(old)
    if n!=1: raise SystemExit(f'v748 {msg}: expected 1 got {n}')
    return s.replace(old,new,1)

# ---------------------------------------------------------------------------
# 1. Lightweight 2F60/2F68 telemetry must survive the endpoint's intentional
#    DV-2 stop of the expensive DeepEntry snapshotter.
# ---------------------------------------------------------------------------
if 'RANDOM_PHASE_LOGGING_V748' not in h:
    anchor='static mut RANDOM_PHASE_PENDING_V747:bool=false;'
    need(anchor in h,'random phase pending anchor missing')
    h=h.replace(anchor,anchor+'\nstatic mut RANDOM_PHASE_LOGGING_V748:bool=false;',1)

rep_old='    unsafe{if !DEEP_LOGGING{return;}}\n    let phase='
rep_new='    unsafe{if !RANDOM_PHASE_LOGGING_V748{return;}}\n    let phase='
h=rep(h,rep_old,rep_new,'random phase gate')

start_old='''        RANDOM_PHASE_PENDING_V747=false;
        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;
        DEEP_LOGGING = true;'''
start_new='''        RANDOM_PHASE_PENDING_V747=false;
        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;
        RANDOM_PHASE_LOGGING_V748=true;
        DEEP_LOGGING = true;'''
h=rep(h,start_old,start_new,'random phase start flag')

clear_old='''        RANDOM_PHASE_PENDING_V747=false;
        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;
        DEEP_LOGGING = false;'''
clear_new='''        RANDOM_PHASE_PENDING_V747=false;
        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;
        RANDOM_PHASE_LOGGING_V748=false;
        DEEP_LOGGING = false;'''
h=rep(h,clear_old,clear_new,'random phase clear flag')

if 'pub fn random_phase_stop_v748()' not in h:
    anchor='pub fn random_phase_count_v747()->u32'
    need(anchor in h,'random phase count anchor missing')
    h=h.replace(anchor,
        'pub fn random_phase_stop_v748(){unsafe{RANDOM_PHASE_LOGGING_V748=false;RANDOM_PHASE_PENDING_V747=false;}}\n'+anchor,1)

# ---------------------------------------------------------------------------
# 2. Live top-hook F604 value.  The old asub/ssub are samples at rDIV reads and
#    can be stale throughout the 13-hook plateau; this samples F604 at each
#    run_frame boundary and at the physical UP trigger.
# ---------------------------------------------------------------------------
if 'HOST_FRAME_MCYCLE_V748' not in h:
    anchor='static mut HOST_FRAME_DELTA_V747: u64 = 0;'
    need(anchor in h,'host frame delta anchor missing')
    h=h.replace(anchor,anchor+'\nstatic mut HOST_FRAME_MCYCLE_V748: u8 = 0;',1)

old='''pub fn mark_host_frame_v747() {
    let now=pnp::system_tick();
    unsafe {
        HOST_FRAME_DELTA_V747=if HOST_FRAME_TICK_V747==0{0}else{now.wrapping_sub(HOST_FRAME_TICK_V747)};
        HOST_FRAME_TICK_V747=now;
        HOST_FRAME_INDEX_V747=HOST_FRAME_INDEX_V747.wrapping_add(1);
    }
}'''
new='''pub fn mark_host_frame_v747() {
    let now=pnp::system_tick();
    let live_mcycle=pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
    unsafe {
        HOST_FRAME_DELTA_V747=if HOST_FRAME_TICK_V747==0{0}else{now.wrapping_sub(HOST_FRAME_TICK_V747)};
        HOST_FRAME_TICK_V747=now;
        HOST_FRAME_MCYCLE_V748=live_mcycle;
        HOST_FRAME_INDEX_V747=HOST_FRAME_INDEX_V747.wrapping_add(1);
    }
}'''
h=rep(h,old,new,'host frame live mcycle')

if 'pub fn host_frame_live_mcycle_v748()' not in h:
    anchor='pub fn host_frame_metrics_v747()->(u32,u64,u64){\n    unsafe{(HOST_FRAME_INDEX_V747,HOST_FRAME_TICK_V747,HOST_FRAME_DELTA_V747)}\n}\n'
    need(anchor in h,'host metrics anchor missing')
    h=h.replace(anchor,anchor+'pub fn host_frame_live_mcycle_v748()->u8{unsafe{HOST_FRAME_MCYCLE_V748}}\n',1)

# ---------------------------------------------------------------------------
# 3. Robust trace import patch. v747 generated import is split across lines.
# ---------------------------------------------------------------------------
if 'random_phase_stop_v748' not in t.split('};',1)[0]:
    anchor='    host_frame_metrics_v747, random_phase_count_v747, random_phase_entry_v747,\n'
    need(anchor in t,'trace import anchor missing')
    t=t.replace(anchor,
        '    host_frame_live_mcycle_v748, host_frame_metrics_v747, random_phase_count_v747, random_phase_entry_v747, random_phase_stop_v748,\n',1)

# TraceEntry carries the live top-hook sample.
if 'pub hook_live_mcycle_v748: u8,' not in t:
    anchor='    pub ticks_since_last_hook_v747: u64,\n'
    need(anchor in t,'TraceEntry hook delta field missing')
    t=t.replace(anchor,anchor+'    pub hook_live_mcycle_v748: u8,\n',1)
    anchor='        ticks_since_last_hook_v747: 0,\n'
    need(anchor in t,'TraceEntry empty hook delta missing')
    t=t.replace(anchor,anchor+'        hook_live_mcycle_v748: 0,\n',1)

if 'let hook_live_mcycle_v748=host_frame_live_mcycle_v748();' not in t:
    anchor='        let (hook_frame_index_v747,hook_tick_v747,ticks_since_last_hook_v747)=host_frame_metrics_v747();\n'
    need(anchor in t,'TraceEntry metrics record anchor missing')
    t=t.replace(anchor,anchor+'        let hook_live_mcycle_v748=host_frame_live_mcycle_v748();\n',1)
    anchor='            ticks_since_last_hook_v747,\n'
    need(anchor in t,'TraceEntry initializer hook delta missing')
    t=t.replace(anchor,anchor+'            hook_live_mcycle_v748,\n',1)

# ---------------------------------------------------------------------------
# 4. Physical UP trigger phase snapshot (NPJT2), without changing legacy NPJT.
# ---------------------------------------------------------------------------
if 'nptest_trigger_hook_index_v748: u32,' not in t:
    anchor='    nptest_trigger_div: u16,\n'
    need(anchor in t,'nptest field anchor missing')
    t=t.replace(anchor,anchor+'''    nptest_trigger_hook_index_v748: u32,
    nptest_trigger_hook_tick_v748: u64,
    nptest_trigger_live_mcycle_v748: u8,
''',1)
    anchor='            nptest_trigger_div: 0,\n'
    need(anchor in t,'nptest default anchor missing')
    t=t.replace(anchor,anchor+'''            nptest_trigger_hook_index_v748: 0,
            nptest_trigger_hook_tick_v748: 0,
            nptest_trigger_live_mcycle_v748: 0,
''',1)
    anchor='        self.nptest_trigger_div=0;\n'
    need(anchor in t,'nptest reset anchor missing')
    t=t.replace(anchor,anchor+'''        self.nptest_trigger_hook_index_v748=0;
        self.nptest_trigger_hook_tick_v748=0;
        self.nptest_trigger_live_mcycle_v748=0;
''',1)

trigger_old='''                    self.nptest_trigger_advance = rng_advance();
                    self.nptest_trigger_state = reader.rng_state();
                    self.nptest_trigger_div = measured_div();'''
trigger_new='''                    self.nptest_trigger_advance = rng_advance();
                    self.nptest_trigger_state = reader.rng_state();
                    self.nptest_trigger_div = measured_div();
                    let (fi,ft,_)=host_frame_metrics_v747();
                    self.nptest_trigger_hook_index_v748=fi;
                    self.nptest_trigger_hook_tick_v748=ft;
                    self.nptest_trigger_live_mcycle_v748=host_frame_live_mcycle_v748();'''
if 'self.nptest_trigger_hook_index_v748=fi;' not in t:
    t=rep(t,trigger_old,trigger_new,'nptest trigger phase')

# ---------------------------------------------------------------------------
# 5. Stop lightweight telemetry only after actual DV/result is visible.
# ---------------------------------------------------------------------------
result_old='''                self.probe_result = Some(result);
                self.probe_active = false;
                self.practical_terminal_advance = rng_advance();
                call_log_stop();
                deep_log_stop();'''
result_new='''                self.probe_result = Some(result);
                self.probe_active = false;
                self.practical_terminal_advance = rng_advance();
                random_phase_stop_v748();
                call_log_stop();
                deep_log_stop();'''
if '                random_phase_stop_v748();\n                call_log_stop();' not in t:
    t=rep(t,result_old,result_new,'final result stop')

# ---------------------------------------------------------------------------
# 6. CSV fixes/additions. Legacy sections stay untouched.
# ---------------------------------------------------------------------------
# phase_a/phase_s are actual F604 rDIV subticks, not DIV low nibbles; also append
# live_mcycle to FRAME2.
header_old='frame2,version,index,advance,hook_frame_index,hook_frame_mod16,hook_tick,ticks_since_last_hook,phase_a,phase_s\\n'
header_new='frame2,version,index,advance,hook_frame_index,hook_frame_mod16,hook_tick,ticks_since_last_hook,phase_a,phase_s,live_mcycle\\n'
t=rep(t,header_old,header_new,'FRAME2 header')
row_old='''let _=write!(line,"FRAME2,V747,{},{},{},{},{},{},{},{}\\n",i,e.advance,
                e.hook_frame_index_v747,e.hook_frame_index_v747&15,e.hook_tick_v747,
                e.ticks_since_last_hook_v747,e.adiv&15,e.sdiv&15);'''
row_new='''let _=write!(line,"FRAME2,V748,{},{},{},{},{},{},{},{},{}\\n",i,e.advance,
                e.hook_frame_index_v747,e.hook_frame_index_v747&15,e.hook_tick_v747,
                e.ticks_since_last_hook_v747,e.asub,e.ssub,e.hook_live_mcycle_v748);'''
t=rep(t,row_old,row_new,'FRAME2 row')

# New trigger row is append-only and does not alter legacy NPJT.
if 'NPJT2,V748' not in t:
    anchor='''        pnp::trace_file_write(line.as_bytes());

        // v7.4.7 append-only telemetry schema.'''
    need(anchor in t,'NPJT append anchor missing')
    add='''        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _=write!(line,"npjt2,version,trigger_hook_index,trigger_hook_mod16,trigger_hook_tick,trigger_live_mcycle\\nNPJT2,V748,{},{},{},{}\\n",
            self.nptest_trigger_hook_index_v748,self.nptest_trigger_hook_index_v748&15,
            self.nptest_trigger_hook_tick_v748,self.nptest_trigger_live_mcycle_v748);
        pnp::trace_file_write(line.as_bytes());

        // v7.4.7 append-only telemetry schema.'''
    t=t.replace(anchor,add,1)

# Version fixed new telemetry rows.
t=t.replace('DEEP2,V747,','DEEP2,V748,')
t=t.replace('PREDEEP2,V747,','PREDEEP2,V748,')
t=t.replace('CONTROL2,V747,','CONTROL2,V748,')

H.write_text(h); T.write_text(t)
print('Applied v7.4.8 telemetry fix: final Random deep phase + live top-hook F604 + NPJT2 trigger phase')
