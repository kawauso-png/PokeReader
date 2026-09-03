#!/usr/bin/env python3
from pathlib import Path

M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
m=M.read_text(); t=T.read_text()

def need(x,msg):
    if not x: raise SystemExit('v742 '+msg)

# -------------------------------------------------------------------------
# v7.4.2: keep v7.4.1 absolute START M0, but expose the full absolute
# Resume cycle mod16.  v7.3.x/v7.4.1 only controlled mod8, leaving the high
# bit uncontrolled (M1 vs M9, M6 vs M14, ...).
# -------------------------------------------------------------------------

# Replace the whole v7.4.0 selector region semantically.  Earlier patches can
# alter whitespace/conditions around the X selector, so do not depend on the
# exact generated text.
a=m.find('        // v7.4.0 slot-sweep selector.')
b=m.find('        // v7.2.4 robust diagnostic arm.',a)
need(a>=0 and b>a,'selector markers missing')
selector='''        // v7.4.2 full absolute resume selector.  Only active after the
        // authoritative frozen A/r10 bucket root is READY, so Y+DOWN/Y+UP
        // scan commands cannot collide with this control.  X=+1, Y=-1.
        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)
        {
            if (just_pressed & KEY_X)
            {
                suicune_phase_slot = (suicune_phase_slot + 1U) & 15U;
                continue;
            }
            if (just_pressed & KEY_Y)
            {
                suicune_phase_slot = (suicune_phase_slot + 15U) & 15U;
                continue;
            }
        }

'''
m=m[:a]+selector+m[b:]

# Rewrite only the absolute-resume target calculation inside the established
# resume-lock block.  Leave the surrounding timing/telemetry path untouched.
a=m.find('                    u32 wanted = suicune_phase_slot & 7U;')
b=m.find('                    suicune_phase_target_tick = target;',a)
need(a>=0 and b>a,'resume mod8 block missing')
resume='''                    u32 wanted = suicune_phase_slot & 15U;
                    // v7.4.2 controls the complete absolute cycle mod16.
                    u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;
                    while (((u32)cycle & 15U) != wanted) cycle++;
                    u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;
                    if (target <= now + 4096ULL)
                    {
                        cycle += 16ULL;
                        target = cycle * SUICUNE_PHASE_PERIOD_TICKS;
                    }
'''
m=m[:a]+resume+m[b:]

# Keep START fixed to M0; update status text and show the actual chosen M live.
t=t.replace('S741 B{} TURBO','S742 B{} TURBO')
t=t.replace('S741 B{} SWEEP FOUND','S742 B{} SWEEP FOUND')
t=t.replace('S741 NEED A EPOCH','S742 NEED A EPOCH')
old='            pnp::println!("SLOT0 BASE  X=+1");'
need(old in t,'old resume UI missing')
t=t.replace(old,'            pnp::println!("RESUME M{:02} X+1 Y-1",pnp::fixed_a_frame().phase_slot & 15);',1)

# Replace the complete v7.4.1 slot_sweep save block, using its header as the
# anchor.  Actual POST remains classified from the captured trace entries.
h=t.find('slot_sweep,version,target_bucket')
need(h>=0,'slot_sweep CSV header missing')
a=t.rfind('        line.clear();',0,h)
b=t.find('        pnp::trace_file_write(line.as_bytes());',h)
need(a>=0 and b>a,'slot_sweep CSV block bounds missing')
b += len('        pnp::trace_file_write(line.as_bytes());')
block='''        line.clear();
        let actual_raw=self.probe_result.map(|x|x.raw_dv).unwrap_or(0);
        let actual_route=self.probe_result.map(|x|x.route).unwrap_or(0);
        let sweep_post=classify_post_entries(self.entries,self.len,self.probe_target.advance);
        let sweep_spm=pnp::start_phase_metrics();
        let start_cycle_mod16=if sweep_spm.period!=0{((sweep_spm.actual/sweep_spm.period)&15)as u32}else{255};
        let start_remainder=if sweep_spm.period!=0{sweep_spm.actual%sweep_spm.period}else{0};
        let start_error=sweep_spm.actual as i128-sweep_spm.target as i128;
        let resume_cycle_mod16=if rpm.period!=0{((rpm.actual/rpm.period)&15)as u32}else{255};
        let resume_remainder=if rpm.period!=0{rpm.actual%rpm.period}else{0};
        let resume_error=rpm.actual as i128-rpm.target as i128;
        let _=write!(line,
            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_resume_mod16,actual_resume_mod16,post_proto,post_rot,post_score,raw_dv,route,freeze_delta,start_cycle_mod16,start_remainder,start_error_ticks,resume_remainder,resume_error_ticks\\nSWEEP,V742,{},{},{},{},{},{},{},{:04X},{},{},{},{},{},{},{}\\n",
            self.sweep_target_bucket,self.bucket_current,rpm.slot&15,resume_cycle_mod16,
            if sweep_post.valid{sweep_post.proto as char}else{'?'},sweep_post.rot40,sweep_post.best_score,
            actual_raw,actual_route,self.sweep_freeze_delta,start_cycle_mod16,start_remainder,start_error,
            resume_remainder,resume_error);
        pnp::trace_file_write(line.as_bytes());'''
t=t[:a]+block+t[b:]

M.write_text(m); T.write_text(t)
print('Applied v7.4.2 Full16 Resume Probe: absolute START M0 retained; absolute Resume M0..M15 selectable')
