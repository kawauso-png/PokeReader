const SUB_MOD: u16 = 64;
const FRAME_SUB_STEP: u8 = 20;
const FRAME_DIV_BASE: u8 = 0x12;
const RANDOM_PAIR_M: u8 = 11;
const MAX_OFFSET_M: u16 = 0x3FFF;
const MAX_CANDIDATES: usize = 64 * 127;
const FORECAST_HORIZON: usize = 16;
const FORECAST_MAX_FITS: usize = 128;
const FORECAST_MIN_QUIET: u16 = 2;

#[derive(Clone, Copy)]
struct Candidate {
    sample_sub: u8,
    offset_m: u16,
}

const EMPTY_CANDIDATE: Candidate = Candidate { sample_sub: 0, offset_m: 0 };

#[derive(Clone, Copy, Default)]
pub struct TrackerStats {
    pub valid: bool,
    pub transitions: u16,
    pub fits: u16,
    pub sub_count: u8,
    pub lock_prefix: u8,
    pub forecast_checks: u16,
    pub forecast_hits: u16,
    pub resets: u16,
    pub quiet_streak: u16,
    pub rng_skips: u16,
    pub last_k: u8,
    pub last_div_step: u8,
    pub last_gap: u8,
    pub last_reason: u8,
}

struct Tracker {
    candidates: [Candidate; MAX_CANDIDATES],
    count: usize,
    transitions: u16,
    last_seq: u32,
    last_usable: bool,
    forecast_valid: bool,
    forecast_rng: u32,
    forecast_div: u8,
    lock_prefix: u8,
    forecast_checks: u16,
    forecast_hits: u16,
    resets: u16,
    quiet_streak: u16,
    rng_skips: u16,
    last_k: u8,
    last_div_step: u8,
    last_gap: u8,
    last_reason: u8,
    arm_stats: TrackerStats,
}

static mut TRACKER: Tracker = Tracker {
    candidates: [EMPTY_CANDIDATE; MAX_CANDIDATES],
    count: 0,
    transitions: 0,
    last_seq: 0,
    last_usable: false,
    forecast_valid: false,
    forecast_rng: 0,
    forecast_div: 0,
    lock_prefix: 0,
    forecast_checks: 0,
    forecast_hits: 0,
    resets: 0,
    quiet_streak: 0,
    rng_skips: 0,
    last_k: 0,
    last_div_step: 0,
    last_gap: 0xFF,
    last_reason: 0,
    arm_stats: TrackerStats {
        valid: false,
        transitions: 0,
        fits: 0,
        sub_count: 0,
        lock_prefix: 0,
        forecast_checks: 0,
        forecast_hits: 0,
        resets: 0,
        quiet_streak: 0,
        rng_skips: 0,
        last_k: 0,
        last_div_step: 0,
        last_gap: 0xFF,
        last_reason: 0,
    },
};

fn rng_add(rng: u32) -> u8 { ((rng >> 16) & 0xFF) as u8 }
fn rng_sub(rng: u32) -> u8 { ((rng >> 8) & 0xFF) as u8 }

fn infer_vblank(prev_rng: u32, current_rng: u32) -> Option<(u8, u8)> {
    let add0 = rng_add(prev_rng);
    let sub0 = rng_sub(prev_rng);
    let add1 = rng_add(current_rng);
    let sub1 = rng_sub(current_rng);
    let first = add1.wrapping_sub(add0);
    let carry = u8::from((add0 as u16 + first as u16) > 0xFF);
    let second = sub0.wrapping_sub(sub1).wrapping_sub(carry);
    let gap = second.wrapping_sub(first);
    if gap <= 1 { Some((first, gap)) } else { None }
}

fn next_sample_sub(sample_sub: u8) -> u8 {
    sample_sub.wrapping_add(FRAME_SUB_STEP) & 0x3F
}

fn next_div_step(sample_sub: u8) -> u8 {
    FRAME_DIV_BASE + u8::from((sample_sub as u16 + FRAME_SUB_STEP as u16) >= SUB_MOD)
}

fn random_gap(first_sub: u8) -> u8 {
    u8::from((first_sub as u16 + RANDOM_PAIR_M as u16) >= SUB_MOD)
}

fn predict_one(rng: u32, div: u8, candidate: Candidate) -> (u32, u8, Candidate) {
    let next_div = div.wrapping_add(next_div_step(candidate.sample_sub));
    let next_sub = next_sample_sub(candidate.sample_sub);
    let total = next_sub as u16 + candidate.offset_m;
    let first = next_div.wrapping_add((total / SUB_MOD) as u8);
    let first_sub = (total % SUB_MOD) as u8;
    let second = first.wrapping_add(random_gap(first_sub));

    let add0 = rng_add(rng);
    let sub0 = rng_sub(rng);
    let add_total = add0 as u16 + first as u16;
    let add1 = add_total as u8;
    let carry = u8::from(add_total > 0xFF);
    let sub1 = sub0.wrapping_sub(second).wrapping_sub(carry);

    (
        ((add1 as u32) << 16) | ((sub1 as u32) << 8),
        next_div,
        Candidate { sample_sub: next_sub, offset_m: candidate.offset_m },
    )
}

