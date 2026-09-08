from pathlib import Path
import shutil,subprocess
root=Path(__file__).resolve().parent
def rep(s,a,b,count=1):
    assert s.count(a)==count,(a[:90],s.count(a),count)
    return s.replace(a,b)
subprocess.run(['python3',str(root/'v7108/generate_model.py')],check=True)
for name in ('audio_sim.c','rank_core.c','rank_runtime.c'):
    shutil.copy2(root/'v7108'/name,root/'3gx/sources'/('v7108_'+name))
for name in ('rank_core.h','rank_runtime.h','rank_model.h'):
    shutil.copy2(root/'v7108'/name,root/'3gx/includes'/name)
f=root/'3gx/sources/main.c';c=f.read_text()
c=rep(c,'static bool is_paused = false;','#include "rank_runtime.h"\n#include "rank_core.h"\nstatic bool rank7108_hunting=false;\nstatic bool is_paused = false;')
# An explicit pause key is handled before the legacy held-key neutral guard.
anchor='        // v7.3.2 authoritative frozen-root lock.'
c=rep(c,anchor,'''        if(rank7108_hunting && !suicune_live_pass_ready && (just_pressed & KEY_SELECT)) {
            rank7108_hunting=false;suicune_root_lock_active=false;
            suicune_root_lock_ready=false;suicune_root_lock_failed=true;
            suicune_neutral_probe_pending=false;suicune_wait_up_after_b=false;
            v7102_panel("S7108 SEARCH PAUSED","Y+DOWN: RESTART SEARCH","NO GAME INPUT SENT");
            continue;
        }

'''+anchor)
c=rep(c,'''                    v7102_ready_panel();
                    if (suicune_phase_slot''','''                    if(rank7108_hunting) {
                        suicune_live_pass_ready=false;
                        suicune_neutral_probe_frames=3U;
                        suicune_neutral_probe_remaining=3U;
                        suicune_neutral_probe_executed=0;
                        suicune_neutral_probe_pending=true;
                        suicune_start_phase_slot=3U;
                        suicune_wait_up_after_b=true;
                        v7102_panel("S7108 CHECKING CANDIDATE","RELEASE ALL BUTTONS","SELECT: PAUSE SEARCH");
                    } else v7102_ready_panel();
                    if (suicune_phase_slot''')
c=rep(c,'''                suicune_neutral_probe_pending = false;
                arm_suicune_probe();''','''                suicune_neutral_probe_pending = false;
                if(rank7108_hunting) {
                    int decision=rank7108_evaluate();
                    if(!rank7108_log_scan(decision))decision=-1;
                    if(decision<0 || (decision>0 && !rank7108_commit())) {
                        char info[32];snprintf(info,sizeof(info),"ERROR %08lX",(unsigned long)rank7108_error());
                        rank7108_hunting=false;suicune_wait_up_after_b=false;
                        suicune_root_lock_active=false;suicune_root_lock_ready=false;suicune_root_lock_failed=true;
                        v7102_panel("S7108 PREDICTION STOPPED",info,"NO UP - RECORD ERROR CODE");
                        continue;
                    }
                    if(decision==0) {
                        char info[32];snprintf(info,sizeof(info),"CHECK %lu COST %lu",(unsigned long)rank7108_checks(),(unsigned long)rank7108_cycles());
                        suicune_wait_up_after_b=false;suicune_root_lock_ready=false;
                        suicune_root_lock_active=true;suicune_root_lock_failed=false;
                        v7102_panel("S7108 SEARCHING",info,"SELECT: PAUSE SEARCH");
                        continue;
                    }
                }
                arm_suicune_probe();''')
c=rep(c,'''                if(suicune_live_pass_ready) v7102_panel("S7107 RECORD ARMED","HOLD UP UNTIL PAUSED","THEN RELEASE UP");''','''                if(suicune_live_pass_ready && rank7108_hunting) {
                    char title[32];snprintf(title,sizeof(title),"TRY %04X RANK %lu",rank7108_best_shiny(),(unsigned long)rank7108_best_rank());
                    v7102_panel(title,"HOLD UP UNTIL PAUSED","THEN RELEASE UP");
                }
                else if(suicune_live_pass_ready) v7102_panel("S7107 RECORD ARMED","HOLD UP UNTIL PAUSED","THEN RELEASE UP");''')
