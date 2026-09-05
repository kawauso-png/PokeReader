from pathlib import Path

ROOT = Path('.')
C = ROOT / '3gx/sources/main.c'
T = ROOT / 'reader_core/src/crystal/trace.rs'


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'v785 {label}: expected 1 match, got {n}')
    return text.replace(old, new, 1)


def replace_fn(src, sig, new):
    i = src.index(sig)
    brace = src.index('{', i)
    depth = 0
    j = brace
    while j < len(src):
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[:i] + new + src[j+1:]
        j += 1
    raise SystemExit(f'v785 function end not found: {sig}')

# C side: phase-lock the start of the live 16-mask + Exact2 pass window.
# M14 release/resume stays untouched.
c = C.read_text()

old_stage2 = '''            if (held & KEY_DUP)\n            {\n                if (!suicune_live_pass_ready)\n                {\n                    svcSleepThread(1000000);\n                    continue;\n                }\n                // v7.6.7d: no paused write-test. The only meaningful test is\n                // the hook-timed clear immediately before Crystal reads rJOYP.\n                suicune_wait_up_after_b = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                fixed_armed = false;\n                suicune_auto_resume_pending = false;\n                suicune_phase_lock_active = false;\n                suicune_start_phase_lock_active = false;\n                is_paused = false;\n                break;\n            }'''
new_stage2 = '''            if (held & KEY_DUP)\n            {\n                if (!suicune_live_pass_ready)\n                {\n                    svcSleepThread(1000000);\n                    continue;\n                }\n\n                // v7.8.5 SHINY PHASE PROBE.  The real-UP Exact2 mechanism is\n                // unchanged.  While still frozen, align the *release into* the\n                // live 16-mask + 2-pass path to one selected absolute host\n                // display-cycle slot.  No RNG/DIV/GB input value is written.\n                // UP may be held during this wait because the VC is still\n                // paused; once released, the existing live mask remains the\n                // authority until the two FFA4 polls are passed.\n                u64 now = svcGetSystemTick();\n                u32 wanted_start = suicune_start_phase_slot & 15U;\n                u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;\n                while (((u32)cycle & 15U) != wanted_start) cycle++;\n                u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                if (target <= now + 4096ULL)\n                {\n                    cycle += 16ULL;\n                    target = cycle * SUICUNE_PHASE_PERIOD_TICKS;\n                }\n                suicune_start_phase_lock_active = true;\n                suicune_start_phase_anchor_tick = now;\n                suicune_start_phase_target_tick = target;\n                while (svcGetSystemTick() < target) { }\n                suicune_start_phase_actual_tick = svcGetSystemTick();\n\n                // v7.6.7d: no paused write-test. The only meaningful test is\n                // the hook-timed clear immediately before Crystal reads rJOYP.\n                suicune_wait_up_after_b = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                fixed_armed = false;\n                suicune_auto_resume_pending = false;\n                suicune_phase_lock_active = false;\n                is_paused = false;\n                break;\n            }'''
c = replace_once(c, old_stage2, new_stage2, 'stage2 live-start phase lock')

old_selector = '''        // v7.4.2 full absolute resume selector.  Only active after the\n        // authoritative frozen A/r10 bucket root is READY, so Y+DOWN/Y+UP\n        // scan commands cannot collide with this control.  X=+1, Y=-1.\n        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            if (just_pressed & KEY_X)\n            {\n                suicune_phase_slot = (suicune_phase_slot + 1U) & 15U;\n                continue;\n            }\n            if (just_pressed & KEY_Y)\n            {\n                suicune_phase_slot = (suicune_phase_slot + 15U) & 15U;\n                continue;\n            }\n        }'''
new_selector = '''        // v7.8.5 start-slot selector.  Exact2 release/resume is deliberately\n        // fixed at M14 by v7.6.7j, so X/Y now select only the host cycle at\n        // which the live masked path begins.  This isolates the upstream\n        // transport-phase lever under test.\n        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            if (just_pressed & KEY_X)\n            {\n                suicune_start_phase_slot = (suicune_start_phase_slot + 1U) & 15U;\n                continue;\n            }\n            if (just_pressed & KEY_Y)\n            {\n                suicune_start_phase_slot = (suicune_start_phase_slot + 15U) & 15U;\n                continue;\n            }\n        }'''
c = replace_once(c, old_selector, new_selector, 'root-ready slot selector')

old_arm = '''            suicune_start_phase_slot = 0;\n            suicune_start_phase_lock_active = true;\n            suicune_start_phase_anchor_tick = 0;'''
new_arm = '''            // v7.8.5: preserve the user-selected live-start slot across B ARM.\n            suicune_start_phase_lock_active = true;\n            suicune_start_phase_anchor_tick = 0;'''
c = replace_once(c, old_arm, new_arm, 'preserve selected start slot')

