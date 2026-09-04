from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v768 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.8 integrated natural-input shiny probe.
# Base: generated v7.6.7f (no HID masking, JP FFA2..FFA9 observer).
# No HID/GB/RNG/DIV/DV writes are added. Exact2F is produced only by the
# existing pause/single-frame scheduler while the user physically holds UP.

M = Path('3gx/sources/main.c')
m = M.read_text()
old_stage = '''        // v7.3.3 stage 2: after B-only ARM, wait frozen until B is fully
        // released and physical UP is held. Then hand off to the unchanged
        // Exact-2F scheduler. UP is intentionally excluded from its modifier
        // release gate, so the two VC frames contain UP and no B.
        // v7.6.7 stage 2: after B release, only physical UP may remain.
        // If HID masking could not be armed, stay frozen (fail closed).
        // Otherwise resume the VC continuously; rJOYP reads are masked in
        // Rust for 16 input frames, passed for 2, then masked again.
        if (suicune_wait_up_after_b)
        {
            const u32 stage2_block = KEY_A | KEY_B | KEY_X | KEY_Y |
                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R |
                KEY_START | KEY_SELECT;
            if ((held & stage2_block) != 0)
            {
                svcSleepThread(1000000);
                continue;
            }
            if (held & KEY_DUP)
            {
                if (!suicune_live_pass_ready)
                {
                    svcSleepThread(1000000);
                    continue;
                }
                // v7.6.7d: no paused write-test. The only meaningful test is
                // the hook-timed clear immediately before Crystal reads rJOYP.
                suicune_wait_up_after_b = false;
                fixed_frames_remaining = 0;
                fixed_run_pending = false;
                fixed_armed = false;
                suicune_auto_resume_pending = false;
                suicune_phase_lock_active = false;
                suicune_start_phase_lock_active = false;
                is_paused = false;
                break;
            }
            svcSleepThread(1000000);
            continue;
        }
'''
new_stage = '''        // v7.6.8 integrated natural-input path.  B arms the frozen root.
        // After B is fully released, the user physically holds UP.  We do NOT
        // alter HID or GB joypad memory.  Instead, the existing paused
        // single-frame scheduler releases exactly two VC frames, freezes again
        // while UP is released by the user, then controlled-resumes naturally.
        if (suicune_wait_up_after_b)
        {
            const u32 stage2_block = KEY_A | KEY_B | KEY_X | KEY_Y |
                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R |
                KEY_START | KEY_SELECT;
            if ((held & stage2_block) != 0)
            {
                svcSleepThread(1000000);
                continue;
            }
            if (held & KEY_DUP)
            {
                if (!suicune_live_pass_ready)
                {
                    svcSleepThread(1000000);
                    continue;
                }
                suicune_wait_up_after_b = false;
                fixed_a_frames = 2;
                fixed_frames_remaining = 0;
                fixed_armed = true;
                fixed_run_pending = true;
                suicune_auto_resume_pending = true;
                // Keep the existing start/resume phase locks.  No game frame
                // is released here; fixed_run_pending starts Exact2F only after
                // the B/modifier release gate is clean.
                continue;
            }
            svcSleepThread(1000000);
            continue;
        }
'''
m = rep(m, old_stage, new_stage, 'natural Exact2F stage2')
restore_pair = '        hid_up_mask_restore();\n        scan_input();'
if m.count(restore_pair) != 2:
    raise SystemExit(f'v768 restore-before-scan: expected 2 matches, got {m.count(restore_pair)}')
m = m.replace(restore_pair, '        scan_input();')
M.write_text(m)

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()
h = rep(h, 'const LIVE_MASK_FRAMES: u32 = 16;\nconst LIVE_PASS_FRAMES: u32 = 2;\nconst LIVE_POST_FRAMES: u32 = 4;\nconst LIVE_SAMPLE_CAP: usize = 22;',
'''const LIVE_MASK_FRAMES: u32 = 0;
const LIVE_PASS_FRAMES: u32 = 2;
const LIVE_POST_FRAMES: u32 = 6;
const LIVE_SAMPLE_CAP: usize = 8;''', 'input window constants')

