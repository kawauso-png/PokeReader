from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v781 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# 1) Conservative straddle repair. Keep every normal score=0 classification
# byte-for-byte equivalent. Only when the old L1 metric is imperfect do we
# accept a repair, and only when exactly one proto/rotation can be made exact
# by one adjacent-pair merge or by dropping one window edge.
old = '''    out.valid = true;\n    out.proto = b'A' + best_proto as u8;\n    // Canonical rotation is reported at rel40, matching the old rel40..55\n    // classifier and existing Factor/Prototype notes.\n    out.rot40 = ((best_rot28 + 12) & 15) as u8;\n    out.best_score = best_score.min(0xffff) as u16;\n    out.second_score = second_score.min(0xffff) as u16;\n    out\n}\n'''
new = '''    // v7.8.1: the live 13-sample window can straddle one emulator-frame\n    // boundary.  Preserve the strict classifier whenever it is already exact.\n    // For a nonzero best only, try three exact-preserving repairs:\n    //   * merge one adjacent observed/expected delta pair,\n    //   * drop the first delta,\n    //   * drop the last delta.\n    // Historical POSTFP regression: all 7 imperfect windows are uniquely\n    // repaired to their true cell while all 57 strict score=0 windows bypass\n    // this fallback completely.\n    if best_score != 0 {\n        let mut repaired_count = 0u8;\n        let mut repaired_proto = 0usize;\n        let mut repaired_rot28 = 0usize;\n        for proto in 0..PRE_FP_PROTOS.len() {\n            for rot28 in 0..16usize {\n                let mut exact = false;\n\n                let mut drop_head = 0u32;\n                for i in 1..12usize {\n                    let d = out.deltas[i] as i32\n                        - PRE_FP_PROTOS[proto][(rot28 + i) & 15] as i32;\n                    drop_head = drop_head.saturating_add(if d < 0 { (-d) as u32 } else { d as u32 });\n                }\n                if drop_head == 0 { exact = true; }\n\n                let mut drop_tail = 0u32;\n                for i in 0..11usize {\n                    let d = out.deltas[i] as i32\n                        - PRE_FP_PROTOS[proto][(rot28 + i) & 15] as i32;\n                    drop_tail = drop_tail.saturating_add(if d < 0 { (-d) as u32 } else { d as u32 });\n                }\n                if drop_tail == 0 { exact = true; }\n\n                if !exact {\n                    for merge in 0..11usize {\n                        let mut score = 0u32;\n                        let observed_pair = out.deltas[merge] as i32\n                            + out.deltas[merge + 1] as i32;\n                        let expected_pair = PRE_FP_PROTOS[proto][(rot28 + merge) & 15] as i32\n                            + PRE_FP_PROTOS[proto][(rot28 + merge + 1) & 15] as i32;\n                        let pd = observed_pair - expected_pair;\n                        score = score.saturating_add(if pd < 0 { (-pd) as u32 } else { pd as u32 });\n                        for i in 0..12usize {\n                            if i == merge || i == merge + 1 { continue; }\n                            let d = out.deltas[i] as i32\n                                - PRE_FP_PROTOS[proto][(rot28 + i) & 15] as i32;\n                            score = score.saturating_add(if d < 0 { (-d) as u32 } else { d as u32 });\n                        }\n                        if score == 0 { exact = true; break; }\n                    }\n                }\n\n                if exact {\n                    repaired_count = repaired_count.saturating_add(1);\n                    repaired_proto = proto;\n                    repaired_rot28 = rot28;\n                }\n            }\n        }\n        if repaired_count == 1 {\n            best_score = 0;\n            best_proto = repaired_proto;\n            best_rot28 = repaired_rot28;\n        }\n    }\n\n    out.valid = true;\n    out.proto = b'A' + best_proto as u8;\n    // Canonical rotation is reported at rel40, matching the old rel40..55\n    // classifier and existing Factor/Prototype notes.\n    out.rot40 = ((best_rot28 + 12) & 15) as u8;\n    out.best_score = best_score.min(0xffff) as u16;\n    out.second_score = second_score.min(0xffff) as u16;\n    out\n}\n'''
t = rep(t, old, new, 'straddle fallback')

