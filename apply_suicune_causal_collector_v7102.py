#!/usr/bin/env python3
"""Generate observation-only collector from pinned v7100, not candidate v7101."""
from pathlib import Path
import shutil
def rep(s,a,b,count=1):
    assert s.count(a)==count,(a[:100],s.count(a),count)
    return s.replace(a,b)
tpath=Path('reader_core/src/crystal/trace.rs');hpath=tpath.with_name('hook.rs');cpath=Path('3gx/sources/main.c')
t=tpath.read_text();h=hpath.read_text();c=cpath.read_text()
assert 'V7101_ARM_OK' not in t and 'v7101_check_root' not in t
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in t
t=rep(t,'''        self.state = TraceState::Armed;
    }

    fn update_suicune_endpoint''','''        self.practical_active=false;
        self.practical_candidate_valid=false;
        super::research::arm(self.probe_target.advance,self.practical_live_found_advance,self.practical_live_found_state);
        if super::research::suicune_research_arm_ok()==0 {
            self.probe_active=false;self.practical_miss=16;self.state=TraceState::Done;
            return;
        }
        self.state = TraceState::Armed;
    }

    fn update_suicune_endpoint''')
t=rep(t,'''        self.len += 1;

        // v7.6.7f''','''        self.len += 1;
        if self.probe_session && self.probe_active {
            super::research::frame((self.len-1) as u32,rng_advance());
        }

        // v7.6.7f''')
t=rep(t,'if V796_JPRED_VALID { v798_add_sample(', 'if V796_JPRED_VALID && super::research::mode()==0 { v798_add_sample(')
t=rep(t,'''    fn save(&mut self) {
        if self.len == 0 {''','''    fn save(&mut self) {
        super::research::finish();
        if self.len == 0 {''')
t=rep(t,'''        pnp::trace_file_close();
        unsafe { v798_save_cal_if_dirty(); v7100_save_if_dirty(); }''','''        super::research::save();
        pnp::trace_file_close();
        if super::research::mode()==0 { unsafe { v798_save_cal_if_dirty(); v7100_save_if_dirty(); } }''')
t=rep(t,'        self.save_result = Some(true);','        self.save_result = Some(pnp::trace_last_error()==0);')
t=rep(t,'    pub fn draw_rng_status(&self) {','''    pub fn draw_rng_status(&self) {
        if let Some(result)=self.probe_result {
            pnp::println!("S7104 {} DONE",super::research::mode_name());
            pnp::println!("DV {:04X}",result.raw_dv);
            if exact_tail_is_shiny(result.raw_dv) {
                pnp::println!("SHINY - CATCH IT!");
                pnp::println!("START: RESUME / CATCH");
            } else { pnp::println!("RESET VC FOR NEXT RUN"); }
            pnp::println!("CSV {} {}",self.save_status().0,pnp::trace_written_slot());
            return;
        }
        if self.practical_miss==16 {
            pnp::println!("S7104 CAPTURE FAILED");
            pnp::println!("NO UP - RESET VC");
            pnp::println!("CSV {}",pnp::trace_written_slot());
            return;
        }''')
t=rep(t,'"S786 NEUTRAL SCAN A/r10 B76"','"S7104 OBSERVE SCAN"',2)
t=rep(t,'"S786 NEUTRAL ROOT READY"','"S7104 ROOT READY"')
t=rep(t,'"NEUTRAL {}F X+1 Y-1",sp.slot','"NEUTRAL {}F FIXED",sp.slot')
a=t.index('        } else if self.probe_session && self.probe_active && !self.practical_active {')
b=t.index('        } else if self.practical_miss != 0 {',a)
t=t[:a]+'''        } else if self.probe_session && self.probe_active && !self.practical_active {
            pnp::println!("S7104 {} RECORD",super::research::mode_name());
            pnp::println!("WAIT FOR FINAL DV");
            pnp::println!("RELEASE UP AT PAUSE");
'''+t[b:]
t=rep(t,'STALLPHASE,V7100,','STALLPHASE,V7104,')

# Capture DEEP mode at all final-window DIV boundaries, including neighboring
# VBlank reads. Paired RNG states let analysis infer consumed A/S bytes without
# assuming the diagnostic pre-return DIV observation equals the consumed byte.
h=rep(h,'''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {''','''    if unsafe { ENDPOINT_FAST_TAIL } {
        super::research::div_boundary(rng_advance(),pc,regs,_stack_pointer);
    }
    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {''')

c=rep(c,'static bool is_paused = false;','''static bool is_paused = false;
static u32 v7102_mode=0;
u32 host_suicune_research_mode(void) { return v7102_mode; }
extern u32 suicune_research_arm_ok(void);
static u8 *v7102_top_a=NULL,*v7102_top_b=NULL;
static u32 v7102_stride=0,v7102_format=0;
static bool v7102_release_shown=false;
extern void reset_print(void);
static const char *v7102_name(void) {return v7102_mode==1?"TAIL":v7102_mode==2?"DEEP":"BASE";}
static void v7102_panel(const char *a,const char *b,const char *d) {
    u8 *buffers[2]={v7102_top_a,v7102_top_b};
    for(u32 i=0;i<2;i++) {
        if(!buffers[i] || (i==1 && buffers[0]==buffers[1])) continue;
        reset_print();host_set_print_max_len(32);
        host_print((u32)a,strlen(a),0xffffff);host_print((u32)b,strlen(b),0xffffff);host_print((u32)d,strlen(d),0xffffff);
        draw_to_screen(0,buffers[i],v7102_stride,v7102_format);
        svcFlushProcessDataCache(CUR_PROCESS_HANDLE,(u32)buffers[i],v7102_stride*400U);
    }
}
static void v7102_ready_panel(void) {
    char title[32];snprintf(title,sizeof(title),"S7104 %s READY",v7102_name());
    v7102_panel(title,"X: CHANGE MODE","B -> RELEASE ALL KEYS");
}''')
c=rep(c,'''    if (isTopScreen)
    {
        hid_up_mask_restore();''','''    if (isTopScreen)
    {
        v7102_top_a=fb_a;v7102_top_b=fb_b;v7102_stride=stride;v7102_format=format;
        hid_up_mask_restore();''')
