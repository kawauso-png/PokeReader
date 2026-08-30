use super::adaptive_model::AdaptiveStats;

const HORIZON: u8 = 16;
const SCAN_EVERY: u8 = 8;
const MAX_STATES: usize = 512;
const HASH_SIZE: usize = 1024;
const RAW_WORDS: usize = 1024; // 65536 bits

#[derive(Clone, Copy)]
struct NState {
    add: u8,
    div: u8,
    phase: u8,
    frame: u8,
}
const EMPTY_STATE: NState = NState { add: 0, div: 0, phase: 0, frame: 0 };

#[derive(Clone, Copy, Default)]
pub struct ForecastStats {
    pub valid: bool,
    pub phase_count: u8,
    pub now_candidates: u16,
    pub now_shiny: u8,
    pub next_horizon: u8,
    pub next_candidates: u16,
    pub next_shiny: u8,
    pub target_seq: u32,
    pub overflow: bool,
    pub scan_age: u8,
}

#[derive(Clone, Copy, Default)]
pub struct ArmForecast {
    pub valid: bool,
    pub candidates: u16,
    pub shiny: u8,
    pub phase_count: u8,
    pub next_horizon: u8,
    pub next_candidates: u16,
    pub next_shiny: u8,
    pub target_seq: u32,
}

static mut PHASE_MASK: u64 = 0;
static mut PHASE_LAST_SEQ: u32 = 0;
static mut SCAN_TICK: u8 = 0;
static mut LIVE: ForecastStats = ForecastStats {
    valid: false, phase_count: 0, now_candidates: 0, now_shiny: 0,
    next_horizon: 0, next_candidates: 0, next_shiny: 0, target_seq: 0,
    overflow: false, scan_age: 0,
};
static mut ARM: ArmForecast = ArmForecast {
    valid: false, candidates: 0, shiny: 0, phase_count: 0,
    next_horizon: 0, next_candidates: 0, next_shiny: 0, target_seq: 0,
};

static mut CUR: [NState; MAX_STATES] = [EMPTY_STATE; MAX_STATES];
static mut NEXT: [NState; MAX_STATES] = [EMPTY_STATE; MAX_STATES];
static mut HASH: [u32; HASH_SIZE] = [0; HASH_SIZE];
static mut RAW_BITS: [u64; RAW_WORDS] = [0; RAW_WORDS];
static mut ARM_BITS: [u64; RAW_WORDS] = [0; RAW_WORDS];

fn rng_add(rng: u32) -> u8 { ((rng >> 16) & 0xFF) as u8 }

fn next_frame(frame: u8) -> u8 {
    match frame {
        1 => 5,
        2..=5 => frame - 1,
        _ => 0,
    }
}

fn shiny(raw: u16) -> bool {
    let atk = ((raw >> 12) & 0xF) as u8;
    let def = ((raw >> 8) & 0xF) as u8;
    let spe = ((raw >> 4) & 0xF) as u8;
    let spc = (raw & 0xF) as u8;
    def == 10 && spe == 10 && spc == 10
        && matches!(atk, 2 | 3 | 6 | 7 | 10 | 11 | 14 | 15)
}

fn phase_step(phase: u8) -> u8 {
    0x12 + u8::from((phase as u16 + 20) >= 64)
}
fn phase_next(phase: u8) -> u8 { phase.wrapping_add(20) & 0x3F }

pub fn observe_phase(prev_seq: u32, prev_div: u8, seq: u32, div: u8, usable: bool) {
    unsafe {
        if !usable || prev_seq == 0 || seq != prev_seq.wrapping_add(1)
            || (PHASE_LAST_SEQ != 0 && PHASE_LAST_SEQ != prev_seq)
        {
            PHASE_MASK = 0;
            PHASE_LAST_SEQ = seq;
            return;
        }
        let step = div.wrapping_sub(prev_div);
        if !matches!(step, 0x12 | 0x13) {
            PHASE_MASK = 0;
            PHASE_LAST_SEQ = seq;
            return;
        }

        let mut next = 0u64;
        if PHASE_MASK == 0 {
            for p in 0u8..64u8 {
                if phase_step(p) == step {
                    next |= 1u64 << phase_next(p);
                }
            }
        } else {
            for p in 0u8..64u8 {
                if (PHASE_MASK & (1u64 << p)) != 0 && phase_step(p) == step {
                    next |= 1u64 << phase_next(p);
                }
            }
            // A host-side sampling slip can move the apparent phase family.
            // Re-seed from the current observed DIV step rather than staying dead.
            if next == 0 {
                for p in 0u8..64u8 {
                    if phase_step(p) == step {
                        next |= 1u64 << phase_next(p);
                    }
                }
            }
        }
        PHASE_MASK = next;
        PHASE_LAST_SEQ = seq;
    }
}