h = rep(h,
'''    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
}''',
'''    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
    pub rjoy_sample_count: u8,
    pub rjoy_sample_rel: [u8; LIVE_SAMPLE_CAP],
    pub rjoy_sample_tick: [u64; LIVE_SAMPLE_CAP],
    pub rjoy_sample_mcycle: [u8; LIVE_SAMPLE_CAP],
    pub rjoy_sample_pc: [u16; LIVE_SAMPLE_CAP],
    pub rjoy_sample_div: [u8; LIVE_SAMPLE_CAP],
    pub rjoy_last_sample_advance: u32,
}''', 'rjoy telemetry fields')

h = rep(h,
'''        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
    };''',
'''        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
        rjoy_sample_count: 0,
        rjoy_sample_rel: [0; LIVE_SAMPLE_CAP],
        rjoy_sample_tick: [0; LIVE_SAMPLE_CAP],
        rjoy_sample_mcycle: [0; LIVE_SAMPLE_CAP],
        rjoy_sample_pc: [0; LIVE_SAMPLE_CAP],
        rjoy_sample_div: [0; LIVE_SAMPLE_CAP],
        rjoy_last_sample_advance: 0,
    };''', 'rjoy defaults')

# Add a cheap gate so trace.rs avoids eight HRAM reads after the first 8 advances.
anchor = '''pub fn live_pass_telemetry() -> LivePassTelemetry {
    unsafe {
        let mut out = LIVE_PASS;
        let (bf, rf) = pnp::hid_mask_stats();
        out.begin_failures = bf.wrapping_sub(LIVE_PASS_BEGIN_FAILURE_BASE);
        out.restore_failures = rf.wrapping_sub(LIVE_PASS_RESTORE_FAILURE_BASE);
        out
    }
}
'''
insert = anchor + '''
pub fn live_pass_needs_joymap_sample() -> bool {
    unsafe { LIVE_PASS_ARMED && (LIVE_PASS.joy_sample_count as usize) < LIVE_SAMPLE_CAP }
}
'''
h = rep(h, anchor, insert, 'joymap sample gate')

# Replace the no-mask rJOYP observer with a bounded first-8-advance timing sampler.
start = h.index('fn live_pass_filter_rjoy(requested: u32) {')
end = h.index('\n}\n\n// Suicune VBlank Context v5.2.', start) + 2
# Build the bounded read-only rJOYP timing sampler.
new_func = '''fn live_pass_filter_rjoy(requested: u32) {
    if requested != RJOYP_ADDR {
        return;
    }

    unsafe {
        if !LIVE_PASS_ARMED {
            return;
        }
        let now = RNG_ADVANCE;
        if LIVE_PASS.rjoy_last_sample_advance == now && LIVE_PASS.rjoy_sample_count != 0 {
            return;
        }
        let idx = LIVE_PASS.rjoy_sample_count as usize;
        if idx >= LIVE_SAMPLE_CAP {
            return;
        }
        LIVE_PASS.rjoy_last_sample_advance = now;
        LIVE_PASS.rjoy_reads = LIVE_PASS.rjoy_reads.wrapping_add(1);
        let tick = pnp::system_tick();
        let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
        let pc = Gen2Reader::crystal().pc_reg();
        let div = Gen2Reader::crystal().div();
        LIVE_PASS.rjoy_sample_rel[idx] = now.wrapping_sub(LIVE_PASS.first_input_advance) as u8;
        LIVE_PASS.rjoy_sample_tick[idx] = tick;
        LIVE_PASS.rjoy_sample_mcycle[idx] = mcycle;
        LIVE_PASS.rjoy_sample_pc[idx] = pc;
        LIVE_PASS.rjoy_sample_div[idx] = div;
        LIVE_PASS.rjoy_sample_count = LIVE_PASS.rjoy_sample_count.saturating_add(1);
    }
}'''
h = h[:start] + new_func + h[end:]
H.write_text(h)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
t = rep(t,
'use super::hook::{live_pass_observe_joymap, live_pass_should_finish, live_pass_telemetry};',
'use super::hook::{live_pass_needs_joymap_sample, live_pass_observe_joymap, live_pass_telemetry};',
'trace imports')