c=rep(c,'''            // Stage3 current-root live scan start.
            if (just_pressed & KEY_DDOWN)
            {''','''            // Ranked experiment: auto-check frozen PRE candidates before UP.
            if (just_pressed & KEY_DDOWN)
            {
                rank7108_begin();rank7108_hunting=false;suicune_live_pass_ready=false;
                if(!rank7108_rom_preflight()) {
                    suicune_root_lock_active=false;suicune_root_lock_ready=false;suicune_root_lock_failed=true;
                    suicune_neutral_probe_pending=false;suicune_wait_up_after_b=false;
                    char info[32];snprintf(info,sizeof(info),"ERROR %08lX",(unsigned long)rank7108_error());
                    v7102_panel("S7109 ROM CHECK STOP",info,rank7108_rom_dump_ok()?"ROM DUMP SAVED - RETURN SD":"NO UP - DIAGNOSTIC NOT SAVED");
                    continue;
                }
                rank7108_hunting=true;''')
c=c.replace('S7107','S7108').replace('S7108 ','S7109 ')
f.write_text(c)

f=root/'reader_core/src/crystal/trace.rs';t=f.read_text()
marker='    pub fn status_line(&self) ->'
t=rep(t,marker,'''    // Frozen PRE validation, identical to the collector's neutral3 condition.
    pub fn ranked_pre_state(&self,reader:&Gen2Reader)->u32 {
        let cur=rng_advance();
        let total=(self.practical_live_found_state>>8) as u32+450;
        let ss=(self.practical_live_found_state as u8).wrapping_sub(451u16 as u8).wrapping_sub((total>>8) as u8);
        let expected=(((total&255) as u16)<<8)|ss as u16;
        let div=measured_div();
        let ap=((div>>8)<<6)|(adiv_subtick() as u16);
        let sp=((div&255)<<6)|(sdiv_subtick() as u16);
        if self.probe_session || cur.wrapping_sub(self.practical_live_found_advance)!=3
            || reader.rng_state()!=expected || ap!=0x2a35 || sp!=0x2a40 || pnp::current_keys()!=0 {return 0;}
        0x80000000u32|expected as u32
    }

'''+marker)
t=rep(t,'        super::research::save();','''        extern "C" {fn rank7108_append_result(advance:u32,present:u32,dv:u32);}
        let rdv=self.probe_result.map(|r|r.raw_dv as u32).unwrap_or(0);
        unsafe {rank7108_append_result(self.probe_target.advance,self.probe_result.is_some() as u32,rdv);}
        super::research::save();''')
t=t.replace('S7107','S7109').replace('STALLPHASE,V7107,','STALLPHASE,V7109,')
t=t.replace('S7109 OBSERVE SCAN','S7109 RANK SEARCH').replace('S7109 ROOT READY','S7109 CHECKING PRE')
f.write_text(t)
f=root/'reader_core/src/crystal/frame.rs';s=f.read_text()
s+='''
pub fn ranked_pre_state(advance:*mut u32)->u32 {
    if advance.is_null(){return 0;}
    let reader=Gen2Reader::crystal();
    let state=unsafe {get_state()};
    unsafe {*advance=super::hook::rng_advance();}
    state.trace.ranked_pre_state(&reader)
}
''';f.write_text(s)
f=root/'reader_core/src/crystal/mod.rs';s=f.read_text();s+='\npub use frame::ranked_pre_state;\n';f.write_text(s)
f=root/'reader_core/src/lib.rs';s=f.read_text()
s+='''
#[no_mangle]
pub extern "C" fn suicune_rank_pre_state(advance:*mut u32)->u32 {
    if let Ok(LoadedTitle::CrystalJp)=loaded_title(){crystal::ranked_pre_state(advance)}else{0}
}
''';f.write_text(s)
print('Applied v7108 ranked PRE gate, durable pre-input prediction, physical Exact2/M14 retained')