# 2) Exact DV-2 endpoint classifier + finite deep candidate generator.
marker = '''/// Small stack formatter so a CSV row can be built without allocating.\n'''
insert = r'''
// v7.8.1 endpoint exact-tail gate.
//
// The endpoint snapshot is stop2+11 = DV-2.  Long-range rel40 extrapolation is
// deliberately not used here.  Instead, the last 11 unique advancing frames
// re-lock the local A/B/C/D prototype and rotation; the next two AP4 values are
// then deterministic on every compatible historical trace tested (55/55).
// From the predicted DV-frame state/AP4, enumerate the finite observed deep
// route3/route4 profile library.  The union covered the actual raw DV in 55/55
// compatible historical traces.  Invalid/ambiguous classification always
// fails open; only a valid finite union with zero shiny raws can abort.
#[derive(Clone, Copy)]
struct ExactTailEval {
    valid: bool,
    proto: u8,
    next_rot: u8,
    score: u16,
    second_score: u16,
    dv_ap4: u16,
    candidate_count: u8,
    shiny_count: u8,
    first_shiny: u16,
}

impl ExactTailEval {
    const EMPTY: Self = Self {
        valid: false, proto: b'?', next_rot: 0, score: 0xffff,
        second_score: 0xffff, dv_ap4: 0, candidate_count: 0,
        shiny_count: 0, first_shiny: 0,
    };
}

const R3_A_EXACT: [[u8; 3]; 5] = [
    [183,189,191], [183,188,190], [184,190,192], [184,189,191], [182,188,190],
];
const R3_S_EXACT: [[u8; 3]; 7] = [
    [183,189,191], [183,188,190], [184,190,192], [184,189,191],
    [183,188,191], [184,189,192], [184,191,192],
];
const R4_A_EXACT: [[u8; 4]; 3] = [
    [183,185,190,192], [184,186,191,193], [184,186,192,194],
];
const R4_S_EXACT: [[u8; 4]; 6] = [
    [183,185,190,193], [184,186,192,194], [184,186,191,194],
    [184,187,192,194], [184,186,190,193], [183,185,191,193],
];

#[inline]
fn exact_tail_step(state: u16, hi: u8, lo: u8) -> u16 {
    let add = (state >> 8) as u8;
    let sub = state as u8;
    let (next_add, carry) = add.overflowing_add(hi);
    let next_sub = sub.wrapping_sub(lo).wrapping_sub(carry as u8);
    ((next_add as u16) << 8) | next_sub as u16
}

#[inline]
fn exact_tail_normal_step(state: u16, ap4: u16) -> u16 {
    let hi = ((ap4 >> 6) & 0xff) as u8;
    let lo = (((ap4.wrapping_add(11)) >> 6) & 0xff) as u8;
    exact_tail_step(state, hi, lo)
}

#[inline]
fn exact_tail_is_shiny(raw: u16) -> bool {
    matches!(raw, 0x2aaa | 0x3aaa | 0x6aaa | 0x7aaa | 0xaaaa | 0xbaaa | 0xeaaa | 0xfaaa)
}

#[inline]
fn exact_tail_push_candidate(
    candidates: &mut [u16; 64], count: &mut usize, raw: u16,
    shiny_count: &mut u8, first_shiny: &mut u16,
) {
    for i in 0..*count {
        if candidates[i] == raw { return; }
    }
    if *count >= candidates.len() { return; }
    candidates[*count] = raw;
    *count += 1;
    if exact_tail_is_shiny(raw) {
        *shiny_count = shiny_count.saturating_add(1);
        if *first_shiny == 0 { *first_shiny = raw; }
    }
}

fn exact_tail_eval(
    entries: &[TraceEntry], len: usize, capture_advance: u32,
    capture_state: u16, capture_ap4: u16,
) -> ExactTailEval {
    let mut out = ExactTailEval::EMPTY;
    if len == 0 || capture_advance == 0 { return out; }

    // Reverse-collapse repeated advances, keeping the latest row for each
    // advance, then require 11 consecutive advancing samples ending exactly
    // at the endpoint capture.
    let mut seq = [TraceEntry::EMPTY; 11];
    let mut got = 0usize;
    let mut previous_advance = 0u32;
    let mut have_previous = false;
    let mut i = len;
    while i > 0 && got < 11 {
        i -= 1;
        let e = entries[i];
        if e.advance > capture_advance { continue; }
        if have_previous && e.advance == previous_advance { continue; }
        if have_previous && e.advance.wrapping_add(1) != previous_advance { return out; }
        seq[10 - got] = e;
        previous_advance = e.advance;
        have_previous = true;
        got += 1;
    }
    if got != 11 || seq[10].advance != capture_advance { return out; }

    let mut obs = [0i16; 10];
    for j in 0..10usize {
        let p0 = direct_phase_m((seq[j].div >> 8) as u8, seq[j].asub);
        let p1 = direct_phase_m((seq[j + 1].div >> 8) as u8, seq[j + 1].asub);
        let d = (((p1 as i32 - p0 as i32) & 0x3fff) - PRE_FP_FRAME_M) as i16;
        obs[j] = d;
    }

    let mut best = u32::MAX;
    let mut second = u32::MAX;
    let mut best_proto = 0usize;
    let mut best_rot0 = 0usize;
    for proto in 0..PRE_FP_PROTOS.len() {
        for rot0 in 0..16usize {
            let mut score = 0u32;
            for j in 0..10usize {
                let d = obs[j] as i32 - PRE_FP_PROTOS[proto][(rot0 + j) & 15] as i32;
                score = score.saturating_add(if d < 0 { (-d) as u32 } else { d as u32 });
            }
            if score < best {
                second = best; best = score; best_proto = proto; best_rot0 = rot0;
            } else if score < second {
                second = score;
            }
        }
    }

    // Exact and unique only. Anything else must continue naturally.
    if best != 0 || second == 0 { return out; }
    let next_rot = (best_rot0 + 10) & 15;
    let ap1 = capture_ap4
        .wrapping_add(PRE_FP_FRAME_M as u16)
        .wrapping_add(PRE_FP_PROTOS[best_proto][next_rot] as u16) & 0x3fff;
    let ap2 = ap1
        .wrapping_add(PRE_FP_FRAME_M as u16)
        .wrapping_add(PRE_FP_PROTOS[best_proto][(next_rot + 1) & 15] as u16) & 0x3fff;
    let state1 = exact_tail_normal_step(capture_state, ap1);
    let predeep = exact_tail_normal_step(state1, ap2);
    let base_hi = ((ap2 >> 6) & 0xff) as u8;
    let base_lo = (((ap2.wrapping_add(11)) >> 6) & 0xff) as u8;

    let mut candidates = [0u16; 64];
    let mut candidate_count = 0usize;
    let mut shiny_count = 0u8;
    let mut first_shiny = 0u16;

    // Route3 cross-products.
    for aa in R3_A_EXACT.iter() {
        for ss in R3_S_EXACT.iter() {
            let mut st = predeep;
            let mut prev_sub = st as u8;
            let mut sub = prev_sub;
            for k in 0..3usize {
                st = exact_tail_step(st, base_hi.wrapping_add(aa[k]), base_lo.wrapping_add(ss[k]));
                prev_sub = sub;
                sub = st as u8;
            }
            let raw = ((prev_sub as u16) << 8) | sub as u16;
            exact_tail_push_candidate(&mut candidates, &mut candidate_count, raw, &mut shiny_count, &mut first_shiny);
        }
    }

    // Route4 cross-products. Route is not trusted before the DV burst, so the
    // production gate always uses the union of route3 and route4 candidates.
    for aa in R4_A_EXACT.iter() {
        for ss in R4_S_EXACT.iter() {
            let mut st = predeep;
            let mut prev_sub = st as u8;
            let mut sub = prev_sub;
            for k in 0..4usize {
                st = exact_tail_step(st, base_hi.wrapping_add(aa[k]), base_lo.wrapping_add(ss[k]));
                prev_sub = sub;
                sub = st as u8;
            }
            let raw = ((prev_sub as u16) << 8) | sub as u16;
            exact_tail_push_candidate(&mut candidates, &mut candidate_count, raw, &mut shiny_count, &mut first_shiny);
        }
    }

    out.valid = true;
    out.proto = b'A' + best_proto as u8;
    out.next_rot = next_rot as u8;
    out.score = best as u16;
    out.second_score = second.min(0xffff) as u16;
    out.dv_ap4 = ap2;
    out.candidate_count = candidate_count.min(255) as u8;
    out.shiny_count = shiny_count;
    out.first_shiny = first_shiny;
    out
}

'''
if marker not in t:
    raise SystemExit('v781 exact-tail insertion marker missing')
