"""Apply after v7112: private native replay candidate gate and scheduled input."""
from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
for name in ['arm_core.c','shadow.c','gate_runtime.c']:
 shutil.copyfile(r/'v7113'/name,r/'3gx/sources'/('v7113_'+name))
for name in ['arm_core.h','shadow.h','gate_runtime.h','dv_endpoint.h']:
 shutil.copyfile(r/'v7113'/name,r/'3gx/includes'/name)
f=r/'reader_core/src/crystal/snapshot7111.rs';s=f.read_text();assert 'suicune_shadow7113_capture' not in s
s+='''
// The native predictor mutates ONLY this private buffer. Capture again before
// each hypothesis and before research::arm persists the actual input snapshot.
#[no_mangle]
pub extern "C" fn suicune_shadow7113_capture(target:u32,heap:*mut u32)->*mut u8 {unsafe{
    if heap.is_null() || !capture(target,true) || !PRESENT.iter().all(|v|*v) {return core::ptr::null_mut();}
    *heap=HEAP;core::ptr::addr_of_mut!(DATA).cast::<u8>()
}}
''';f.write_text(s)
f=r/'3gx/sources/main.c';s=f.read_text()
def rep(a,b,count=1):
 global s
 assert s.count(a)==count,(a[:90],s.count(a));s=s.replace(a,b)
rep('#include "rank_core.h"','#include "rank_core.h"\n#include "gate_runtime.h"')
rep('static const bool clock7110_collection=true;','static const bool clock7110_collection=false;\nstatic u32 gate7113_last_seconds=~0U;')
anchor='static void v7102_ready_panel(void) {'
rep(anchor,'''void host7113_progress(u32 check,u32 model,u32 frame) {
    char a[32],b[32];snprintf(a,sizeof(a),"S7113 CHECK %lu",(unsigned long)check);
    snprintf(b,sizeof(b),"MODEL %lu/2 FRAME %lu",(unsigned long)(model+1),(unsigned long)frame);
    v7102_panel(a,b,"SELECT: STOP - RELEASE OTHERS");
}
'''+anchor)
rep('rank7108_begin();rank7108_hunting=false;','gate7113_begin();gate7113_last_seconds=~0U;rank7108_hunting=false;')
for a,b in [('rank7108_evaluate()','gate7113_evaluate()'),('rank7108_log_scan(decision)','gate7113_log_scan(decision)'),('rank7108_commit()','gate7113_commit()'),('rank7108_checks()','gate7113_checks()')]:rep(a,b)
# Error from ROM preflight remains a rank-runtime error; evaluator uses gate error.
rep('(unsigned long)rank7108_error());\n                        rank7108_hunting=false;','(unsigned long)gate7113_error());\n                        rank7108_hunting=false;')
rep('"TRY %04X RANK %lu",rank7108_best_shiny(),(unsigned long)rank7108_best_rank()','"TRY SHINY DV %04X",gate7113_dv()')
rep('v7102_panel(title,"HOLD UP UNTIL PAUSED","THEN RELEASE UP");','v7102_panel(title,"WAIT FOR COUNTDOWN","SELECT: CANCEL CANDIDATE");')
# Capture timestamp for the eventual input. Do not replace physical input.
anchor='            // Neutral delay is complete. From here this is the proven v7.6.7'
rep(anchor,'''            if (gate7113_active()) {
                u64 now=svcGetSystemTick(),target=gate7113_launch_tick();
                if ((just_pressed & KEY_SELECT) || now>target+2681118ULL) {
                    gate7113_cancel();suicune_wait_up_after_b=false;suicune_live_pass_ready=false;
                    fixed_armed=false;rank7108_hunting=false;
                    v7102_panel("S7113 CANDIDATE CANCELLED","Y+DOWN: SEARCH AGAIN","STILL PAUSED");
                    continue;
                }
                u32 seconds=now<target?(u32)((target-now+268111855ULL)/268111856ULL):0;
                if(seconds!=gate7113_last_seconds){
                    gate7113_last_seconds=seconds;char a[32],b[32];
                    snprintf(a,sizeof(a),"TRY SHINY DV %04X",gate7113_dv());
                    snprintf(b,sizeof(b),"START IN %lu SEC",(unsigned long)seconds);
                    v7102_panel(a,b,seconds>5?"WAIT - SELECT TO CANCEL":"HOLD UP NOW UNTIL PAUSED");
                }
                if(now<target){svcSleepThread(1000000);continue;}
            }

'''+anchor)
# Keep M14 absolute phase. Only its occurrence is reserved in advance.
rep('''                suicune_obs_up_release_tick = now;
                suicune_phase_slot = wanted;''','''                if(gate7113_active()) {
                    target=gate7113_resume_tick();
                    if(now>=target) {
                        v7102_panel("S7113 RELEASE TOO LATE","STILL PAUSED","RESET VC BEFORE NEXT TRY");
                        svcSleepThread(1000000);continue;
                    }
                }
                suicune_obs_up_release_tick = now;
                suicune_phase_slot = wanted;''')
# Confirm release only after the reserved wait and a fresh physical key check.
rep('                suicune_exact2_release_confirmed();\n','')
rep('                while (svcGetSystemTick() < target) { }\n                suicune_phase_actual_tick = svcGetSystemTick();','''                while (svcGetSystemTick() < target) { }
                if(gate7113_active()) {
                    scan_input();
                    if(get_current_keys()!=0) {
                        v7102_panel("S7113 KEYS AT RESUME","STILL PAUSED","RESET VC BEFORE NEXT TRY");
                        continue;
                    }
                }
                suicune_exact2_release_confirmed();
                suicune_phase_actual_tick = svcGetSystemTick();''',1)
# A selected candidate can wait up to five seconds after launch for release.
s=s.replace('"AUTO RESUME M14"','"RELEASE NOW - AUTO RESUME"')
s=s.replace('S7112','S7113');f.write_text(s)
f=r/'reader_core/src/crystal/trace.rs';s=f.read_text();anchor='        super::research::save();';assert s.count(anchor)==1
s=s.replace(anchor,'''        extern "C" {fn gate7113_append_result(advance:u32,present:u32,dv:u32);}
        unsafe {gate7113_append_result(self.probe_target.advance,self.probe_result.is_some() as u32,rdv);}
'''+anchor).replace('STALLPHASE,V7112,','STALLPHASE,V7113,').replace('S7112','S7113');f.write_text(s)
f=r/'3gx/Makefile';s=f.read_text();anchor='-include $(DEPENDS)';assert s.count(anchor)==1;s=s.replace(anchor,'v7113_arm_core.o v7113_shadow.o: CFLAGS += -O3\n\n'+anchor);f.write_text(s)
print('Applied v7113 native-clone shiny candidate gate; physical UP, Exact2 and absolute M14 retained')
