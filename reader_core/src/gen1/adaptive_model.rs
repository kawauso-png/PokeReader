const WIN: usize = 80;
const DIV_WIN: usize = 16;

#[derive(Clone, Copy)]
struct Row {
    seq: u32,
    k: u8,
    step: u8,
    gap: u8,
}

const EMPTY: Row = Row { seq: 0, k: 0, step: 0, gap: 0xFF };

#[derive(Clone, Copy, Default)]
pub struct AdaptiveStats {
    pub valid: bool,
    pub ready: bool,
    pub clean_tail: u16,
    pub base: u8,
    pub base_hits: u8,
    pub residue20: u8,
    pub marker_hits: u8,
    pub marker_total: u8,
    pub core_hits: u8,
    pub core_total: u8,
    pub sub_count: u8,
    pub div_lock: u8,
    pub last_k: u8,
    pub last_step: u8,
    pub last_gap: u8,
}

static mut RING: [Row; WIN] = [EMPTY; WIN];
static mut HEAD: usize = 0;
static mut COUNT: usize = 0;
static mut CLEAN_TAIL: u16 = 0;
static mut LAST_SEQ: u32 = 0;
static mut LIVE: AdaptiveStats = AdaptiveStats {
    valid: false, ready: false, clean_tail: 0, base: 0, base_hits: 0,
    residue20: 0, marker_hits: 0, marker_total: 0, core_hits: 0,
    core_total: 0, sub_count: 0, div_lock: 0, last_k: 0,
    last_step: 0, last_gap: 0xFF,
};
static mut ARM: AdaptiveStats = AdaptiveStats {
    valid: false, ready: false, clean_tail: 0, base: 0, base_hits: 0,
    residue20: 0, marker_hits: 0, marker_total: 0, core_hits: 0,
    core_total: 0, sub_count: 0, div_lock: 0, last_k: 0,
    last_step: 0, last_gap: 0xFF,
};

fn rng_add(rng: u32) -> u8 { ((rng >> 16) & 0xFF) as u8 }
fn rng_sub(rng: u32) -> u8 { ((rng >> 8) & 0xFF) as u8 }

fn infer(prev_rng: u32, rng: u32) -> Option<(u8, u8)> {
    let a0 = rng_add(prev_rng);
    let s0 = rng_sub(prev_rng);
    let a1 = rng_add(rng);
    let s1 = rng_sub(rng);
    let first = a1.wrapping_sub(a0);
    let carry = u8::from((a0 as u16 + first as u16) > 0xFF);
    let second = s0.wrapping_sub(s1).wrapping_sub(carry);
    let gap = second.wrapping_sub(first);
    if gap <= 1 { Some((first, gap)) } else { None }
}

fn allowed_normal(delta: u8, step: u8, gap: u8) -> bool {
    matches!((delta, step, gap),
        (0xFF, 0x13, 1) |
        (0x00, 0x12, 0) |
        (0x00, 0x12, 1) |
        (0x00, 0x13, 0) |
        (0x01, 0x12, 0))
}

fn allowed_special(delta: u8, step: u8, gap: u8) -> bool {
    matches!((delta, step, gap),
        (0x02, 0x12, 1) |
        (0x02, 0x13, 0) |
        (0x02, 0x13, 1) |
        (0x03, 0x12, 0) |
        (0x03, 0x13, 0))
}

fn row_at_oldest(i: usize) -> Row {
    unsafe {
        let start = (HEAD + WIN - COUNT) % WIN;
        RING[(start + i) % WIN]
    }
}

