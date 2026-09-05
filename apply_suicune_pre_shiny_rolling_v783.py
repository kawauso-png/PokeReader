from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v783 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


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
    raise SystemExit(f'v783 function end not found: {sig}')

P = Path('reader_core/src/crystal/practical.rs')
T = Path('reader_core/src/crystal/trace.rs')
p = P.read_text()
t = T.read_text()

# v7.8.3 PRE Shiny Rolling Search
#
# v7.8.2 still paused on every exact A/r10 bucket76 root, so it reduced only
# waiting time after the physical press.  v7.8.3 restores the inverse shiny
# selector as a PRE *candidate screen*: the game is allowed to run naturally
# while 3GX observes roots; only a root whose finite historical hypotheses can
# connect to a shiny raw causes AutoPause.
#
# This PRE screen is intentionally NOT authoritative.  It may produce false
# positives because PRE->tail transport is not deterministic.  The actual
# rel40 impossible-phase gate and v7.8.1 DV-2 exact-tail gate remain authoritative
# hard-negative filters.  No RNG/DIV/DV/input memory is written.

# The inverse weighted evaluator previously required score >=12.  For bucket76
# the score is a ranking/support quantity, not a physical probability.  A single
# observed minor deep profile contributes ~6 support points.  Accept it as a
# coarse rolling candidate; later exact gates decide whether the run survives.
p = rep(
    p,
    'let score=((sw.saturating_mul(100)+total/2)/total).min(100)as u8;if score<12{return None}',
    'let score=((sw.saturating_mul(100)+total/2)/total).min(100)as u8;if score<6{return None}',
    'inverse PRE support threshold 12 -> 6',
)
P.write_text(p)

new_monitor = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        // v7.8.3 PRE SHINY ROLLING SEARCH.
        // Observe natural roots continuously and pause only when the current
        // exact A/r10 bucket76 root passes the inverse shiny candidate screen.
        // The PRE score is ranking/support only; rel40 + DV-2 remain authority.
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

        // Keep the validated physical-flow root class for this first production
        // rolling build.  Other A/r10 buckets can be added later without
        // changing the authoritative downstream gates.
        if bucket != 76 { return; }

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
        let Some(bp) = practical::evaluate_weighted_bucket_inverse(
            bucket, reader.rng_state(), measured_div(), ai, si
        ) else {
            // No shiny connection under the PRE hypothesis union: keep scanning
            // naturally.  Nothing is paused and no user action is required.
            return;
        };

        self.phase_target_proto = b'A';
        self.phase_target_rot = 10;
        self.bucket_model_active = true;
        self.bucket_current = bucket;
        self.bucket_anchor = bp.anchor;
        self.bucket_distance = bp.distance;
        self.bucket_radius = bp.radius;
        self.bucket_expected_post_proto = bp.post_proto;
        self.bucket_expected_post_rot = bp.post_rot;
        self.multipre_score = bp.prediction.support_weight;
        self.multipre_branches = bp.prediction.shiny_mask.count_ones().min(255) as u8;

        self.practical_live_found_advance = cur;
        self.practical_live_found_state = reader.rng_state();
        self.practical_live_found_div = measured_div();
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = ai;
        self.practical_live_found_si = si;

        self.bind_practical_prediction(bp.prediction);
        self.practical_live_found_lane = 253;
        self.practical_empirical = false;
        self.practical_empirical_candidates = self.practical_empirical_candidates.saturating_add(1);
        self.practical_live_scan = false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }'''

t = replace_fn(t, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)', new_monitor)

# Make the locked-root UI explicit: the user should only ever see the press
# prompt after the PRE shiny screen has passed.
old_ui = '''            } else if self.practical_candidate_valid {
                pnp::println!("S766 A/r10 B76 LOCK");
                pnp::println!("T{} S{:04X} D{:04X}",self.practical_target,self.practical_live_found_state,self.practical_live_found_div);
                pnp::println!("RESUME M{:02} X+1 Y-1",pnp::fixed_a_frame().phase_slot & 15);
                pnp::println!("B -> RELEASE -> UP");
            } else {
                pnp::println!("S762 LOCK WAIT");
            }
'''
new_ui = '''            } else if self.practical_candidate_valid {
                pnp::println!("S783 PRE SHINY CAND");
                pnp::println!("W{} M{:02X} DV{:04X}",self.practical_support,self.practical_mask,self.practical_raw);
                pnp::println!("T{} B{} POST {}/r{}",self.practical_target,self.bucket_current,
                    if self.bucket_expected_post_proto==0{'?'}else{self.bucket_expected_post_proto as char},self.bucket_expected_post_rot);
                pnp::println!("B -> RELEASE -> UP");
            } else {
                pnp::println!("S783 PRE SHINY SCAN");
                pnp::println!("ROOT {} A10 {}",self.practical_live_checked,self.practical_empirical_eval);
                pnp::println!("AUTO WAIT - NO INPUT");
            }
'''
t = rep(t, old_ui, new_ui, 'rolling UI')

# Version tag for the top-level status where available.
t = t.replace('V782', 'V783', 1) if 'V782' in t else t
T.write_text(t)

print('Applied v7.8.3 PRE Shiny Rolling Search: A/r10 B76 inverse candidate scan + rel40/tail authority retained')
