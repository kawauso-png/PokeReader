const SUB_MOD: u16 = 64;
const FRAME_SUB_STEP: u8 = 20;
const FRAME_DIV_BASE: u8 = 0x12;
const RANDOM_PAIR_M: u8 = 11;
const NORMAL_FIRST_HIGH_OFFSET: u16 = 0x18 * SUB_MOD;
const OFFSET_MIN: u16 = NORMAL_FIRST_HIGH_OFFSET - 63;
const OFFSET_MAX: u16 = NORMAL_FIRST_HIGH_OFFSET + 63;
const OFFSET_COUNT: usize = (OFFSET_MAX - OFFSET_MIN + 1) as usize;
const MAX_CANDIDATES: usize = 64 * OFFSET_COUNT;
const FORECAST_HORIZON: usize = 16;
const FORECAST_MAX_FITS: usize = 128;

#[derive(Clone, Copy)]
struct Candidate {
    sample_sub: u8,
    offset_m: u16,
}

const EMPTY_CANDIDATE: Candidate = Candidate {
    sample_sub: 0,
    offset_m: 0,
};

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
}

struct Tracker {
    candidates: [Candidate; MAX_CANDIDATES],
    count: usize,
    transitions: u16,
    last_seq: u32,
    last_clean: bool,
    forecast_valid: bool,
    forecast_rng: u32,
    forecast_div: u8,
    lock_prefix: u8,
    forecast_checks: u16,
    forecast_hits: u16,
    resets: u16,
    arm_stats: TrackerStats,
}

static mut TRACKER: Tracker = Tracker {
    candidates: [EMPTY_CANDIDATE; MAX_CANDIDATES],
    count: 0,
    transitions: 0,
    last_seq: 0,
    last_clean: false,
    forecast_valid: false,
    forecast_rng: 0,
    forecast_div: 0,
    lock_prefix: 0,
    forecast_checks: 0,
    forecast_hits: 0,
    resets: 0,
    arm_stats: TrackerStats {
        valid: false,
        transitions: 0,
        fits: 0,
        sub_count: 0,
        lock_prefix: 0,
        forecast_checks: 0,
        forecast_hits: 0,
        resets: 0,
    },
};

fn rng_add(rng: u32) -> u8 {
    ((rng >> 16) & 0xFF) as u8
}

fn rng_sub(rng: u32) -> u8 {
    ((rng >> 8) & 0xFF) as u8
}

fn infer_vblank(prev_rng: u32, current_rng: u32) -> Option<(u8, u8)> {
    let add0 = rng_add(prev_rng);
    let sub0 = rng_sub(prev_rng);
    let add1 = rng_add(current_rng);
    let sub1 = rng_sub(current_rng);

    let first = add1.wrapping_sub(add0);
    let carry = u8::from((add0 as u16 + first as u16) > 0xFF);
    let second = sub0.wrapping_sub(sub1).wrapping_sub(carry);
    let gap = second.wrapping_sub(first);
    if gap <= 1 {
        Some((first, gap))
    } else {
        None
    }
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
    let next_rng = ((add1 as u32) << 16) | ((sub1 as u32) << 8);

    (
        next_rng,
        next_div,
        Candidate {
            sample_sub: next_sub,
            offset_m: candidate.offset_m,
        },
    )
}

impl Tracker {
    fn seed(&mut self, seq: u32, clean: bool, count_reset: bool) {
        let checks = self.forecast_checks;
        let hits = self.forecast_hits;
        let resets = self.resets.wrapping_add(u16::from(count_reset));
        let arm_stats = self.arm_stats;

        let mut n = 0usize;
        for sample_sub in 0u8..64u8 {
            let mut offset = OFFSET_MIN;
            while offset <= OFFSET_MAX {
                self.candidates[n] = Candidate {
                    sample_sub,
                    offset_m: offset,
                };
                n += 1;
                offset += 1;
            }
        }
        self.count = n;
        self.transitions = 0;
        self.last_seq = seq;
        self.last_clean = clean;
        self.forecast_valid = false;
        self.forecast_rng = 0;
        self.forecast_div = 0;
        self.lock_prefix = 0;
        self.forecast_checks = checks;
        self.forecast_hits = hits;
        self.resets = resets;
        self.arm_stats = arm_stats;
    }