impl Tracker {
    fn clear(&mut self, seq: u32, usable: bool, reason: u8, count_reset: bool) {
        self.count = 0;
        self.transitions = 0;
        self.last_seq = seq;
        self.last_usable = usable;
        self.forecast_valid = false;
        self.lock_prefix = 0;
        self.quiet_streak = 0;
        self.last_reason = reason;
        if count_reset { self.resets = self.resets.wrapping_add(1); }
    }

    fn sub_mask(&self) -> u64 {
        let mut mask = 0u64;
        for i in 0..self.count {
            mask |= 1u64 << self.candidates[i].sample_sub;
        }
        mask
    }

    fn sub_count(&self) -> u8 {
        self.sub_mask().count_ones() as u8
    }

    fn stats(&self) -> TrackerStats {
        TrackerStats {
            valid: self.transitions != 0 && self.count != 0,
            transitions: self.transitions,
            fits: self.count.min(u16::MAX as usize) as u16,
            sub_count: self.sub_count(),
            lock_prefix: self.lock_prefix,
            forecast_checks: self.forecast_checks,
            forecast_hits: self.forecast_hits,
            resets: self.resets,
            quiet_streak: self.quiet_streak,
            rng_skips: self.rng_skips,
            last_k: self.last_k,
            last_div_step: self.last_div_step,
            last_gap: self.last_gap,
            last_reason: self.last_reason,
        }
    }

    fn candidate_matches_current(current: Candidate, div: u8, first: u8, gap: u8) -> bool {
        let total = current.sample_sub as u16 + current.offset_m;
        let predicted_first = div.wrapping_add((total / SUB_MOD) as u8);
        let first_sub = (total % SUB_MOD) as u8;
        predicted_first == first && random_gap(first_sub) == gap
    }

    fn offset_bounds(first: u8, div: u8) -> (u16, u16) {
        let k = first.wrapping_sub(div) as u16;
        let center = k * SUB_MOD;
        (
            center.saturating_sub(63),
            core::cmp::min(center.saturating_add(63), MAX_OFFSET_M),
        )
    }

    fn seed_from_transition(
        &mut self,
        seq: u32,
        div: u8,
        div_step: u8,
        first: u8,
        gap: u8,
        reason: u8,
    ) -> bool {
        self.last_k = first.wrapping_sub(div);
        self.last_div_step = div_step;
        self.last_gap = gap;
        let (lo, hi) = Self::offset_bounds(first, div);
        let mut n = 0usize;

        for prev_sub in 0u8..64u8 {
            if next_div_step(prev_sub) != div_step { continue; }
            let current_sub = next_sample_sub(prev_sub);
            let mut offset = lo;
            while offset <= hi {
                let c = Candidate { sample_sub: current_sub, offset_m: offset };
                if Self::candidate_matches_current(c, div, first, gap) {
                    self.candidates[n] = c;
                    n += 1;
                }
                if offset == hi { break; }
                offset += 1;
            }
        }

        self.count = n;
        self.transitions = u16::from(n != 0);
        self.last_seq = seq;
        self.last_usable = true;
        self.forecast_valid = false;
        self.lock_prefix = 0;
        self.quiet_streak = u16::from(n != 0);
        self.last_reason = if n != 0 { reason } else { 7 };
        n != 0
    }

    fn reacquire_offsets_current(&mut self, div: u8, first: u8, gap: u8) -> bool {
        let mask = self.sub_mask();
        if mask == 0 { return false; }

        let (lo, hi) = Self::offset_bounds(first, div);
        let mut n = 0usize;
        for sample_sub in 0u8..64u8 {
            if (mask & (1u64 << sample_sub)) == 0 { continue; }
            let mut offset = lo;
            while offset <= hi {
                let c = Candidate { sample_sub, offset_m: offset };
                if Self::candidate_matches_current(c, div, first, gap) {
                    self.candidates[n] = c;
                    n += 1;
                }
                if offset == hi { break; }
                offset += 1;
            }
        }
        if n == 0 { return false; }
        self.count = n;
        self.forecast_valid = false;
        self.lock_prefix = 0;
        self.quiet_streak = 1;
        true
    }

