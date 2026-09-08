#!/usr/bin/env python3
"""Apply only to the regenerated v7100 source. Never touches guest state."""
from pathlib import Path
import hashlib, shutil

def replace(s, old, new, count=1):
    assert s.count(old)==count, (old[:100],s.count(old),count)
    return s.replace(old,new)

tpath=Path('reader_core/src/crystal/trace.rs');cpath=Path('3gx/sources/main.c')
t=tpath.read_text();c=cpath.read_text()
assert 'V7101_ARM_OK' not in t
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in t
t='''// v7.10.1: observational candidate pilot; no success-rate claim.
#[path = "v7101_model.rs"]
mod v7101_model;
static mut V7101_ARM_OK: bool = false;
static mut V7101_ROOT_SEEN: u32 = 0;
static mut V7101_ROOT_REJECT: u32 = 0;
static mut V7101_LAST_ROOT: u32 = u32::MAX;
fn v7101_check_root(advance: u32, state: u16) -> bool {
    let candidate=v7101_model::root_candidate(state);
    unsafe {
        if V7101_LAST_ROOT != advance {
            V7101_LAST_ROOT=advance;
            V7101_ROOT_SEEN=V7101_ROOT_SEEN.saturating_add(1);
            if !candidate { V7101_ROOT_REJECT=V7101_ROOT_REJECT.saturating_add(1); }
        }
    }
    candidate
}

'''+t
t=replace(t,'    fn reset_scan_epoch(&mut self) {','''    fn reset_scan_epoch(&mut self) {
        unsafe { V7101_ARM_OK=false; V7101_ROOT_SEEN=0; V7101_ROOT_REJECT=0; V7101_LAST_ROOT=u32::MAX; }''')
t=replace(t,'        if bucket != 76 { return; }','''        if bucket != 76 { return; }
        // Cheap host-memory lookup only after the existing exact phase test.
        if !v7101_check_root(cur,reader.rng_state()) { return; }''')
t=replace(t,'        let mut out = 0u32;\n        if phase_probe', '''        let mut out = 0u32;
        // Bit25 is an arm-time consistency check, not a shiny prediction.
        if self.probe_session && self.probe_active && unsafe { V7101_ARM_OK } { out |= 1u32 << 25; }
        if phase_probe''')
t=replace(t,'''            let phase_ready = phase_probe && proto == b'A' && rot == 10
                && bucket_valid && bucket == 76;''','''            let phase_cell = phase_probe && proto == b'A' && rot == 10
                && bucket_valid && bucket == 76;
            let candidate = phase_cell && v7101_check_root(cur,reader.rng_state());
            // Revalidate the actually frozen state; asynchronous pause may drift.
            let phase_ready = candidate;''')
t=replace(t,'''        self.state = TraceState::Armed;
    }

    fn update_suicune_endpoint''','''        // Always use the native-result observation lane; old rel40 hard rejects
        // are not justified by the modern trace corpus.
        self.practical_active = false;
        self.practical_candidate_valid = false;
        unsafe {
            V7101_ARM_OK = self.practical_live_found_lane == 252
                && v7101_model::arm_matches(self.practical_live_found_state,
                    self.probe_target.state,
                    self.probe_target.advance.wrapping_sub(self.practical_live_found_advance),
                    direct_phase_m((self.probe_target.div >> 8) as u8, self.probe_target.asub),
                    direct_phase_m(self.probe_target.div as u8, self.probe_target.ssub),
                    pnp::start_phase_metrics().slot as u32);
            if !V7101_ARM_OK {
                self.probe_active=false;
                self.practical_miss=16;
                self.state=TraceState::Done;
                return;
            }
        }
        self.state = TraceState::Armed;
    }

    fn update_suicune_endpoint''')
# Model negatives at DV-2 are advisory. Existing v797 force-final remains true.
t=replace(t,'preserve the hard-negative','preserve the empirical-negative')
t=replace(t,'"S786 NEUTRAL SCAN A/r10 B76"','"S7101 CANDIDATE SCAN"',2)
t=replace(t,'"S786 NEUTRAL ROOT READY"','"S7101 CANDIDATE READY"')
t=replace(t,'"NEUTRAL {}F X+1 Y-1",sp.slot','"NEUTRAL {}F FIXED",sp.slot')
t=replace(t,'"PRESS UP BLIND + FINAL DV"','"CANDIDATE: HOLD UP"')
t=replace(t,'"ADV{} ROOT{}",rng_advance(),self.practical_live_checked',
    '"ROOT {} SKIP {}",unsafe { V7101_ROOT_SEEN },unsafe { V7101_ROOT_REJECT }')
a=t.index('        } else if self.probe_session && self.probe_active && !self.practical_active {')
b=t.index('        } else if self.practical_miss != 0 {',a)
t=t[:a]+'''        } else if self.probe_session && self.probe_active && !self.practical_active {
            pnp::println!("S7101 CANDIDATE RUN");
            pnp::println!("WAIT FOR FINAL DV");
            pnp::println!("RELEASE UP AT PAUSE");
'''+t[b:]
t=replace(t,'    pub fn draw_rng_status(&self) {','''    pub fn draw_rng_status(&self) {
        // Only actual enemy DV bytes may be labelled shiny.
        if let Some(result) = self.probe_result {
            pnp::println!("S7101 FINAL {:04X}", result.raw_dv);
            if exact_tail_is_shiny(result.raw_dv) {
                pnp::println!("SHINY - CATCH IT!");
                pnp::println!("START: RESUME / CATCH");
            } else {
                pnp::println!("NOT SHINY");
                pnp::println!("RESET VC MANUALLY");
            }
            pnp::println!("CSV {}", pnp::trace_written_slot());
            return;
        }
        if self.practical_miss == 16 {
            pnp::println!("S7101 ARM MISMATCH");
            pnp::println!("NO UP - RESET VC");
            return;
        }''')
