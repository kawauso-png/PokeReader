from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
p=r/'3gx/sources/v7113_gate_runtime.c';s=p.read_text();old=(r/'v7119_mac/runtime.inc').read_text();assert s.count(old)==1;s=s.replace(old,(r/'v7120_mac/runtime.inc').read_text());p.write_text(s)
shutil.copyfile(r/'v7120_mac/protocol.h',r/'3gx/includes/mac7120_protocol.h')
p=r/'3gx/sources/v7116_snapshot.c';s=p.read_text();old=(r/'v7119_mac/io.inc').read_text();assert s.count(old)==1;s=s.replace(old,(r/'v7120_mac/io.inc').read_text()).replace('w[30]=7119','w[30]=7120').replace('\\"software\\":7119','\\"software\\":7120');p.write_text(s)
p=r/'3gx/sources/main.c';s=p.read_text();assert 'host7120_arm' not in s
anchor='void host7119_status(unsigned stage,unsigned done,unsigned detail)'
arm='''/* Accept only a clock-bound Mac prediction for the currently frozen state.
 * Uses the existing physical-UP Exact2 gate; does not synthesize UP. */
int host7120_arm(void){
 suicune_root_lock_active=false;suicune_root_lock_ready=true;suicune_root_lock_failed=false;
 suicune_neutral_probe_pending=false;
 if(clock7110_collection)return 0;
 arm_suicune_probe();
 if(!suicune_research_arm_ok())return 0;
 suicune_live_pass_ready=arm_suicune_live_pass()!=0;
 if(!suicune_live_pass_ready)return 0;
 suicune_observe_reset();suicune_early_lab_reset();suicune_obs_arm_tick=svcGetSystemTick();
 fixed_a_frames=2;fixed_frames_remaining=0;fixed_armed=true;fixed_run_pending=false;
 suicune_auto_resume_pending=false;suicune_phase_lock_active=false;suicune_start_phase_lock_active=false;
 v7102_release_shown=false;suicune_wait_up_after_b=true;rank7108_hunting=true;gate7113_last_seconds=~0U;
 v7102_panel("S7120 MAC CANDIDATE ARMED","WAIT FOR COUNTDOWN","SELECT: CANCEL CANDIDATE");
 return 1;
}

'''
assert s.count(anchor)==1;s=s.replace(anchor,arm+anchor).replace('S7119','S7120')
p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text().replace('S7119','S7120').replace('STALLPHASE,V7119,','STALLPHASE,V7120,');p.write_text(s)
p=r/'3gx/PokeReader.plgInfo';s=p.read_text();assert 'Revision: 19' in s;p.write_text(s.replace('Revision: 19','Revision: 20'))
print('Applied S7120 absolute neutral grid and separate physical-UP candidate arm')