fn step_add(add: u8, div: u8, k: u8, div_step: u8) -> (u8, u8) {
    let nd = div.wrapping_add(div_step);
    let first = nd.wrapping_add(k);
    (add.wrapping_add(first), nd)
}

fn primary_offset(rel: u8) -> u16 {
    match rel {
        1 => 0x602, 2 => 0x601, 3 => 0x605, 4 => 0x601, 5 => 0x61E,
        6 => 0x4D9, 7 => 0x615, 8 => 0x4E6, 9 => 0x619, 10 => 0x4EA,
        11 => 0x371, _ => 0,
    }
}
fn anomaly_offset(rel: u8) -> u16 {
    match rel {
        3 => 0x691, 6 => 0x569, 7 => 0x6AD, 9 => 0x6B5, _ => 0,
    }
}
fn anomaly_rel(frame: u8) -> u8 {
    match frame {
        5 => 3,
        2 => 6,
        1 => 7,
        3 => 9,
        _ => 0, // hFrameCounter=4 is not represented in the 8 calibration traces.
    }
}

fn run_event_path(mut add: u8, mut div: u8, p0: u8, anomaly: u8) -> (u8, u8, u8) {
    let mut p = p0;
    for rel in 1u8..=11u8 {
        let off = if rel == anomaly { anomaly_offset(rel) } else { primary_offset(rel) };
        let step = phase_step(p);
        let pc = phase_next(p);
        let k = (((pc as u16) + off) / 64) as u8;
        let v = step_add(add, div, k, step);
        add = v.0;
        div = v.1;
        p = pc;
    }
    (add, div, p)
}

unsafe fn raw_clear() {
    for i in 0..RAW_WORDS { RAW_BITS[i] = 0; }
}
unsafe fn raw_insert(raw: u16, count: &mut u16, shiny_count: &mut u8) {
    let wi = (raw as usize) >> 6;
    let bit = 1u64 << ((raw as usize) & 63);
    if (RAW_BITS[wi] & bit) == 0 {
        RAW_BITS[wi] |= bit;
        *count = count.saturating_add(1);
        if shiny(raw) { *shiny_count = shiny_count.saturating_add(1); }
    }
}

unsafe fn collect_battle(add: u8, div: u8, p: u8, count: &mut u16, shiny_count: &mut u8) {
    let qv_lo = ((p as u16 + 2053) / 64) as u8;
    let qv_hi = ((p as u16 + 2071) / 64) as u8;
    let mut qv = qv_lo;
    loop {
        let mut tb = 5661u16;
        while tb <= 5667 {
            let qb1 = ((p as u16 + tb) / 64) as u8;
            let qb2 = ((p as u16 + tb + 120) / 64) as u8;
            let rv = div.wrapping_add(qv);
            let rb1 = div.wrapping_add(qb1);
            let rb2 = div.wrapping_add(qb2);
            // The DV frame has one ordinary Random_ before two consecutive
            // non-link BattleRandom calls. BattleRandom enters Random_ with C=1.
            let low = add.wrapping_add(rv).wrapping_add(rb1).wrapping_add(1);
            let high = low.wrapping_add(rb2).wrapping_add(1);
            raw_insert(((high as u16) << 8) | low as u16, count, shiny_count);
            tb += 1;
        }
        if qv == qv_hi { break; }
        qv = qv.wrapping_add(1);
    }
}