old_obs = '''        // v7.6.7f: read-only JP VC Crystal joypad chain FFA2..FFA9.
        // These addresses were established by prior cold-boot physical-input traces.
        let joymap = [
            gb_mem::read_u8(0xffa2), gb_mem::read_u8(0xffa3),
            gb_mem::read_u8(0xffa4), gb_mem::read_u8(0xffa5),
            gb_mem::read_u8(0xffa6), gb_mem::read_u8(0xffa7),
            gb_mem::read_u8(0xffa8), gb_mem::read_u8(0xffa9),
        ];
        live_pass_observe_joymap(joymap, pnp::current_keys());

        // v7.6.7 stops only after the 2F pass and four remasked frames.
        // The live HID filter remains armed until the host freeze takes effect.
        if self.probe_session && live_pass_should_finish() {
            self.stop();
            self.save();
            pnp::request_pause();
            return;
        }
'''
new_obs = '''        // v7.6.8: read the JP joypad chain only for the first eight running
        // advances (Exact2F plus the first resumed frames).  After that, no
        // extra joypad HRAM reads are performed, keeping rel20..DV close to the
        // production path.
        if live_pass_needs_joymap_sample() {
            let joymap = [
                gb_mem::read_u8(0xffa2), gb_mem::read_u8(0xffa3),
                gb_mem::read_u8(0xffa4), gb_mem::read_u8(0xffa5),
                gb_mem::read_u8(0xffa6), gb_mem::read_u8(0xffa7),
                gb_mem::read_u8(0xffa8), gb_mem::read_u8(0xffa9),
            ];
            live_pass_observe_joymap(joymap, pnp::current_keys());
        }
'''
t = rep(t, old_obs, new_obs, 'bounded joy observation/no early finish')

old_rel40 = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                // v7.6.6 ends every diagnostic run at rel40 after recording the
                // actual POST/J/state/div and suffix-gate support.  This avoids a
                // 700-frame tail and makes each M replicate fast and comparable.
                self.practical_fail(13);return
'''
new_rel40 = '''                let lp=live_pass_telemetry();
                // Exact2F is authoritative on Crystal's own game-side held
                // input: both released frames must show UP in FFA8, and none of
                // the first post-release samples may still show UP.
                if lp.game_pass_observed_advances != 2 || lp.game_pass_up_advances != 2
                    || lp.game_remask_up_advances != 0 {
                    self.practical_fail(15);return
                }
                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                // v7.6.8 is both a diagnostic and a real shiny attempt.  A
                // no-shiny rel40 inverse result aborts immediately.  A surviving
                // shiny prediction is rebound to the actual POST/state/div and
                // allowed to continue naturally through 716/717, stop2 and DV.
                if let Some(pred)=g.prediction {
                    self.rebind_practical_post_v690(pred,post.proto,post.rot40);
                } else {
                    self.practical_fail(14);return
                }