t=replace(t,'        pnp::trace_file_close();\n        unsafe { v798_save_cal_if_dirty();', '''        line.clear();
        let _=write!(line,"\\nv7101_pre,status,root_seen,root_rejected,arm_ok,root_state,target_state,model_roots,model_total\\nPRE7101,EXPERIMENTAL,{},{},{},{:04X},{:04X},5887,65536\\n",
            unsafe { V7101_ROOT_SEEN },unsafe { V7101_ROOT_REJECT },unsafe { V7101_ARM_OK } as u8,
            self.practical_live_found_state,self.probe_target.state);
        pnp::trace_file_write(line.as_bytes());
        pnp::trace_file_close();
        unsafe { v798_save_cal_if_dirty();''')

# Cache the existing top-screen surfaces only to refresh instructions while
# frozen. This does not call run_frame(), release a frame, or read guest memory.
c=replace(c,'static bool is_paused = false;', '''static bool is_paused = false;
static u8 *v7101_top_a=NULL, *v7101_top_b=NULL;
static u32 v7101_top_stride=0, v7101_top_format=0;
static bool v7101_release_shown=false;
extern void reset_print(void);
static void v7101_pause_panel(const char *a, const char *b, const char *d)
{
    u8 *buffers[2]={v7101_top_a,v7101_top_b};
    for (u32 i=0;i<2;i++) {
        if (buffers[i]==NULL || (i==1 && buffers[1]==buffers[0])) continue;
        reset_print(); host_set_print_max_len(32);
        host_print((u32)a,strlen(a),0xFFFFFF);
        host_print((u32)b,strlen(b),0xFFFFFF);
        host_print((u32)d,strlen(d),0xFFFFFF);
        draw_to_screen(0,buffers[i],v7101_top_stride,v7101_top_format);
        svcFlushProcessDataCache(CUR_PROCESS_HANDLE,(u32)buffers[i],v7101_top_stride*400U);
    }
}''')
c=replace(c,'''    if (isTopScreen)
    {
        hid_up_mask_restore();''','''    if (isTopScreen)
    {
        v7101_top_a=fb_a; v7101_top_b=fb_b;
        v7101_top_stride=stride; v7101_top_format=format;
        hid_up_mask_restore();''')
c=replace(c,'''        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) == 0)''','''        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) && !v7101_release_shown) {
                v7101_release_shown=true;
                v7101_pause_panel("TWO UP POLLS COMPLETE", "RELEASE UP", "AUTO RESUME M14");
            }
            if ((held & KEY_DUP) == 0)''')
c=replace(c,'''                    suicune_root_lock_ready = true;
                    suicune_root_lock_active = false;''','''                    suicune_root_lock_ready = true;
                    suicune_root_lock_active = false;
                    v7101_pause_panel("S7101 CANDIDATE READY", "B -> RELEASE ALL KEYS", "EXPERIMENTAL / NOT GUARANTEED");''')
c=replace(c,'''                arm_suicune_probe();
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;''','''                arm_suicune_probe();
                if ((suicune_control_pause_cell() & (1U << 25)) == 0) {
                    suicune_wait_up_after_b=false;
                    fixed_armed=false; suicune_live_pass_ready=false;
                    v7101_pause_panel("S7101 ARM MISMATCH", "DO NOT PRESS UP", "RESET VC MANUALLY");
                    continue;
                }
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;''')
c=replace(c,'''                suicune_start_phase_lock_active = false;
                continue;
            }

            // Neutral delay''','''                suicune_start_phase_lock_active = false;
                v7101_release_shown=false;
                if (suicune_live_pass_ready)
                    v7101_pause_panel("S7101 CANDIDATE ARMED", "HOLD UP UNTIL PAUSED", "THEN RELEASE UP");
                else
                    v7101_pause_panel("S7101 INPUT ARM FAILED", "DO NOT PRESS UP", "RESET VC MANUALLY");
                continue;
            }

            // Neutral delay''')
a=c.index('        // v7.8.6 neutral-frame selector.')
b=c.index('        // v7.2.4 robust diagnostic arm.',a)
c=c[:a]+'''        // v7101 candidate table is only defined for exactly three neutral frames.
        // X/Y cannot change this timing parameter.

'''+c[b:]
c=replace(c,'            suicune_neutral_probe_remaining = suicune_neutral_probe_frames;',
'''            suicune_neutral_probe_frames = 3U;
            suicune_neutral_probe_remaining = 3U;''')
# The modern workflow never needs R as a resume shortcut.
c=replace(c,'u32 resume_keys = fixed_armed ? (KEY_START | KEY_R) : (KEY_A | KEY_START | KEY_R);',
            'u32 resume_keys = fixed_armed ? KEY_START : (KEY_A | KEY_START);')

assert 'const u32 wanted = 14U;' in c
assert 'self.practical_live_found_lane = 252;' in t
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in t
tpath.write_text(t);cpath.write_text(c)
shutil.copyfile('v7101/model.rs',tpath.with_name('v7101_model.rs'))
shutil.copyfile('v7101/roots.bin',tpath.with_name('roots.bin'))
print('Applied v7101 empirical PRE candidate pilot; Exact2 + M14 + final DV preserved.')