c=rep(c,'''        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) == 0)''','''        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) && !v7102_release_shown) {
                v7102_release_shown=true;
                v7102_panel("TWO UP POLLS COMPLETE","RELEASE UP","AUTO RESUME M14");
            }
            if ((held & KEY_DUP) == 0)''')
c=rep(c,'''                    suicune_root_lock_ready = true;
                    suicune_root_lock_active = false;''','''                    suicune_root_lock_ready = true;
                    suicune_root_lock_active = false;
                    v7102_ready_panel();''')
c=rep(c,'''                arm_suicune_probe();
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;''','''                arm_suicune_probe();
                if (!suicune_research_arm_ok()) {
                    suicune_wait_up_after_b=false;fixed_armed=false;suicune_live_pass_ready=false;
                    v7102_panel("S7104 CAPTURE FAILED","NO UP - RESET VC","ERROR SNAPSHOT SAVED IF SD OK");
                    continue;
                }
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;''')
c=rep(c,'''                suicune_start_phase_lock_active = false;
                continue;
            }

            // Neutral delay''','''                suicune_start_phase_lock_active = false;
                v7102_release_shown=false;
                if(suicune_live_pass_ready) v7102_panel("S7104 RECORD ARMED","HOLD UP UNTIL PAUSED","THEN RELEASE UP");
                else v7102_panel("S7104 INPUT ARM FAILED","DO NOT PRESS UP","RESET VC MANUALLY");
                continue;
            }

            // Neutral delay''')
a=c.index('        // v7.8.6 neutral-frame selector.')
b=c.index('        // v7.2.4 robust diagnostic arm.',a)
c=c[:a]+'''        // X selects observation intensity only. Neutral3 and Exact2/M14 stay fixed.
        if(suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending
            && (just_pressed & KEY_X)) {
            v7102_mode=(v7102_mode+1U)%3U;
            v7102_ready_panel();continue;
        }

'''+c[b:]
c=rep(c,'            suicune_neutral_probe_remaining = suicune_neutral_probe_frames;',
'''            suicune_neutral_probe_frames=3U;
            suicune_neutral_probe_remaining=3U;''')
c=rep(c,'''                suicune_neutral_probe_frames = 3;
                suicune_neutral_probe_remaining''','''                v7102_mode=0;
                suicune_neutral_probe_frames = 3;
                suicune_neutral_probe_remaining''')
c=rep(c,'u32 resume_keys = fixed_armed ? (KEY_START | KEY_R) : (KEY_A | KEY_START | KEY_R);',
            'u32 resume_keys = fixed_armed ? KEY_START : (KEY_A | KEY_START);')
# A larger diagnostic CSV must not report OK after a short write or failed flush.
c=rep(c,'''    if (trace_file == 0)
    {
        return 0;
    }

    // Do not flush''','''    if (trace_file == 0)
    {
        if(trace_last_error==0) trace_last_error=0xF7102002U;
        return 0;
    }

    // Do not flush''')
c=rep(c,'''    if (R_FAILED(FSFILE_Write(trace_file, &written, trace_file_offset, data, len, 0)))
    {
        return 0;
    }

    trace_file_offset += written;''','''    Result result=FSFILE_Write(trace_file, &written, trace_file_offset, data, len, 0);
    if (trace_last_error==0 && (R_FAILED(result) || written!=len))
        trace_last_error=R_FAILED(result)?(u32)result:0xF7102001U;
    trace_file_offset += written;''')
c=rep(c,'''        FSFILE_Flush(trace_file);
        FSFILE_Close(trace_file);
        trace_file = 0;''','''        Result flushed=FSFILE_Flush(trace_file);
        Result closed=FSFILE_Close(trace_file);
        if(trace_last_error==0 && R_FAILED(flushed)) trace_last_error=(u32)flushed;
        if(trace_last_error==0 && R_FAILED(closed)) trace_last_error=(u32)closed;
        trace_file = 0;''')
m=tpath.with_name('mod.rs');ms=m.read_text();ms=rep(ms,'mod trace;','mod trace;\nmod research;')
assert 'const u32 wanted = 14U;' in c and 'suicune_neutral_probe_frames++' not in c
for path,content in [(tpath,t),(hpath,h),(cpath,c),(m,ms)]:path.write_text(content)
for name in ['research.rs','capture_plan.rs']:shutil.copyfile(Path('v7102')/name,tpath.with_name(name))
print('Applied v7102 BASE/TAIL/DEEP collector, no candidate filter, native final DV retained.')
