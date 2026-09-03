#!/usr/bin/env python3
from pathlib import Path

M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
m=M.read_text(); t=T.read_text()

def rep(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'v742 {label}: expected 1, got {n}')
    return s.replace(a,b,1)

# -------------------------------------------------------------------------
# v7.4.2: keep v7.4.1 absolute START M0, but expose the full absolute
# resume cycle mod16.  v7.3.x/v7.4.0 only controlled cycle mod8, leaving the
# high bit uncontrolled (M1 vs M9, M6 vs M14, ...).
# -------------------------------------------------------------------------
old='''        // v7.4.0 slot-sweep selector. X is consumed inside the pause loop;\n        // no VC frame is released. Cycle absolute SLOT0..7 while frozen.\n        if ((just_pressed & KEY_X) && !(held & KEY_Y)\n            && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            suicune_phase_slot = (suicune_phase_slot + 1U) & 7U;\n            continue;\n        }'''
new='''        // v7.4.2 full absolute resume selector.  Only active after the\n        // authoritative frozen A/r10 bucket root is READY, so Y+DOWN/Y+UP\n        // scan commands cannot collide with this control.  X=+1, Y=-1.\n        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            if (just_pressed & KEY_X)\n            {\n                suicune_phase_slot = (suicune_phase_slot + 1U) & 15U;\n                continue;\n            }\n            if (just_pressed & KEY_Y)\n            {\n                suicune_phase_slot = (suicune_phase_slot + 15U) & 15U;\n                continue;\n            }\n        }'''
m=rep(m,old,new,'full16 selector')

old='''                    u32 wanted = suicune_phase_slot & 7U;\n                    // Pick the next absolute host-period boundary whose cycle\n                    // number has the requested low 3 bits.  resume_command_tick\n                    // follows only a few hundred ticks later, far inside the same\n                    // 4.48M-tick cycle, so it inherits this absolute slot.\n                    u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;\n                    while (((u32)cycle & 7U) != wanted) cycle++;\n                    u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                    if (target <= now + 4096ULL)\n                    {\n                        cycle += 8ULL;\n                        target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                    }'''
new='''                    u32 wanted = suicune_phase_slot & 15U;\n                    // v7.4.2 controls the complete absolute cycle mod16, not\n                    // only its low three bits.  This separates M1/M9, M6/M14,\n                    // etc., which v7.4.1 telemetry showed can lead to different\n                    // POST branches.\n                    u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;\n                    while (((u32)cycle & 15U) != wanted) cycle++;\n                    u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                    if (target <= now + 4096ULL)\n                    {\n                        cycle += 16ULL;\n                        target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                    }'''
m=rep(m,old,new,'absolute resume mod16 wait')

# Keep START fixed to M0; only version/status text and resume selector change.
t=t.replace('S741 B{} TURBO','S742 B{} TURBO')
t=t.replace('S741 B{} SWEEP FOUND','S742 B{} SWEEP FOUND')
t=t.replace('S741 NEED A EPOCH','S742 NEED A EPOCH')
old='''            pnp::println!("A/r10 TARGET; ABS START M0");\n            pnp::println!("SLOT0 BASE  X=+1");\n            pnp::println!("THEN B -> RELEASE -> UP");'''
new='''            pnp::println!("A/r10 TARGET; ABS START M0");\n            pnp::println!("RESUME M{:02} X+1 Y-1",pnp::fixed_a_frame().phase_slot & 15);\n            pnp::println!("THEN B -> RELEASE -> UP");'''
t=rep(t,old,new,'dynamic resume UI')

# v7.4.1 row used low3 resume slot.  Record the full wanted/actual mod16 and
# the actual boundary remainder/error so every trial proves the actuator hit.
old='''        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_slot,actual_slot,post_proto,post_rot,post_score,raw_dv,route,freeze_delta,start_cycle_mod16,start_remainder,start_error_ticks\\nSWEEP,V741,{},{},{},{},{},{},{},{:04X},{},{},{},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&7,\n            if rpm.period!=0{((rpm.actual/rpm.period)&7)as u32}else{255},\n            if sweep_post.valid{sweep_post.proto as char}else{'?'},sweep_post.rot40,sweep_post.best_score,\n            actual_raw,actual_route,self.sweep_freeze_delta,start_cycle_mod16,start_remainder,start_error);'''
new='''        let resume_cycle_mod16=if rpm.period!=0{((rpm.actual/rpm.period)&15)as u32}else{255};\n        let resume_remainder=if rpm.period!=0{rpm.actual%rpm.period}else{0};\n        let resume_error=rpm.actual as i128-rpm.target as i128;\n        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_resume_mod16,actual_resume_mod16,post_proto,post_rot,post_score,raw_dv,route,freeze_delta,start_cycle_mod16,start_remainder,start_error_ticks,resume_remainder,resume_error_ticks\\nSWEEP,V742,{},{},{},{},{},{},{},{:04X},{},{},{},{},{},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&15,resume_cycle_mod16,\n            if sweep_post.valid{sweep_post.proto as char}else{'?'},sweep_post.rot40,sweep_post.best_score,\n            actual_raw,actual_route,self.sweep_freeze_delta,start_cycle_mod16,start_remainder,start_error,\n            resume_remainder,resume_error);'''
t=rep(t,old,new,'v742 sweep csv')

M.write_text(m); T.write_text(t)
print('Applied v7.4.2 Full16 Resume Probe: absolute START M0 retained; absolute Resume M0..M15 selectable')