    fn rebuild_forecast(&mut self, rng: u32, div: u8) {
        self.forecast_valid = false;
        self.lock_prefix = 0;
        if self.quiet_streak < FORECAST_MIN_QUIET || self.count == 0 || self.count > FORECAST_MAX_FITS {
            return;
        }

        let mut ref_rng = [0u32; FORECAST_HORIZON];
        let mut ref_div = [0u8; FORECAST_HORIZON];
        let mut c = self.candidates[0];
        let mut r = rng;
        let mut d = div;
        for k in 0..FORECAST_HORIZON {
            let (nr, nd, nc) = predict_one(r, d, c);
            ref_rng[k] = nr;
            ref_div[k] = nd;
            r = nr;
            d = nd;
            c = nc;
        }

        let mut same = [true; FORECAST_HORIZON];
        for i in 1..self.count {
            let mut c = self.candidates[i];
            let mut r = rng;
            let mut d = div;
            for k in 0..FORECAST_HORIZON {
                let (nr, nd, nc) = predict_one(r, d, c);
                if nr != ref_rng[k] || nd != ref_div[k] { same[k] = false; }
                r = nr;
                d = nd;
                c = nc;
            }
        }

        let mut prefix = 0u8;
        for v in same {
            if !v { break; }
            prefix += 1;
        }
        self.lock_prefix = prefix;
        if prefix != 0 {
            self.forecast_valid = true;
            self.forecast_rng = ref_rng[0];
            self.forecast_div = ref_div[0];
        }
    }

    fn advance_div_only(&mut self, div_step: u8) -> bool {
        let mut write = 0usize;
        for i in 0..self.count {
            let c = self.candidates[i];
            if next_div_step(c.sample_sub) != div_step { continue; }
            self.candidates[write] = Candidate {
                sample_sub: next_sample_sub(c.sample_sub),
                offset_m: c.offset_m,
            };
            write += 1;
        }
        self.count = write;
        write != 0
    }

    fn filter_rng_current(&mut self, div: u8, first: u8, gap: u8) -> bool {
        let mut matches = 0usize;
        for i in 0..self.count {
            if Self::candidate_matches_current(self.candidates[i], div, first, gap) {
                matches += 1;
            }
        }
        if matches == 0 { return false; }

        let mut write = 0usize;
        for i in 0..self.count {
            let c = self.candidates[i];
            if Self::candidate_matches_current(c, div, first, gap) {
                self.candidates[write] = c;
                write += 1;
            }
        }
        self.count = write;
        true
    }

    fn observe(
        &mut self,
        prev_seq: u32,
        prev_rng: u32,
        prev_div: u8,
        seq: u32,
        rng: u32,
        div: u8,
        usable: bool,
    ) -> TrackerStats {
        if !usable {
            self.clear(seq, false, 1, self.count != 0 || self.transitions != 0);
            return self.stats();
        }

        let consecutive = prev_seq != 0
            && seq == prev_seq.wrapping_add(1)
            && self.last_seq == prev_seq
            && self.last_usable;
        if !consecutive {
            self.clear(seq, true, 2, false);
            return self.stats();
        }

        let div_step = div.wrapping_sub(prev_div);
        self.last_div_step = div_step;
        if !matches!(div_step, 0x12 | 0x13) {
            self.clear(seq, true, 4, self.count != 0 || self.transitions != 0);
            return self.stats();
        }

        let inferred = infer_vblank(prev_rng, rng);
        if let Some((first, gap)) = inferred {
            self.last_gap = gap;
            self.last_k = first.wrapping_sub(div);
        } else {
            self.last_gap = 0xFF;
        }

        let forecast_miss = self.forecast_valid
            && (self.forecast_rng != (rng & 0xFFFF00) || self.forecast_div != div);
        if self.forecast_valid {
            self.forecast_checks = self.forecast_checks.wrapping_add(1);
            if !forecast_miss { self.forecast_hits = self.forecast_hits.wrapping_add(1); }
        }

        if self.count == 0 {
            if let Some((first, gap)) = inferred {
                if self.seed_from_transition(seq, div, div_step, first, gap, 0) {
                    self.rebuild_forecast(rng, div);
                }
            } else {
                self.last_seq = seq;
                self.last_usable = true;
                self.last_reason = 3;
            }
            return self.stats();
        }

        if !self.advance_div_only(div_step) {
            self.resets = self.resets.wrapping_add(1);
            if let Some((first, gap)) = inferred {
                if self.seed_from_transition(seq, div, div_step, first, gap, 6) {
                    self.rebuild_forecast(rng, div);
                }
            } else {
                self.clear(seq, true, 6, false);
            }
            return self.stats();
        }

        self.transitions = self.transitions.wrapping_add(1);
        self.last_seq = seq;
        self.last_usable = true;

        if let Some((first, gap)) = inferred {
            let current_match = self.filter_rng_current(div, first, gap);
            if current_match && !forecast_miss {
                self.quiet_streak = self.quiet_streak.wrapping_add(1);
                self.last_reason = 0;
                self.rebuild_forecast(rng, div);
            } else if current_match {
                self.rng_skips = self.rng_skips.wrapping_add(1);
                self.quiet_streak = 0;
                self.forecast_valid = false;
                self.lock_prefix = 0;
                self.last_reason = 9;
            } else {
                self.rng_skips = self.rng_skips.wrapping_add(1);
                if self.reacquire_offsets_current(div, first, gap) {
                    self.last_reason = 10;
                } else {
                    self.quiet_streak = 0;
                    self.forecast_valid = false;
                    self.lock_prefix = 0;
                    self.last_reason = 8;
                }
            }
        } else {
            self.rng_skips = self.rng_skips.wrapping_add(1);
            self.quiet_streak = 0;
            self.forecast_valid = false;
            self.lock_prefix = 0;
            self.last_reason = 3;
        }

        self.stats()
    }
}