t = t.replace(marker, insert + marker, 1)

# 3) Endpoint gate. Invalid/ambiguous tail eval fails open. Valid finite union
# with zero shiny candidates is terminal and saved immediately because the
# trial is intentionally aborted before DV. Shiny-containing unions continue
# naturally with fast-tail instrumentation exactly as before.
old_ep = '''                deep_log_stop();\n                call_log_stop();\n                endpoint_fast_tail_start();\n                // v6.3: no late DV-2 pause. Keep the tail input-free and let\n                // the existing result detector/auto-save finish naturally.\n'''
new_ep = '''                deep_log_stop();\n                call_log_stop();\n\n                let tail = exact_tail_eval(\n                    self.entries, self.len, self.endpoint.capture_advance,\n                    self.endpoint.state, self.endpoint.ap4,\n                );\n                if tail.valid {\n                    // Reuse existing CSV/UI telemetry fields for a compact\n                    // implementation: W=candidate union size, mask=number of\n                    // shiny raws, raw=first shiny raw.\n                    self.practical_support = tail.candidate_count;\n                    self.practical_mask = tail.shiny_count;\n                    self.practical_raw = tail.first_shiny;\n                    self.practical_post_proto = tail.proto;\n                    self.practical_post_rot = tail.next_rot;\n                    self.practical_post_score = tail.second_score;\n                    if tail.shiny_count == 0 {\n                        // v7.8.1 hard negative gate: all currently validated\n                        // route3+route4 exact candidates are non-shiny. Save\n                        // this aborted trace and pause before any DV frame.\n                        self.practical_miss = 14;\n                        self.practical_terminal_advance = rng_advance();\n                        self.practical_active = false;\n                        self.probe_active = false;\n                        endpoint_fast_tail_stop();\n                        self.state = TraceState::Done;\n                        self.save();\n                        pnp::request_pause();\n                        return;\n                    }\n                }\n\n                // Invalid/ambiguous endpoint classification fails open.  A\n                // valid union containing >=1 shiny raw also continues without\n                // any synthetic input or RNG/DIV/DV write.\n                endpoint_fast_tail_start();\n'''
t = rep(t, old_ep, new_ep, 'endpoint exact gate')

# Clear user-facing reason at the new terminal gate.
old_ui = '''            } else if self.practical_miss == 13 {\n                pnp::println!("WHY REL40 CAPTURE");\n            } else {\n'''
new_ui = '''            } else if self.practical_miss == 13 {\n                pnp::println!("WHY REL40 CAPTURE");\n            } else if self.practical_miss == 14 {\n                pnp::println!("TAIL NO SHINY");\n                pnp::println!("CAND {} SH{}",self.practical_support,self.practical_mask);\n            } else {\n'''
t = rep(t, old_ui, new_ui, 'tail gate UI')

# v7.8.0 rel40 now benefits from the straddle fallback automatically; keep its
# non-terminal behavior because the authoritative decision is the late DV-2
# finite-candidate gate.
t = t.replace('V780', 'V781', 1) if 'V780' in t else t
T.write_text(t)
print('Applied v7.8.1 Progressive Exact Tail: straddle POST fallback + DV-2 finite route union gate')
