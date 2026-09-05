from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

def replace_fn(src, sig, new):
    i = src.index(sig)
    brace = src.index('{', i)
    depth = 0
    j = brace
    while j < len(src):
        if src[j] == '{': depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[:i] + new + src[j+1:]
        j += 1
    raise SystemExit(f'v784 function end not found: {sig}')

new_monitor = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        // v7.8.4 MULTI-PRE SHINY ROLLING SEARCH.
        // Observe every exact PRE cell already represented by either a full
        // historical donor lane or an empirical lane.  Only roots for which
        // the inverse finite-hypothesis model reaches a Gen-II shiny raw cause
        // AutoPause.  No future RNG/DIV state is written or synthesized.
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

        if !practical::multipre_supported(proto0, rot) { return; }

        // Bucket models are an A/r10-only refinement. Other PRE cells still use
        // their exact/empirical donor lanes through evaluate_multi_pre_inverse.
        let mut bucket_opt: Option<u8> = None;
        if proto0 == b'A' && rot == 10 {
            let (_, p0) = pre_ring_sample(&r, 0);
            let pd = p0.wrapping_sub(0x0035) & 0x3fff;
            if (pd & 0x003f) == 0 {
                let b = ((pd >> 6) & 0xff) as u8;
                self.bucket_current = b;
                bucket_opt = Some(b);
            }
        }

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

        self.practical_empirical_eval = self.practical_empirical_eval.saturating_add(1);
        let Some(mp) = practical::evaluate_multi_pre_inverse(
            proto0, rot, bucket_opt, reader.rng_state(), measured_div(), ai, si
        ) else {
            return;
        };

        self.phase_target_proto = proto0;
        self.phase_target_rot = rot;
        self.multipre_score = mp.score;
        self.multipre_branches = mp.branches;
        self.bucket_model_active = mp.bucket_model;
        if mp.bucket_model {
            self.bucket_current = mp.bucket;
            self.bucket_anchor = mp.anchor;
            self.bucket_distance = mp.distance;
            self.bucket_radius = 16;
            self.bucket_expected_post_proto = mp.post_proto;
            self.bucket_expected_post_rot = mp.post_rot;
        } else {
            self.bucket_anchor = 0;
            self.bucket_distance = 0xff;
            self.bucket_radius = 0;
            self.bucket_expected_post_proto = mp.post_proto;
            self.bucket_expected_post_rot = mp.post_rot;
        }

        self.practical_live_found_advance = cur;
        self.practical_live_found_state = reader.rng_state();
        self.practical_live_found_div = measured_div();
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = ai;
        self.practical_live_found_si = si;

        self.bind_practical_prediction(mp.prediction);
        self.practical_live_found_lane = 253;
        self.practical_empirical = mp.empirical;
        self.practical_empirical_candidates = self.practical_empirical_candidates.saturating_add(1);
        self.practical_live_scan = false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }'''

t = replace_fn(t, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)', new_monitor)

old_gate = '''                if !v782_rel40_any_shiny_phase(rel40_ap4) {
                    self.practical_miss = 15;'''
new_gate = '''                // v7.8.4: the rel40 phase delta bands were calibrated on the
                // modern A/r10 physical-flow corpus.  For newly-enabled PRE cells,
                // fail open here and let the PRE-agnostic DV-2 exact tail gate decide.
                if self.phase_target_proto == b'A' && self.phase_target_rot == 10
                    && !v782_rel40_any_shiny_phase(rel40_ap4) {
                    self.practical_miss = 15;'''
if old_gate not in t:
    raise SystemExit('v784 rel40 gate anchor missing')
t = t.replace(old_gate, new_gate, 1)

old_scan = '''        if self.practical_scan_enabled {
            pnp::println!("S766 PHASE PROBE SCAN");
            pnp::println!("ADV{} ROOT{}",rng_advance(),self.practical_live_checked);
            if self.phase_now_proto==b'?' {pnp::println!("PRE ?");} else if self.phase_now_proto==b'A'&&self.phase_now_rot==10 {pnp::println!("PRE A/r10 B{}",self.bucket_current);} else {pnp::println!("PRE {}/r{}",self.phase_now_proto as char,self.phase_now_rot);}
            pnp::println!("Y+DOWN -> A/r10 B76");
'''
new_scan = '''        if self.practical_scan_enabled {
            pnp::println!("S784 MULTI-PRE SHINY SCAN");
            pnp::println!("ADV{} ROOT{}",rng_advance(),self.practical_live_checked);
            if self.phase_now_proto==b'?' {pnp::println!("PRE ?");}
            else {pnp::println!("PRE {}/r{}{}",self.phase_now_proto as char,self.phase_now_rot,
                if practical::multipre_supported(self.phase_now_proto,self.phase_now_rot){" *"}else{""});}
            pnp::println!("AUTO WAIT - NO INPUT");
'''
if old_scan not in t:
    raise SystemExit('v784 scan UI anchor missing')
t = t.replace(old_scan, new_scan, 1)

old_cand = '''            } else if self.practical_candidate_valid {
                pnp::println!("S783 PRE SHINY CAND");
                pnp::println!("W{} M{:02X} DV{:04X}",self.practical_support,self.practical_mask,self.practical_raw);
                pnp::println!("T{} B{} A{} D{}",self.practical_target,self.bucket_current,self.bucket_anchor,self.bucket_distance);
                pnp::println!("B -> RELEASE -> UP");
'''
new_cand = '''            } else if self.practical_candidate_valid {
                pnp::println!("S784 MULTI-PRE CAND");
                pnp::println!("PRE {}/r{} R{} W{}",self.phase_target_proto as char,self.phase_target_rot,self.multipre_branches,self.multipre_score);
                pnp::println!("DV{:04X} POST {}/r{}",self.practical_raw,
                    if self.bucket_expected_post_proto==0{'?'}else{self.bucket_expected_post_proto as char},self.bucket_expected_post_rot);
                if self.bucket_model_active {pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);}
                else {pnp::println!("T{}",self.practical_target);}
                pnp::println!("B -> RELEASE -> UP");
'''
if old_cand not in t:
    raise SystemExit('v784 candidate UI anchor missing')
t = t.replace(old_cand, new_cand, 1)

old_wait = '''            } else {
                pnp::println!("S783 PRE SHINY SCAN");
                pnp::println!("ROOT {} A10 {}",self.practical_live_checked,self.practical_empirical_eval);
                pnp::println!("AUTO WAIT - NO INPUT");
            }
'''
new_wait = '''            } else {
                pnp::println!("S784 MULTI-PRE SHINY SCAN");
                pnp::println!("ROOT {} EVAL {}",self.practical_live_checked,self.practical_empirical_eval);
                pnp::println!("AUTO WAIT - NO INPUT");
            }
'''
if old_wait not in t:
    raise SystemExit('v784 wait UI anchor missing')
t = t.replace(old_wait, new_wait, 1)

T.write_text(t)
print('Applied v7.8.4 Multi-PRE Rolling: 9 supported PRE cells + A/r10-only rel40 phase hard-negative + exact tail authority')
