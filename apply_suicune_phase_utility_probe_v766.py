from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

start = t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
end = t.index('\n    fn practical_fail(&mut self, code: u8) {', start)
new_fn = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        // v7.6.6 PHASE UTILITY PROBE
        // Diagnostic only: stop on the first exact lag0 A/r10 with bucket 76.
        // No shiny prediction is consulted before the press.  The purpose is to
        // measure whether controlled absolute Resume M reduces PRE->POST entropy.
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid
        {
            return;
        }
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
        self.bucket_current = bucket;
        if bucket != 76 { return; }

        // Saved root indices are needed only as rel40 fallback if the live
        // trackers are temporarily unavailable after Exact2F.
        let Some(ai0) = add_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let Some(si0) = sub_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let ai = (ai0 as u32) & 0x3fff;
        let si = (si0 as u32) & 0x3fff;

        self.phase_target_proto = b'A';
        self.phase_target_rot = 10;
        self.bucket_model_active = true;
        self.bucket_current = 76;
        self.bucket_anchor = 76;
        self.bucket_distance = 0;
        self.bucket_expected_post_proto = 0;
        self.bucket_expected_post_rot = 0;
        self.multipre_score = 0;
        self.multipre_branches = 0;

        self.practical_live_found_advance = cur;
        self.practical_live_found_state = reader.rng_state();
        self.practical_live_found_div = measured_div();
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = ai;
        self.practical_live_found_si = si;

        // A default Prediction is a transport token only.  v7.6.6 never uses
        // its expected POST/DV; rel40 is classified from the actual trace.
        self.bind_practical_prediction(practical::Prediction::default());
        self.practical_live_found_lane = 253;
        self.practical_empirical = false;
        self.practical_live_scan = false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }
'''
t = t[:start] + new_fn + t[end:]

old_gate = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);\n                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;\n                if g.evaluated==0{self.practical_fail(11);return}\n                if let Some(x)=g.prediction{\n                    self.practical_empirical=x.lane_id>=101&&x.lane_id<200;\n                    self.bucket_model_active=x.lane_id>=200;\n                    self.rebind_practical_post_v690(x,post.proto,post.rot40);\n                    return\n                }\n                self.practical_fail(10);return\n'''
new_gate = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);\n                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;\n                // v7.6.6 ends every diagnostic run at rel40 after recording the\n                // actual POST/J/state/div and suffix-gate support.  This avoids a\n                // 700-frame tail and makes each M replicate fast and comparable.\n                self.practical_fail(13);return\n'''
if old_gate not in t:
    raise SystemExit('v766 rel40 gate anchor missing')
t = t.replace(old_gate, new_gate, 1)

# Telemetry: add one compact marker; existing RPH/MAP/POSTFP/REL40GATE rows carry the details.
old_csv = '''        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();\n'''
new_csv = '''        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _=write!(line,"\\nphase_utility,version,pre_proto,pre_rot,bucket,target_advance,state,div,post_proto,post_rot,state40,div40,gate_models,gate_eval,gate_shiny,miss\\nPHASEUTILITY,V766,{},{},{},{},{:04X},{:04X},{},{},{:04X},{:04X},{},{},{},{}\\n",\n            self.phase_target_proto as char,self.phase_target_rot,self.bucket_current,self.practical_target,\n            self.practical_live_found_state,self.practical_live_found_div,\n            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,\n            self.v763_rel40_state,self.v763_rel40_div,self.v763_gate_models,self.v763_gate_evaluated,self.v763_gate_shiny_models,self.practical_miss);\n        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();\n'''
# Use the last matching close sequence in save(), not an unrelated function.
pos = t.rfind(old_csv)
if pos < 0:
    raise SystemExit('v766 csv close anchor missing')
t = t[:pos] + t[pos:].replace(old_csv, new_csv, 1)

# UI: rename the scan/lock/rel40 completion path and show selected absolute Resume M.
t = t.replace('pnp::println!("S763 PRE-HINT SCAN");', 'pnp::println!("S766 PHASE PROBE SCAN");', 1)
t = t.replace('pnp::println!("Y+DOWN START 9 CELLS");', 'pnp::println!("Y+DOWN -> A/r10 B76");', 1)

old_lane = '''            if self.practical_miss==10 {\n                pnp::println!("S763 REL40 NOT SHINY");'''
new_lane = '''            if self.practical_miss==13 {\n                pnp::println!("S766 REL40 CAPTURED");\n                pnp::println!("P{}/r{} S{:04X}",self.practical_post_proto as char,self.practical_post_rot,self.v763_rel40_state);\n                pnp::println!("D{:04X} M{} E{}",self.v763_rel40_div,self.v763_gate_models,self.v763_gate_evaluated);\n                pnp::println!("SAVE OK - RESET VC");\n            } else if self.practical_miss==10 {\n                pnp::println!("S763 REL40 NOT SHINY");'''
if old_lane not in t:
    raise SystemExit('v766 lane UI anchor missing')
t = t.replace(old_lane, new_lane, 1)

old_ready = '''            } else if self.practical_candidate_valid {\n                pnp::println!("S763 PRE HINT LOCK");\n                pnp::println!("PRE {}/r{} BR{}",self.phase_target_proto as char,self.phase_target_rot,self.multipre_branches);\n                pnp::println!("RANK {} T{}",self.multipre_score,self.practical_target);\n                pnp::println!("H{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");\n'''
new_ready = '''            } else if self.practical_candidate_valid {\n                pnp::println!("S766 A/r10 B76 LOCK");\n                pnp::println!("T{} S{:04X} D{:04X}",self.practical_target,self.practical_live_found_state,self.practical_live_found_div);\n                pnp::println!("RESUME M{:02} X+1 Y-1",pnp::fixed_a_frame().phase_slot & 15);\n                pnp::println!("B -> RELEASE -> UP");\n'''
if old_ready not in t:
    raise SystemExit('v766 ready UI anchor missing')
t = t.replace(old_ready, new_ready, 1)

t = t.replace('pnp::println!("S764 RESET RECOMMENDED");', 'pnp::println!("S766 RESET RECOMMENDED");', 1)
t = t.replace('''            } else if self.practical_miss == 12 {\n                pnp::println!("WHY REL40 CLASS");\n            } else {''', '''            } else if self.practical_miss == 12 {\n                pnp::println!("WHY REL40 CLASS");\n            } else if self.practical_miss == 13 {\n                pnp::println!("WHY REL40 CAPTURE");\n            } else {''', 1)

T.write_text(t)

C = Path('3gx/sources/main.c')
c = C.read_text()
# Active Stage3 scan start defaults to M0 in the diagnostic build; after lock,
# X selects M1 and Y selects M14 in a single press each.
old = '''                suicune_phase_slot = 8;\n                search_suicune_practical_targets();'''
new = '''                suicune_phase_slot = 0; // v7.6.6 diagnostic default: absolute Resume M0\n                search_suicune_practical_targets();'''
if old not in c:
    raise SystemExit('v766 C scan default anchor missing')
c = c.replace(old, new, 1)
C.write_text(c)

print('Applied v7.6.6 phase utility probe: A/r10 bucket76, absolute M selector, stop at rel40')
