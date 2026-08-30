#[derive(Clone, Copy, Default)]
pub struct KFrameStats {
    pub valid: bool,
    pub phase20_known: bool,
    pub phase20: u8,
    pub total: u32,
    pub hits: u32,
    pub special_total: u32,
    pub special_hits: u32,
    pub frame_total: u32,
    pub frame_hits: u32,
    pub ignored: u32,
    pub last_k: u8,
    pub last_div_step: u8,
    pub last_gap: u8,
    pub last_frame: u8,
    pub last_special: bool,
}

static mut LIVE: KFrameStats = KFrameStats {
    valid: false, phase20_known: false, phase20: 0,
    total: 0, hits: 0, special_total: 0, special_hits: 0,
    frame_total: 0, frame_hits: 0, ignored: 0, last_k: 0,
    last_div_step: 0, last_gap: 0xFF, last_frame: 0, last_special: false,
};
static mut ARM: KFrameStats = KFrameStats {
    valid: false, phase20_known: false, phase20: 0,
    total: 0, hits: 0, special_total: 0, special_hits: 0,
    frame_total: 0, frame_hits: 0, ignored: 0, last_k: 0,
    last_div_step: 0, last_gap: 0xFF, last_frame: 0, last_special: false,
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

fn frame_next(prev: u8) -> Option<u8> {
    match prev {
        1 => Some(5),
        2..=5 => Some(prev - 1),
        _ => None,
    }
}

fn marker_k(k: u8) -> bool { k >= 0x1A }

fn allowed(special: bool, k: u8, div_step: u8, gap: u8) -> bool {
    if special {
        matches!((k, div_step, gap),
            (0x1A, 0x13, 1) |
            (0x1B, 0x12, 0) |
            (0x1B, 0x13, 0))
    } else {
        matches!((k, div_step, gap),
            (0x17, 0x13, 1) |
            (0x18, 0x12, 0) |
            (0x18, 0x12, 1) |
            (0x18, 0x13, 0) |
            (0x19, 0x12, 0))
    }
}

pub fn observe(prev_seq: u32, prev_rng: u32, prev_div: u8, prev_frame: u8,
               seq: u32, rng: u32, div: u8, frame: u8, usable: bool) -> KFrameStats {
    unsafe {
        LIVE.last_frame = frame;
        if !usable || prev_seq == 0 || seq != prev_seq.wrapping_add(1) {
            LIVE.ignored = LIVE.ignored.wrapping_add(1);
            return LIVE;
        }

        // hFrameCounter is diagnostic only.  The predictive class is calibrated
        // from K itself, so a fresh boot may begin at any frame/seq alignment.
        if let Some(expect) = frame_next(prev_frame) {
            if (1..=5).contains(&frame) {
                LIVE.frame_total = LIVE.frame_total.wrapping_add(1);
                if frame == expect { LIVE.frame_hits = LIVE.frame_hits.wrapping_add(1); }
            }
        }

        let div_step = div.wrapping_sub(prev_div);
        if !matches!(div_step, 0x12 | 0x13) {
            LIVE.ignored = LIVE.ignored.wrapping_add(1);
            return LIVE;
        }
        let Some((first, gap)) = infer_vblank(prev_rng, rng) else {
            LIVE.ignored = LIVE.ignored.wrapping_add(1);
            return LIVE;
        };
        let k = first.wrapping_sub(div);
        LIVE.last_k = k;
        LIVE.last_div_step = div_step;
        LIVE.last_gap = gap;

        // Trace 0040: all 26 K>=1A rows occurred at one seq mod20 residue,
        // and every occurrence of that residue was K=1A/1B.  Use the first
        // marker only to learn the residue; validation starts afterwards.
        if !LIVE.phase20_known {
            if marker_k(k) {
                LIVE.phase20 = (seq % 20) as u8;
                LIVE.phase20_known = true;
            }
            LIVE.ignored = LIVE.ignored.wrapping_add(1);
            return LIVE;
        }

        let special = (seq % 20) as u8 == LIVE.phase20;
        let hit = allowed(special, k, div_step, gap);
        LIVE.valid = true;
        LIVE.total = LIVE.total.wrapping_add(1);
        LIVE.hits = LIVE.hits.wrapping_add(u32::from(hit));
        if special {
            LIVE.special_total = LIVE.special_total.wrapping_add(1);
            LIVE.special_hits = LIVE.special_hits.wrapping_add(u32::from(hit));
        }
        LIVE.last_special = special;
        LIVE
    }
}

pub fn stats() -> KFrameStats { unsafe { LIVE } }
pub fn mark_arm() { unsafe { ARM = LIVE; } }
pub fn arm_stats() -> KFrameStats { unsafe { ARM } }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn support_sets_match_trace_0040_classes() {
        for c in [(0x1A,0x13,1),(0x1B,0x12,0),(0x1B,0x13,0)] {
            assert!(allowed(true,c.0,c.1,c.2));
        }
        for c in [(0x17,0x13,1),(0x18,0x12,0),(0x18,0x12,1),(0x18,0x13,0),(0x19,0x12,0)] {
            assert!(allowed(false,c.0,c.1,c.2));
        }
        assert!(marker_k(0x1A));
        assert!(marker_k(0x1B));
        assert!(!marker_k(0x19));
        assert!(!allowed(false,0x1B,0x12,0));
        assert!(!allowed(true,0x18,0x12,0));
    }

    #[test]
    fn standing_frame_cycle_is_1_5_4_3_2() {
        assert_eq!(frame_next(1),Some(5));
        assert_eq!(frame_next(5),Some(4));
        assert_eq!(frame_next(4),Some(3));
        assert_eq!(frame_next(3),Some(2));
        assert_eq!(frame_next(2),Some(1));
    }
}