    fn sub_count(&self) -> u8 {
        let mut mask = 0u64;
        for i in 0..self.count {
            mask |= 1u64 << self.candidates[i].sample_sub;
        }
        mask.count_ones() as u8
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
        }
    }

    fn rebuild_forecast(&mut self, rng: u32, div: u8) {
        self.forecast_valid = false;
        self.lock_prefix = 0;
        if self.count == 0 || self.count > FORECAST_MAX_FITS {
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
                if nr != ref_rng[k] || nd != ref_div[k] {
                    same[k] = false;
                }
                r = nr;
                d = nd;
                c = nc;
            }
        }

        let mut prefix = 0u8;
        for same_frame in same {
            if !same_frame {
                break;
            }
            prefix += 1;
        }
        self.lock_prefix = prefix;
        if prefix != 0 {
            self.forecast_valid = true;
            self.forecast_rng = ref_rng[0];
            self.forecast_div = ref_div[0];
        }
    }

    fn observe(
        &mut self,
        prev_seq: u32,
        prev_rng: u32,
        prev_div: u8,
        seq: u32,
        rng: u32,
        div: u8,
        clean: bool,
    ) -> TrackerStats {
        if self.count == 0 {
            self.seed(seq, clean, false);
            return self.stats();
        }

        let consecutive = prev_seq != 0
            && seq == prev_seq.wrapping_add(1)
            && self.last_seq == prev_seq
            && self.last_clean
            && clean;
        if !consecutive {
            self.seed(seq, clean, true);
            return self.stats();
        }

        if self.forecast_valid {
            self.forecast_checks = self.forecast_checks.wrapping_add(1);
            if self.forecast_rng == (rng & 0xFFFF00) && self.forecast_div == div {
                self.forecast_hits = self.forecast_hits.wrapping_add(1);
            } else {
                self.seed(seq, clean, true);
                return self.stats();
            }
        }

        let Some((first, gap)) = infer_vblank(prev_rng, rng) else {
            self.seed(seq, clean, true);
            return self.stats();
        };
        let div_step = div.wrapping_sub(prev_div);
        if !matches!(div_step, 0x12 | 0x13) {
            self.seed(seq, clean, true);
            return self.stats();
        }

        let mut write = 0usize;
        for i in 0..self.count {
            let candidate = self.candidates[i];
            if next_div_step(candidate.sample_sub) != div_step {
                continue;
            }
            let next_sub = next_sample_sub(candidate.sample_sub);
            let total = next_sub as u16 + candidate.offset_m;
            let predicted_first = div.wrapping_add((total / SUB_MOD) as u8);
            let first_sub = (total % SUB_MOD) as u8;
            if predicted_first != first || random_gap(first_sub) != gap {
                continue;
            }
            self.candidates[write] = Candidate {
                sample_sub: next_sub,
                offset_m: candidate.offset_m,
            };
            write += 1;
        }

        self.count = write;
        if self.count == 0 {
            self.seed(seq, clean, true);
            return self.stats();
        }

        self.transitions = self.transitions.wrapping_add(1);
        self.last_seq = seq;
        self.last_clean = clean;
        self.rebuild_forecast(rng, div);
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
    clean: bool,
) -> TrackerStats {
    unsafe { TRACKER.observe(prev_seq, prev_rng, prev_div, seq, rng, div, clean) }
}

pub fn stats() -> TrackerStats {
    unsafe { TRACKER.stats() }
}

pub fn mark_arm() {
    unsafe {
        TRACKER.arm_stats = TRACKER.stats();
        TRACKER.arm_stats.valid = TRACKER.arm_stats.transitions != 0;
    }
}

pub fn arm_stats() -> TrackerStats {
    unsafe { TRACKER.arm_stats }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn threshold_physics_are_stable() {
        assert_eq!(next_div_step(43), 0x12);
        assert_eq!(next_div_step(44), 0x13);
        assert_eq!(next_sample_sub(63), 19);
        assert_eq!(random_gap(52), 0);
        assert_eq!(random_gap(53), 1);
    }

    #[test]
    fn trace_0039_preinput_converges_to_known_fit_set() {
        let samples = [
            (0xCD9E00u32, 0x0Cu8),
            (0x036700u32, 0x1Eu8),
            (0x4B1F00u32, 0x30u8),
            (0xA6C400u32, 0x42u8),
            (0x135600u32, 0x55u8),
            (0x92D700u32, 0x67u8),
            (0x234400u32, 0x79u8),
            (0xC7A000u32, 0x8Cu8),
            (0x7DE900u32, 0x9Eu8),
        ];

        let mut tracker = Tracker {
            candidates: [EMPTY_CANDIDATE; MAX_CANDIDATES],
            count: 0,
            transitions: 0,
            last_seq: 0,
            last_clean: false,
            forecast_valid: false,
            forecast_rng: 0,
            forecast_div: 0,
            lock_prefix: 0,
            forecast_checks: 0,
            forecast_hits: 0,
            resets: 0,
            arm_stats: TrackerStats::default(),
        };

        tracker.seed(1410, true, false);
        for i in 1..samples.len() {
            let (prev_rng, prev_div) = samples[i - 1];
            let (rng, div) = samples[i];
            let stats = tracker.observe(
                1409 + i as u32,
                prev_rng,
                prev_div,
                1410 + i as u32,
                rng,
                div,
                true,
            );
            if i == samples.len() - 1 {
                assert_eq!(stats.fits, 16);
                assert_eq!(stats.sub_count, 4);
                assert_eq!(stats.lock_prefix, 3);
            }
        }
    }
}