unsafe fn collect_event(add: u8, div: u8, phase: u8, frame: u8,
                        count: &mut u16, shiny_count: &mut u8) {
    // Exact2F hardware traces show the event-side sample phase can stay aligned
    // or shift by a small 4/8 M-cycle host sampling skew. Keep all three.
    for jump in [0u8, 60u8, 56u8] { // 0, -4, -8 mod 64
        let p0 = phase.wrapping_add(jump) & 0x3F;
        let primary = run_event_path(add, div, p0, 0);
        collect_battle(primary.0, primary.1, primary.2, count, shiny_count);

        if (p0 & 3) == 3 {
            let rel = anomaly_rel(frame);
            if rel != 0 {
                let alt = run_event_path(add, div, p0, rel);
                collect_battle(alt.0, alt.1, alt.2, count, shiny_count);
            } else if frame == 4 {
                // No frame-4 calibration yet: conservatively include each
                // one-anomaly path observed for the other frame-counter classes.
                for r in [3u8, 6u8, 7u8, 9u8] {
                    let alt = run_event_path(add, div, p0, r);
                    collect_battle(alt.0, alt.1, alt.2, count, shiny_count);
                }
            }
        }
    }
}

unsafe fn evaluate_states(count_states: usize) -> (u16, u8) {
    raw_clear();
    let mut count = 0u16;
    let mut shiny_count = 0u8;
    for i in 0..count_states {
        let s = CUR[i];
        collect_event(s.add, s.div, s.phase, s.frame, &mut count, &mut shiny_count);
    }
    (count, shiny_count)
}

fn pack(s: NState) -> u32 {
    1u32
        .wrapping_add(s.add as u32)
        .wrapping_add((s.div as u32) << 8)
        .wrapping_add((s.phase as u32) << 16)
        .wrapping_add((s.frame as u32) << 24)
}
unsafe fn hash_clear() {
    for i in 0..HASH_SIZE { HASH[i] = 0; }
}
unsafe fn next_insert(s: NState, count: &mut usize) -> bool {
    let key = pack(s);
    let mut idx = ((key.wrapping_mul(0x9E37_79B1)) as usize) & (HASH_SIZE - 1);
    for _ in 0..HASH_SIZE {
        let cur = HASH[idx];
        if cur == key { return true; }
        if cur == 0 {
            if *count >= MAX_STATES { return false; }
            HASH[idx] = key;
            NEXT[*count] = s;
            *count += 1;
            return true;
        }
        idx = (idx + 1) & (HASH_SIZE - 1);
    }
    false
}

unsafe fn propagate_normal(cur_count: usize, seq: u32, base: u8, residue20: u8) -> Option<usize> {
    hash_clear();
    let mut out = 0usize;
    for i in 0..cur_count {
        let s = CUR[i];
        let step = phase_step(s.phase);
        let np = phase_next(s.phase);
        let nf = next_frame(s.frame);
        if nf == 0 { return None; }
        let special = ((seq + 1) % 20) as u8 == residue20;

        let mut add_one = |k: u8| -> bool {
            let v = step_add(s.add, s.div, k, step);
            unsafe { next_insert(NState { add: v.0, div: v.1, phase: np, frame: nf }, &mut out) }
        };

        if special {
            if !add_one(base.wrapping_add(2)) || !add_one(base.wrapping_add(3)) { return None; }
        } else if step == 0x12 {
            if !add_one(base) || !add_one(base.wrapping_add(1)) { return None; }
        } else {
            if !add_one(base.wrapping_sub(1)) || !add_one(base) { return None; }
        }
    }
    for i in 0..out { CUR[i] = NEXT[i]; }
    Some(out)
}

unsafe fn seed_current(rng: u32, div: u8, frame: u8) -> usize {
    let add = rng_add(rng);
    let mut n = 0usize;
    for p in 0u8..64u8 {
        if (PHASE_MASK & (1u64 << p)) != 0 && n < MAX_STATES {
            CUR[n] = NState { add, div, phase: p, frame };
            n += 1;
        }
    }
    n
}

unsafe fn scan_full(seq: u32, rng: u32, div: u8, frame: u8, adp: AdaptiveStats) -> ForecastStats {
    let phase_count = PHASE_MASK.count_ones() as u8;
    let mut out = ForecastStats {
        valid: false, phase_count, now_candidates: 0, now_shiny: 0,
        next_horizon: 0, next_candidates: 0, next_shiny: 0, target_seq: 0,
        overflow: false, scan_age: 0,
    };
    if !adp.ready || phase_count == 0 || next_frame(frame) == 0 { return out; }

    let mut n = seed_current(rng, div, frame);
    if n == 0 { return out; }
    let now = evaluate_states(n);
    out.now_candidates = now.0;
    out.now_shiny = now.1;

    for h in 1u8..=HORIZON {
        let Some(nn) = propagate_normal(n, seq + h as u32 - 1, adp.base, adp.residue20) else {
            out.overflow = true;
            return out;
        };
        n = nn;
        let e = evaluate_states(n);
        if out.next_horizon == 0 && e.1 != 0 {
            out.next_horizon = h;
            out.next_candidates = e.0;
            out.next_shiny = e.1;
            out.target_seq = seq.wrapping_add(h as u32);
        }
    }
    out.valid = true;
    out
}

