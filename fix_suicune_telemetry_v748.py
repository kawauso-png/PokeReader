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

# Lightweight 2F60/2F68 telemetry must survive the existing DV-2 deep_log_stop().
# Heavy DeepEntry snapshots still stop at DV-2 exactly as before.
if 'RANDOM_PHASE_LOGGING_V748' not in h:
    anchor='static mut RANDOM_PHASE_PENDING_V747:bool=false;'
    need(anchor in h,'random phase pending anchor missing')
    h=h.replace(anchor,anchor+'\nstatic mut RANDOM_PHASE_LOGGING_V748:bool=false;',1)

# Independent gate: do not reuse DEEP_LOGGING, because endpoint v4.4 deliberately
# disables the heavy deep probe before the final event Random burst.
h=rep(h,
      '    unsafe{if !DEEP_LOGGING{return;}}\n    let phase=',
      '    unsafe{if !RANDOM_PHASE_LOGGING_V748{return;}}\n    let phase=',
      'random phase gate')

# Start/clear the lightweight logger with each Suicune probe.
start_old='''        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;\n        DEEP_LOGGING = true;'''
start_new='''        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;\n        RANDOM_PHASE_LOGGING_V748=true;\n        DEEP_LOGGING = true;'''
h=rep(h,start_old,start_new,'random phase start flag')

clear_old='''        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;\n        DEEP_LOGGING = false;'''
clear_new='''        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747::EMPTY;\n        RANDOM_PHASE_LOGGING_V748=false;\n        DEEP_LOGGING = false;'''
h=rep(h,clear_old,clear_new,'random phase clear flag')

if 'pub fn random_phase_stop_v748()' not in h:
    anchor='pub fn random_phase_count_v747()->u32'
    need(anchor in h,'random phase count anchor missing')
    h=h.replace(anchor,'pub fn random_phase_stop_v748(){unsafe{RANDOM_PHASE_LOGGING_V748=false;RANDOM_PHASE_PENDING_V747=false;}}\n'+anchor,1)

# Stop lightweight telemetry only after DV/result is visible, immediately before save.
if 'random_phase_stop_v748' not in t.split('};',1)[0]:
    old='deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, host_frame_metrics_v747, measured_div, random_phase_count_v747, random_phase_entry_v747, rng_advance,'
    new='deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, host_frame_metrics_v747, measured_div, random_phase_count_v747, random_phase_entry_v747, random_phase_stop_v748, rng_advance,'
    t=rep(t,old,new,'trace import')

anchor='''                self.probe_result = Some(result);\n                self.probe_active = false;\n                self.practical_terminal_advance = rng_advance();\n                call_log_stop();\n                deep_log_stop();'''
if '                random_phase_stop_v748();\n                call_log_stop();' not in t:
    repl='''                self.probe_result = Some(result);\n                self.probe_active = false;\n                self.practical_terminal_advance = rng_advance();\n                random_phase_stop_v748();\n                call_log_stop();\n                deep_log_stop();'''
    t=rep(t,anchor,repl,'final result stop')

# FRAME2 phase_a/phase_s must be the direct F604 subticks, not DIV low nibbles.
t=rep(t,
      'e.ticks_since_last_hook_v747,e.adiv&15,e.sdiv&15);',
      'e.ticks_since_last_hook_v747,e.asub,e.ssub);',
      'FRAME2 phase source')

# Distinguish fixed rows without changing legacy sections.
t=t.replace('DEEP2,V747,','DEEP2,V748,')
t=t.replace('PREDEEP2,V747,','PREDEEP2,V748,')
t=t.replace('FRAME2,V747,','FRAME2,V748,')
t=t.replace('CONTROL2,V747,','CONTROL2,V748,')

H.write_text(h); T.write_text(t)
print('Applied v7.4.8 telemetry fix: final Random survives DV-2 heavy-probe stop; FRAME2 uses F604 subticks')