# v7.8.5 audit fix: two legacy v7.4.x paths still forced START back to M0.
# They are not authoritative for the current FFA4 Exact2 route, but leaving
# them in place makes Y=-1 selection silently collapse to M0 on the next HID
# poll and can also mis-label any legacy fixed-run diagnostics.
old_legacy_start = '''                    const u32 wanted_start_cycle = 0U;'''
new_legacy_start = '''                    const u32 wanted_start_cycle = suicune_start_phase_slot & 15U;'''
c = replace_once(c, old_legacy_start, new_legacy_start, 'legacy selected start cycle')

old_legacy_overwrite = '''                    suicune_start_phase_slot = wanted_start_cycle;
                    suicune_start_phase_anchor_tick = target;
                    suicune_start_phase_target_tick = target;'''
new_legacy_overwrite = '''                    suicune_start_phase_anchor_tick = now;
                    suicune_start_phase_target_tick = target;'''
c = replace_once(c, old_legacy_overwrite, new_legacy_overwrite, 'legacy start telemetry without slot overwrite')

old_y_reset = '''            // v7.4.1: START phase is not user-selectable during the sweep.
            // It is always absolute host cycle mod16 == 0.
            suicune_start_phase_slot = 0;
'''
new_y_reset = '''            // v7.8.5: START phase selection persists until changed at ROOT READY.
'''
c = replace_once(c, old_y_reset, new_y_reset, 'remove stale Y-block M0 reset')

C.write_text(c)

# Rust side: replace model-based shiny root selector with a controlled A/r10,
# bucket76 phase-probe root. Lane 252 is reserved for this diagnostic build.
t = T.read_text()