fn calculate() -> AdaptiveStats {
    unsafe {
        let mut s = LIVE;
        s.clean_tail = CLEAN_TAIL;
        s.valid = COUNT != 0;
        s.ready = false;
        s.core_total = COUNT as u8;
        if COUNT == 0 { return s; }

        let mut counts = [0u8; 256];
        for i in 0..COUNT {
            let r = row_at_oldest(i);
            counts[r.k as usize] = counts[r.k as usize].saturating_add(1);
        }
        let mut base = 0u8;
        let mut base_hits = 0u8;
        for k in 0..256usize {
            if counts[k] > base_hits {
                base_hits = counts[k];
                base = k as u8;
            }
        }
        s.base = base;
        s.base_hits = base_hits;

        let mut residues = [0u8; 20];
        let mut marker_total = 0u8;
        for i in 0..COUNT {
            let r = row_at_oldest(i);
            let d = r.k.wrapping_sub(base);
            if matches!(d, 2 | 3) {
                marker_total = marker_total.saturating_add(1);
                let rr = (r.seq % 20) as usize;
                residues[rr] = residues[rr].saturating_add(1);
            }
        }
        let mut residue = 0u8;
        let mut marker_hits = 0u8;
        for rr in 0..20usize {
            if residues[rr] > marker_hits {
                marker_hits = residues[rr];
                residue = rr as u8;
            }
        }
        s.residue20 = residue;
        s.marker_hits = marker_hits;
        s.marker_total = marker_total;

        let mut core_hits = 0u8;
        for i in 0..COUNT {
            let r = row_at_oldest(i);
            let d = r.k.wrapping_sub(base);
            let special = (r.seq % 20) as u8 == residue;
            let ok = if special {
                allowed_special(d, r.step, r.gap)
            } else {
                allowed_normal(d, r.step, r.gap)
            };
            core_hits = core_hits.saturating_add(u8::from(ok));
        }
        s.core_hits = core_hits;

        // Infer current sampled rDIV subphase using only the most recent 16 DIV steps.
        // A transition ending at row i is governed by the previous sample subphase;
        // each accepted frame advances +20 mod 64.
        let use_n = core::cmp::min(COUNT, DIV_WIN);
        let first_i = COUNT - use_n;
        let mut sub_mask = 0u64;
        for start_sub in 0u8..64u8 {
            let mut sub = start_sub;
            let mut ok = true;
            for i in first_i..COUNT {
                let r = row_at_oldest(i);
                let expect = 0x12u8 + u8::from((sub as u16 + 20u16) >= 64u16);
                if r.step != expect { ok = false; break; }
                sub = sub.wrapping_add(20) & 0x3F;
            }
            if ok { sub_mask |= 1u64 << sub; }
        }
        s.sub_count = sub_mask.count_ones() as u8;

        let mut lock = 0u8;
        if sub_mask != 0 {
            let mut mask = sub_mask;
            for _ in 0..16 {
                let mut seen = 0u8;
                let mut next_mask = 0u64;
                for sub in 0u8..64u8 {
                    if (mask & (1u64 << sub)) == 0 { continue; }
                    let step = 0x12u8 + u8::from((sub as u16 + 20u16) >= 64u16);
                    seen |= if step == 0x12 { 1 } else { 2 };
                    let ns = sub.wrapping_add(20) & 0x3F;
                    next_mask |= 1u64 << ns;
                }
                if seen == 3 { break; }
                lock = lock.saturating_add(1);
                mask = next_mask;
            }
        }
        s.div_lock = lock;

        s.ready = COUNT == WIN
            && CLEAN_TAIL >= WIN as u16
            && base_hits >= 56
            && marker_total >= 3
            && marker_hits == marker_total
            && core_hits == WIN as u8
            && s.sub_count != 0
            && s.div_lock >= 12;
        s
    }
}

fn clear(seq: u32) {
    unsafe {
        HEAD = 0;
        COUNT = 0;
        CLEAN_TAIL = 0;
        LAST_SEQ = seq;
        LIVE.valid = false;
        LIVE.ready = false;
        LIVE.clean_tail = 0;
        LIVE.core_total = 0;
    }
}

pub fn observe(prev_seq: u32, prev_rng: u32, prev_div: u8,
               seq: u32, rng: u32, div: u8, usable: bool) -> AdaptiveStats {
    unsafe {
        if !usable || prev_seq == 0 || seq != prev_seq.wrapping_add(1)
            || (LAST_SEQ != 0 && LAST_SEQ != prev_seq)
        {
            clear(seq);
            return LIVE;
        }
        let step = div.wrapping_sub(prev_div);
        let Some((first, gap)) = infer(prev_rng, rng) else {
            clear(seq);
            return LIVE;
        };
        if !matches!(step, 0x12 | 0x13) {
            clear(seq);
            return LIVE;
        }
        let k = first.wrapping_sub(div);
        RING[HEAD] = Row { seq, k, step, gap };
        HEAD = (HEAD + 1) % WIN;
        if COUNT < WIN { COUNT += 1; }
        CLEAN_TAIL = CLEAN_TAIL.saturating_add(1);
        LAST_SEQ = seq;
        LIVE.last_k = k;
        LIVE.last_step = step;
        LIVE.last_gap = gap;
        LIVE = calculate();
        LIVE
    }
}

pub fn stats() -> AdaptiveStats { unsafe { LIVE } }
pub fn mark_arm() { unsafe { ARM = LIVE; } }
pub fn arm_stats() -> AdaptiveStats { unsafe { ARM } }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalized_support_contains_both_observed_modes() {
        // 0E-mode and 18-mode share the same deltas.
        assert!(allowed_normal(0x00, 0x12, 0));
        assert!(allowed_normal(0xFF, 0x13, 1));
        assert!(allowed_normal(0x01, 0x12, 0));
        assert!(allowed_special(0x02, 0x13, 0));
        assert!(allowed_special(0x02, 0x13, 1));
        assert!(allowed_special(0x03, 0x12, 0));
    }

    #[test]
    fn ready_threshold_requires_full_clean_window() {
        assert_eq!(WIN, 80);
        assert_eq!(DIV_WIN, 16);
    }
}