pub fn observe(
    prev_seq: u32,
    prev_rng: u32,
    prev_div: u8,
    seq: u32,
    rng: u32,
    div: u8,
    usable: bool,
) -> TrackerStats {
    unsafe { TRACKER.observe(prev_seq, prev_rng, prev_div, seq, rng, div, usable) }
}

pub fn stats() -> TrackerStats {
    unsafe { TRACKER.stats() }
}

pub fn mark_arm() {
    unsafe { TRACKER.arm_stats = TRACKER.stats(); }
}

pub fn arm_stats() -> TrackerStats {
    unsafe { TRACKER.arm_stats }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fresh() -> Tracker {
        Tracker {
            candidates: [EMPTY_CANDIDATE; MAX_CANDIDATES],
            count: 0,
            transitions: 0,
            last_seq: 1410,
            last_usable: true,
            forecast_valid: false,
            forecast_rng: 0,
            forecast_div: 0,
            lock_prefix: 0,
            forecast_checks: 0,
            forecast_hits: 0,
            resets: 0,
            quiet_streak: 0,
            rng_skips: 0,
            last_k: 0,
            last_div_step: 0,
            last_gap: 0xFF,
            last_reason: 0,
            arm_stats: TrackerStats::default(),
        }
    }

    #[test]
    fn threshold_physics_are_stable() {
        assert_eq!(next_div_step(43), 0x12);
        assert_eq!(next_div_step(44), 0x13);
        assert_eq!(next_sample_sub(63), 19);
        assert_eq!(random_gap(52), 0);
        assert_eq!(random_gap(53), 1);
    }

    #[test]
    fn trace_0039_converges_and_forecasts() {
        let samples = [
            (0xCD9E00u32,0x0Cu8),(0x036700,0x1E),(0x4B1F00,0x30),
            (0xA6C400,0x42),(0x135600,0x55),(0x92D700,0x67),
            (0x234400,0x79),(0xC7A000,0x8C),(0x7DE900,0x9E),
        ];
        let mut t = fresh();
        for i in 1..samples.len() {
            let (pr,pd)=samples[i-1];
            let (r,d)=samples[i];
            let s=t.observe(1409+i as u32,pr,pd,1410+i as u32,r,d,true);
            if i==samples.len()-1 {
                assert_eq!(s.fits,16);
                assert_eq!(s.sub_count,4);
                assert_eq!(s.lock_prefix,3);
                assert_eq!(s.forecast_checks,s.forecast_hits);
                assert!(s.transitions>=6);
            }
        }
    }

    #[test]
    fn bad_offset_reacquires_without_losing_subphase() {
        let samples = [
            (0xCD9E00u32,0x0Cu8),(0x036700,0x1E),(0x4B1F00,0x30),
            (0xA6C400,0x42),(0x135600,0x55),(0x92D700,0x67),
        ];
        let mut t = fresh();
        for i in 1..4 {
            let (pr,pd)=samples[i-1];
            let (r,d)=samples[i];
            let _=t.observe(1409+i as u32,pr,pd,1410+i as u32,r,d,true);
        }
        let subs_before=t.sub_count();
        for i in 0..t.count {
            t.candidates[i].offset_m=t.candidates[i].offset_m.wrapping_add(64) & 0x3FFF;
        }
        t.forecast_valid=false;
        let s=t.observe(1413,samples[3].0,samples[3].1,1414,samples[4].0,samples[4].1,true);
        assert_eq!(s.last_reason,10);
        assert_eq!(s.sub_count,subs_before);
        assert_eq!(s.quiet_streak,1);
        let s2=t.observe(1414,samples[4].0,samples[4].1,1415,samples[5].0,samples[5].1,true);
        assert_eq!(s2.last_reason,0);
        assert!(s2.quiet_streak>=2);
    }
}
