#!/usr/bin/env python3
from pathlib import Path

M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
m=M.read_text(); t=T.read_text()

def rep(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'v741 {label}: expected 1, got {n}')
    return s.replace(a,b,1)

# -------------------------------------------------------------------------
# v7.4.1: remove the old relative START selector entirely.
# Y+DOWN is already used by the slot-sweep target selector, so allowing it to
# also toggle start-phase creates a hidden mode difference between B76/B39.
# START is now fixed to absolute host cycle mod16 == 0 for every trial.
# -------------------------------------------------------------------------
old='''            // v5.0 START phase selector: left/right = +/-1, down = opposite half-cycle.\n            // Resume remains P00 so only one causal variable is changed.\n            suicune_phase_slot = 0;\n            if (just_pressed & KEY_DRIGHT)\n                suicune_start_phase_slot = (suicune_start_phase_slot + 1) & 0x0f;\n            if (just_pressed & KEY_DLEFT)\n                suicune_start_phase_slot = (suicune_start_phase_slot + 15) & 0x0f;\n            if (just_pressed & KEY_DDOWN)\n                suicune_start_phase_slot ^= 8;'''
new='''            // v7.4.1: absolute START M0 is fixed for the entire sweep.\n            // Do not let Y+DOWN/Y+UP target selection mutate START phase.\n            suicune_start_phase_slot = 0;'''
m=rep(m,old,new,'remove relative start selector')

old='''                    suicune_start_phase_lock_active = true;\n                    suicune_start_phase_anchor_tick = suicune_start_last_top_tick;\n                    suicune_start_phase_target_tick = 0;\n                    suicune_start_phase_actual_tick = 0;'''
new='''                    suicune_start_phase_slot = 0;\n                    suicune_start_phase_lock_active = true;\n                    suicune_start_phase_anchor_tick = 0;\n                    suicune_start_phase_target_tick = 0;\n                    suicune_start_phase_actual_tick = 0;'''
m=rep(m,old,new,'arm absolute start')

old='''                if (suicune_auto_resume_pending && suicune_start_phase_lock_active && suicune_start_phase_anchor_tick != 0)\n                {\n                    u64 now = suicune_obs_fixed_release_tick;\n                    u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_start_phase_slot) / SUICUNE_PHASE_SLOTS;\n                    u64 target = suicune_start_phase_anchor_tick + offset;\n                    if (target <= now + 4096ULL)\n                    {\n                        u64 delta = (now + 4096ULL) - target;\n                        target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;\n                    }\n                    suicune_start_phase_target_tick = target;\n                    while (svcGetSystemTick() < target) { }\n                    suicune_start_phase_actual_tick = svcGetSystemTick();\n                }'''
new='''                if (suicune_auto_resume_pending && suicune_start_phase_lock_active)\n                {\n                    u64 now = suicune_obs_fixed_release_tick;\n                    const u32 wanted_start_cycle = 0U;\n                    u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;\n                    while (((u32)cycle & 15U) != wanted_start_cycle) cycle++;\n                    u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                    if (target <= now + 4096ULL)\n                    {\n                        cycle += 16ULL;\n                        target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                    }\n                    suicune_start_phase_slot = wanted_start_cycle;\n                    suicune_start_phase_anchor_tick = target;\n                    suicune_start_phase_target_tick = target;\n                    while (svcGetSystemTick() < target) { }\n                    suicune_start_phase_actual_tick = svcGetSystemTick();\n                }'''
m=rep(m,old,new,'absolute start wait')

# UI versioning and explicit absolute START status.
t=t.replace('S740 B{} TURBO','S741 B{} TURBO')
t=t.replace('S740 B{} SWEEP FOUND','S741 B{} SWEEP FOUND')
t=t.replace('S740 NEED A EPOCH','S741 NEED A EPOCH')
old='''            pnp::println!("A/r10 TARGET; WAIT 0.5s");\n            pnp::println!("SLOT0 BASE  X=+1");'''
new='''            pnp::println!("A/r10 TARGET; ABS START M0");\n            pnp::println!("SLOT0 BASE  X=+1");'''
t=rep(t,old,new,'sweep found UI')

# Replace the v740 sweep row with explicit absolute START diagnostics.
old='''        line.clear();\n        let actual_raw=self.probe_result.map(|x|x.raw_dv).unwrap_or(0);\n        let actual_route=self.probe_result.map(|x|x.route).unwrap_or(0);\n        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_slot,actual_slot,post_proto,post_rot,post_score,raw_dv,route,freeze_delta\\nSWEEP,V740,{},{},{},{},{},{},{},{:04X},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&7,\n            if rpm.period!=0{((rpm.actual/rpm.period)&7)as u32}else{255},\n            actual_post_proto as char,actual_post_rot,actual_post_score,\n            actual_raw,actual_route,self.sweep_freeze_delta);\n        pnp::trace_file_write(line.as_bytes());'''
new='''        line.clear();\n        let actual_raw=self.probe_result.map(|x|x.raw_dv).unwrap_or(0);\n        let actual_route=self.probe_result.map(|x|x.route).unwrap_or(0);\n        let sweep_spm=pnp::start_phase_metrics();\n        let start_cycle_mod16=if sweep_spm.period!=0{((sweep_spm.actual/sweep_spm.period)&15)as u32}else{255};\n        let start_remainder=if sweep_spm.period!=0{sweep_spm.actual%sweep_spm.period}else{0};\n        let start_error=sweep_spm.actual as i128-sweep_spm.target as i128;\n        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_slot,actual_slot,post_proto,post_rot,post_score,raw_dv,route,freeze_delta,start_cycle_mod16,start_remainder,start_error_ticks\\nSWEEP,V741,{},{},{},{},{},{},{},{:04X},{},{},{},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&7,\n            if rpm.period!=0{((rpm.actual/rpm.period)&7)as u32}else{255},\n            actual_post_proto as char,actual_post_rot,actual_post_score,\n            actual_raw,actual_route,self.sweep_freeze_delta,start_cycle_mod16,start_remainder,start_error);\n        pnp::trace_file_write(line.as_bytes());'''
t=rep(t,old,new,'v741 sweep csv')

M.write_text(m); T.write_text(t)
print('Applied v7.4.1 Absolute START Sweep: fixed cycle mod16=0, no Y+DOWN phase collision, SLOT0..7 resume sweep retained')