new_monitor = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        // v7.8.5 SHINY-CAPABLE PHASE PROBE.
        // Do not select roots by the stale v7.8.4 donor/shiny model.  For a
        // transport experiment, hold PRE class and bucket constant and vary
        // only the host live-start slot.  A/r10 bucket76 is the modern M14
        // comparison condition.  Lane 252 means PHASE PROBE, never a shiny
        // prediction.
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid
        { return; }

        let cur = rng_advance();
        let da = cur.wrapping_sub(self.practical_live_last_advance);
        if da == 0 { return; }
        self.practical_live_last_advance = cur;
        self.practical_live_checked = self.practical_live_checked.saturating_add(1);

        let r = latest_pre_vblank_ring();
        let n = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n != PRE_VBLANK_RING_LEN { return; }
        let (last, _) = pre_ring_sample(&r, n - 1);
        let lag = cur.wrapping_sub(last);
        let (proto0, mut rot, best, second, ok) = classify_pre_ring(&r);
        self.phase_best_score = best;
        self.phase_second_score = second;
        self.phase_consecutive = ok;
        self.phase_now_proto = proto0;
        self.phase_now_rot = rot;
        self.phase_now_lag = lag.min(255) as u8;
        if lag == 1 { rot = rot.wrapping_add(1) & 15; }
        if lag != 0 || !ok || best != 0 { return; }
        self.phase_exact_count = self.phase_exact_count.saturating_add(1);
        self.phase_now_rot = rot;
        if proto0 != b'A' || rot != 10 { return; }

        let (_, p0) = pre_ring_sample(&r, 0);
        let pd = p0.wrapping_sub(0x0035) & 0x3fff;
        if (pd & 0x003f) != 0 { return; }
        let bucket = ((pd >> 6) & 0xff) as u8;
        if bucket != 76 { return; }

        self.phase_target_proto = b'A';
        self.phase_target_rot = 10;
        self.bucket_model_active = true;
        self.bucket_current = 76;
        self.bucket_anchor = 76;
        self.bucket_distance = 0;
        self.bucket_radius = 0;
        self.bucket_expected_post_proto = 0;
        self.bucket_expected_post_rot = 0;

        self.practical_target = cur;
        self.practical_live_found_advance = cur;
        self.practical_live_found_state = reader.rng_state();
        self.practical_live_found_div = measured_div();
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = add_div_tracker().index().unwrap_or(0) as u32 & 0x3fff;
        self.practical_live_found_si = sub_div_tracker().index().unwrap_or(0) as u32 & 0x3fff;
        self.practical_live_found_lane = 252;
        self.practical_candidate_valid = false;
        self.practical_scan_enabled = false;
        self.practical_live_scan = false;
        self.practical_miss = 0;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }'''
t = replace_fn(t, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)', new_monitor)

new_control = r'''    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {
        let phase_probe = self.practical_live_found_lane == 252 && !self.probe_session;
        let shiny_model = self.practical_live_found_lane == 253
            && self.practical_candidate_valid && !self.probe_session;
        let mut out = 0u32;
        if phase_probe || shiny_model { out |= 1u32 << 31; }

        let r = latest_pre_vblank_ring();
        let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        let (proto, rot, best, second, consecutive) = classify_pre_ring(&r);
        self.phase_now_proto = proto;
        self.phase_now_rot = rot;
        self.phase_best_score = best;
        self.phase_second_score = second;
        self.phase_consecutive = consecutive;
        let cur = rng_advance();

        // Legacy/model lane keeps its exact target semantics. Phase-probe lane
        // deliberately does not: if asynchronous AutoPause moved us off the
        // scanned cell, neutral root-lock stepping continues until the next
        // authoritative A/r10 bucket76 cell is frozen.
        if shiny_model && cur > self.practical_target {
            self.practical_miss = 8;
            out |= 1u32 << 26;
            return out;
        }

        if count == PRE_VBLANK_RING_LEN && consecutive && best == 0 {
            out |= 1u32 << 29;
            out |= proto as u32;
            out |= (rot as u32) << 8;

            let mut bucket_valid = false;
            let mut bucket = 0u8;
            if proto == b'A' && rot == 10 {
                let (_, p0) = pre_ring_sample(&r, 0);
                let pd = p0.wrapping_sub(0x0035) & 0x3fff;
                if (pd & 0x003f) == 0 {
                    bucket_valid = true;
                    bucket = ((pd >> 6) & 0xff) as u8;
                    out |= 1u32 << 28;
                    out |= (bucket as u32) << 12;
                }
            }

            let phase_ready = phase_probe && proto == b'A' && rot == 10
                && bucket_valid && bucket == 76;
            let model_bucket_ok = if self.bucket_model_active {
                bucket_valid && bucket == self.bucket_current
            } else { true };
            let model_ready = shiny_model && cur == self.practical_target
                && proto == self.phase_target_proto && rot == self.phase_target_rot
                && model_bucket_ok;

            if phase_ready || model_ready {
                self.phase_target_proto = proto;
                self.phase_target_rot = rot;
                self.bucket_model_active = phase_probe || self.bucket_model_active;
                if phase_probe {
                    self.bucket_current = 76;
                    self.practical_target = cur;
                    self.practical_live_found_advance = cur;
                }
                self.practical_live_found_state = reader.rng_state();
                self.practical_live_found_div = measured_div();
                self.practical_live_found_tick = pnp::system_tick();
                self.practical_live_found_ai = add_div_tracker().index().unwrap_or(0) as u32 & 0x3fff;
                self.practical_live_found_si = sub_div_tracker().index().unwrap_or(0) as u32 & 0x3fff;
                out |= 1u32 << 27;
            }
        }
        out
    }'''
t = replace_fn(t, '    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32', new_control)

t = t.replace('pnp::println!("S784 MULTI-PRE SHINY SCAN");',
              'pnp::println!("S785 PHASE SCAN A/r10 B76");')

needle = '''        } else if self.practical_live_found_lane == 253 && !self.probe_session {'''
insert = '''        } else if self.practical_live_found_lane == 252 && !self.probe_session {
            let sp = pnp::start_phase_metrics();
            pnp::println!("S785 PHASE ROOT READY");
            pnp::println!("A/r10 B76 S{:04X} D{:04X}",self.practical_live_found_state,self.practical_live_found_div);
            pnp::println!("START M{:02} X+1 Y-1",sp.slot & 15);
            pnp::println!("RESUME M14 FIXED");
            pnp::println!("B ARM -> RELEASE -> HOLD UP");
        } else if self.practical_live_found_lane == 253 && !self.probe_session {'''
t = replace_once(t, needle, insert, 'lane252 UI')

probe_insert_at = '''        let lp = live_pass_telemetry();'''
probe_summary = r'''        if self.practical_live_found_lane == 252 {
            let sp = pnp::start_phase_metrics();
            let rp = pnp::resume_phase_metrics();
            let start_mod = if sp.period != 0 { ((sp.actual / sp.period) & 15) as u32 } else { 255 };
            let resume_mod = if rp.period != 0 { ((rp.actual / rp.period) & 15) as u32 } else { 255 };
            let start_err = sp.actual as i128 - sp.target as i128;
            let raw = self.probe_result.map(|x| x.raw_dv).unwrap_or(0);
            let route = self.probe_result.map(|x| x.route).unwrap_or(0);
            line.clear();
            let _ = write!(line,
                "\nphase_probe785,version,root_advance,root_state,root_div,bucket,start_slot,start_actual_mod16,start_error_ticks,resume_slot,resume_actual_mod16,j_a,j_s,post_proto,post_rot,route,raw_dv\nPHASEPROBE,V785,{},{:04X},{:04X},{},{},{},{},{},{},{},{},{},{},{},{:04X}\n",
                self.practical_live_found_advance,self.practical_live_found_state,self.practical_live_found_div,
                self.bucket_current,sp.slot&15,start_mod,start_err,rp.slot&15,resume_mod,
                self.early_j_a,self.early_j_s,
                if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,
                route,raw);
            pnp::trace_file_write(line.as_bytes());
        }

        let lp = live_pass_telemetry();'''
t = replace_once(t, probe_insert_at, probe_summary, 'phase probe CSV summary')

T.write_text(t)
print('v7.8.5 phase probe patch applied')