'''
t = rep(t, old_rel40, new_rel40, 'rel40 continue/abort gate')

# Version/section labels.
t = t.replace('LIVEPASS,V767F,', 'INPUTLAB,V768,')
t = t.replace('LIVEPASSHOST,V767F,', 'INPUTHOST,V768,')
t = t.replace('JOYMAP,V767F,', 'JOYMAP,V768,')
t = t.replace('JOYFRAME,V767F,', 'JOYFRAME,V768,')
# Cap exported raw joy rows at 8.
t = t.replace('for i in 0..n.min(22) {', 'for i in 0..n.min(8) {')

# Append rJOYP timing rows and one compact integrated verdict before file close.
old_close = '''        pnp::trace_file_close();
        set_vblank_context_capture(true);'''
new_close = '''        line.clear();
        let _ = write!(line, "\\nrjoy_frames,version,index,rel_advance,tick,mcycle,pc,div\\n");
        pnp::trace_file_write(line.as_bytes());
        let rn = lp.rjoy_sample_count as usize;
        for i in 0..rn.min(8) {
            line.clear();
            let _ = write!(
                line,
                "RJOYFRAME,V768,{},{},{},{:02X},{:04X},{:02X}\\n",
                i, lp.rjoy_sample_rel[i], lp.rjoy_sample_tick[i],
                lp.rjoy_sample_mcycle[i], lp.rjoy_sample_pc[i], lp.rjoy_sample_div[i]
            );
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _=write!(line,
            "\\nintegrated,version,exact_frames,resume_slot,input_samples,input_pass_seen,input_pass_up,input_post_up,state40,div40,post_proto,post_rot,post_score,gate_models,gate_eval,gate_shiny,pred_raw,pred_lane,pred_source,pred_support,stop2_offset,actual_raw,actual_route,miss\\nINTEGRATED,V768,2,{},{},{},{},{},{:04X},{:04X},{},{},{},{},{},{},{:04X},{},{},{},{},{},{:04X},{},{}\\n",
            pnp::fixed_a_frame().phase_slot & 15,
            lp.joy_sample_count,lp.game_pass_observed_advances,lp.game_pass_up_advances,lp.game_remask_up_advances,
            self.v763_rel40_state,self.v763_rel40_div,
            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,self.practical_post_score,
            self.v763_gate_models,self.v763_gate_evaluated,self.v763_gate_shiny_models,
            self.practical_raw,self.practical_lane,self.practical_source,self.practical_support,
            self.endpoint.stop2_offset,actual_raw,actual_route,self.practical_miss);
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();
        set_vblank_context_capture(true);'''
t = rep(t, old_close, new_close, 'integrated CSV tail')

# Clear operator instructions for the two paused input stages.
t = rep(t,
'''    pub fn draw_rng_status(&self) {
        if self.practical_scan_enabled {''',
'''    pub fn draw_rng_status(&self) {
        let ff = pnp::fixed_a_frame();
        if self.probe_session && ff.armed && !ff.running && !ff.pending {
            if ff.physical_up {
                pnp::println!("S768 EXACT2F DONE");
                pnp::println!("RELEASE UP - AUTO RESUME");
            } else {
                pnp::println!("S768 ROOT ARMED");
                pnp::println!("HOLD UP ONLY");
            }
            return;
        }
        if self.practical_scan_enabled {''',
'operator stage display')

t = t.replace('S766 PHASE PROBE SCAN', 'S768 SHINY INTEGRATED')
t = t.replace('THEN B -> RELEASE -> UP', 'THEN B -> RELEASE -> HOLD UP')
t = t.replace('B -> RELEASE -> UP', 'B -> RELEASE -> HOLD UP')

# Better operator-visible failure reasons.
t = rep(t,
'''            } else if self.practical_miss == 13 {
                pnp::println!("WHY REL40 CAPTURE");
            } else {''',
'''            } else if self.practical_miss == 13 {
                pnp::println!("WHY REL40 CAPTURE");
            } else if self.practical_miss == 14 {
                pnp::println!("WHY REL40 NONSHINY");
            } else if self.practical_miss == 15 {
                pnp::println!("WHY INPUT NOT EXACT2F");
            } else {''',
'visible failure labels')
T.write_text(t)

print('Applied v7.6.8 integrated natural Exact2F + rel40 shiny gate + full tail')