pub fn scan(seq: u32, rng: u32, div: u8, frame: u8, adp: AdaptiveStats) -> ForecastStats {
    unsafe {
        SCAN_TICK = SCAN_TICK.wrapping_add(1);
        let target_near = LIVE.target_seq >= seq && LIVE.target_seq.wrapping_sub(seq) <= 4;
        if !adp.ready || PHASE_MASK == 0 {
            LIVE.valid = false;
            LIVE.scan_age = 0;
            return LIVE;
        }
        if SCAN_TICK % SCAN_EVERY == 0 || target_near || !LIVE.valid {
            LIVE = scan_full(seq, rng, div, frame, adp);
        } else {
            LIVE.scan_age = LIVE.scan_age.saturating_add(1);
        }
        LIVE
    }
}

pub fn mark_arm(seq: u32, rng: u32, div: u8, frame: u8, adp: AdaptiveStats) {
    unsafe {
        let fresh = scan_full(seq, rng, div, frame, adp);
        ARM = ArmForecast {
            valid: fresh.valid,
            candidates: fresh.now_candidates,
            shiny: fresh.now_shiny,
            phase_count: fresh.phase_count,
            next_horizon: fresh.next_horizon,
            next_candidates: fresh.next_candidates,
            next_shiny: fresh.next_shiny,
            target_seq: fresh.target_seq,
        };
        for i in 0..RAW_WORDS { ARM_BITS[i] = RAW_BITS[i]; }
    }
}

pub fn arm_stats() -> ArmForecast { unsafe { ARM } }
pub fn arm_contains(raw: u16) -> bool {
    unsafe {
        if !ARM.valid { return false; }
        let wi = (raw as usize) >> 6;
        let bit = 1u64 << ((raw as usize) & 63);
        (ARM_BITS[wi] & bit) != 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shiny_rule_is_gen1_dv_rule() {
        assert!(shiny(0x2AAA));
        assert!(shiny(0xFAAA));
        assert!(!shiny(0x1AAA));
        assert!(!shiny(0x2BAA));
    }

    #[test]
    fn trace_0043_primary_event_reaches_known_pre_add_div() {
        // Trigger: ADD=54, DIV=27, frame=1. Event phase p0=0 is compatible
        // with the observed DIV path. The primary timing path reaches PRE ADD=A8 DIV=F0.
        let v = run_event_path(0x54, 0x27, 0, 0);
        assert_eq!((v.0, v.1, v.2), (0xA8, 0xF0, 28));
    }

    #[test]
    fn trace_0042_primary_event_reaches_known_pre_add_div() {
        // Trigger: ADD=0E, DIV=C7, frame=3, p0=44..47. p0=44 reaches
        // the observed PRE ADD=48 DIV=91.
        let v = run_event_path(0x0E, 0xC7, 44, 0);
        assert_eq!((v.0, v.1), (0x48, 0x91));
    }

    #[test]
    fn battle_timing_formula_contains_trace_0043_raw() {
        // PRE ADD=A8 DIV=F0, phase=28. Any calibrated timing pair in the
        // lower interval gives the observed 4C01 branch.
        let add = 0xA8u8;
        let div = 0xF0u8;
        let p = 28u8;
        let qv = ((p as u16 + 2053) / 64) as u8;
        let qb1 = ((p as u16 + 5661) / 64) as u8;
        let qb2 = ((p as u16 + 5661 + 120) / 64) as u8;
        let low = add.wrapping_add(div.wrapping_add(qv))
            .wrapping_add(div.wrapping_add(qb1)).wrapping_add(1);
        let high = low.wrapping_add(div.wrapping_add(qb2)).wrapping_add(1);
        assert_eq!(((high as u16) << 8) | low as u16, 0x4C01);
    }
}
