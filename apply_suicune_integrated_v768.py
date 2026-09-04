from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v768 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.8 integrated shiny path, based on generated v7.6.7h.
# Exact2 is CLOSED LOOP on Crystal's own FFA8 hJoyDown:
#   physical UP -> Crystal accepts UP on two consecutive RNG advances -> Pause
#   -> user releases UP while frozen -> natural Resume.
# The controller modifies no HID word, rJOYP result/address, GB RAM, RNG, DIV,
# DV or save data. The only actuator is Pause/Resume.

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

# Stop the expensive FFA2..FFA9 reads as soon as the controller has seen the
# first game-side clear after the physical-UP release. Until then sampling must
# remain live even if input polling is delayed, so there is no fixed-frame cap.
anchor = '''pub fn live_pass_telemetry() -> LivePassTelemetry {'''
insert = '''pub fn exact2_needs_joymap_sample() -> bool {
    unsafe {
        LIVE_PASS_ARMED
            && (LIVE_PASS.exact2_up_advances < 2
                || LIVE_PASS.exact2_release_confirmed == 0
                || LIVE_PASS.exact2_first_clear_advance == 0)
    }
}

'''
if h.count(anchor) != 1:
    raise SystemExit(f'v768 joy sample gate anchor count {h.count(anchor)}')
h = h.replace(anchor, insert + anchor, 1)
H.write_text(h)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# v767h already removed the old +22 stop. Make the FFA2..FFA9 observation
# dynamic: keep it only until Exact2 and the first post-release clear are proven.
t = rep(t,
'use super::hook::{live_pass_observe_joymap, live_pass_telemetry};',
'use super::hook::{exact2_needs_joymap_sample, live_pass_observe_joymap, live_pass_telemetry};',
'trace import')

old_obs = '''        // v7.6.7f: read-only JP VC Crystal joypad chain FFA2..FFA9.
        // These addresses were established by prior cold-boot physical-input traces.
        let joymap = [
            gb_mem::read_u8(0xffa2), gb_mem::read_u8(0xffa3),
            gb_mem::read_u8(0xffa4), gb_mem::read_u8(0xffa5),
            gb_mem::read_u8(0xffa6), gb_mem::read_u8(0xffa7),
            gb_mem::read_u8(0xffa8), gb_mem::read_u8(0xffa9),
        ];
        live_pass_observe_joymap(joymap, pnp::current_keys());'''
new_obs = '''        // v7.6.8: observe the JP joypad chain only while closed-loop Exact2
        // is unresolved, and through the first FFA8-clear after physical UP
        // release. No extra joypad reads remain in the J/POST/tail region.
        if exact2_needs_joymap_sample() {
            let joymap = [
                gb_mem::read_u8(0xffa2), gb_mem::read_u8(0xffa3),
                gb_mem::read_u8(0xffa4), gb_mem::read_u8(0xffa5),
                gb_mem::read_u8(0xffa6), gb_mem::read_u8(0xffa7),
                gb_mem::read_u8(0xffa8), gb_mem::read_u8(0xffa9),
            ];
            live_pass_observe_joymap(joymap, pnp::current_keys());
        }'''
t = rep(t, old_obs, new_obs, 'dynamic JP joy observation')

# At rel40, first validate that the physical-UP controller really produced two
# consecutive game-accepted UP advances and then a clean released state. Then
# use the existing actual-POST + actual-State/DIV inverse gate. Non-shiny runs
# stop immediately; a surviving shiny prediction continues naturally to DV.
old_rel40 = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                // v7.6.6 ends every diagnostic run at rel40 after recording the
                // actual POST/J/state/div and suffix-gate support.  This avoids a
                // 700-frame tail and makes each M replicate fast and comparable.
                self.practical_fail(13);return
'''
new_rel40 = '''                let lp=live_pass_telemetry();
                let exact2_ok = lp.exact2_up_advances == 2
                    && lp.exact2_pause_requested != 0
                    && lp.exact2_release_confirmed != 0
                    && lp.exact2_first_up_advance != 0
                    && lp.exact2_second_up_advance == lp.exact2_first_up_advance.wrapping_add(1)
                    && lp.exact2_first_clear_advance != 0;
                if !exact2_ok {
                    self.practical_fail(15);return
                }
                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                // v7.6.8: no shiny-compatible rel40 tail => abort now. A shiny
                // prediction is rebound to the actual POST and allowed to run
                // untouched through the existing 716/717, stop2 and native DV.
                if let Some(pred)=g.prediction {
                    self.rebind_practical_post_v690(pred,post.proto,post.rot40);
                } else {
                    self.practical_fail(14);return
                }
'''
t = rep(t, old_rel40, new_rel40, 'rel40 shiny continue gate')

# Final lineage. Keep the detailed existing CSV sections so one run gives
# input timing, early/J, POST, rel40 gate, endpoint and actual DV evidence.
t = t.replace('LIVEPASS,V767H,', 'INPUTLAB,V768,')
t = t.replace('LIVEPASSHOST,V767H,', 'INPUTHOST,V768,')
t = t.replace('JOYMAP,V767H,', 'JOYMAP,V768,')
t = t.replace('EXACT2,V767H,', 'EXACT2,V768,')
t = t.replace('JOYFRAME,V767H,', 'JOYFRAME,V768,')

# Operator-visible state: after the second accepted-UP advance the game is
# frozen and the only required action is to release UP.
anchor = '''    pub fn draw_rng_status(&self) {
        if self.practical_scan_enabled {'''
insert = '''    pub fn draw_rng_status(&self) {
        let lp = live_pass_telemetry();
        if self.probe_session && lp.exact2_pause_requested != 0 && lp.exact2_release_confirmed == 0 {
            pnp::println!("S768 EXACT2 ACCEPTED");
            pnp::println!("RELEASE UP");
            return;
        }
        if self.practical_scan_enabled {'''
t = rep(t, anchor, insert, 'Exact2 release UI')
t = t.replace('S766 PHASE PROBE SCAN', 'S768 SHINY INTEGRATED')
t = t.replace('THEN B -> RELEASE -> UP', 'THEN B -> RELEASE -> HOLD UP')
t = t.replace('B -> RELEASE -> UP', 'B -> RELEASE -> HOLD UP')

# Explain the two new fast-abort reasons on screen.
t = rep(t,
'''            } else if self.practical_miss == 13 {
                pnp::println!("WHY REL40 CAPTURE");
            } else {''',
'''            } else if self.practical_miss == 13 {
                pnp::println!("WHY REL40 CAPTURE");
            } else if self.practical_miss == 14 {
                pnp::println!("WHY REL40 NONSHINY");
            } else if self.practical_miss == 15 {
                pnp::println!("WHY INPUT NOT EXACT2");
            } else {''',
'failure labels')

T.write_text(t)
print('Applied v7.6.8: closed-loop FFA8 Exact2 + rel40 shiny gate + natural tail')
