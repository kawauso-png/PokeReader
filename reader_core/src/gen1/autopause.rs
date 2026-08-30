use super::adaptive_model::AdaptiveStats;
use super::shiny_forecast::ForecastStats;

const MAX_CANDIDATES: u16 = 8;

#[derive(Clone, Copy, Default)]
pub struct AutoPauseStats {
    pub latched: bool,
    pub fired: bool,
    pub target_seq: u32,
    pub candidates: u16,
    pub shiny: u8,
    pub remain: u8,
    pub base: u8,
    pub residue20: u8,
}

static mut LIVE: AutoPauseStats = AutoPauseStats {
    latched: false,
    fired: false,
    target_seq: 0,
    candidates: 0,
    shiny: 0,
    remain: 0,
    base: 0,
    residue20: 0,
};
static mut FIRE_PENDING: bool = false;

fn clear_latch() {
    unsafe {
        LIVE.latched = false;
        LIVE.target_seq = 0;
        LIVE.candidates = 0;
        LIVE.shiny = 0;
        LIVE.remain = 0;
        LIVE.base = 0;
        LIVE.residue20 = 0;
    }
}

pub fn observe(seq: u32, adp: AdaptiveStats, fc: ForecastStats) -> AutoPauseStats {
    unsafe {
        if LIVE.fired {
            LIVE.remain = 0;
            return LIVE;
        }

        // Any loss of the 80/80 adaptive gate invalidates a future target.
        if !adp.ready || !fc.valid {
            clear_latch();
            return LIVE;
        }

        if LIVE.latched {
            // The target is tied to the learned K family and its 20F residue.
            // If either changes, discard it rather than pausing on stale math.
            if adp.base != LIVE.base
                || adp.residue20 != LIVE.residue20
                || seq > LIVE.target_seq
            {
                clear_latch();
            }
        }

        if !LIVE.latched
            && fc.next_horizon != 0
            && fc.next_candidates != 0
            && fc.next_candidates <= MAX_CANDIDATES
            && fc.next_shiny != 0
            && fc.target_seq > seq
        {
            LIVE.latched = true;
            LIVE.target_seq = fc.target_seq;
            LIVE.candidates = fc.next_candidates;
            LIVE.shiny = fc.next_shiny;
            LIVE.base = adp.base;
            LIVE.residue20 = adp.residue20;
        }

        if LIVE.latched {
            let delta = LIVE.target_seq.wrapping_sub(seq);
            LIVE.remain = core::cmp::min(delta, u8::MAX as u32) as u8;
            if seq == LIVE.target_seq {
                LIVE.latched = false;
                LIVE.fired = true;
                LIVE.remain = 0;
                FIRE_PENDING = true;
            }
        }
        LIVE
    }
}

pub fn take_fire() -> bool {
    unsafe {
        let v = FIRE_PENDING;
        FIRE_PENDING = false;
        v
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn adp(base: u8, residue20: u8) -> AdaptiveStats {
        AdaptiveStats {
            valid: true,
            ready: true,
            clean_tail: 80,
            base,
            base_hits: 70,
            residue20,
            marker_hits: 4,
            marker_total: 4,
            core_hits: 80,
            core_total: 80,
            sub_count: 4,
            div_lock: 16,
            last_k: base,
            last_step: 0x12,
            last_gap: 0,
        }
    }

    fn fc(target: u32, candidates: u16, shiny: u8) -> ForecastStats {
        ForecastStats {
            valid: true,
            phase_count: 4,
            now_candidates: 5,
            now_shiny: 0,
            next_horizon: 6,
            next_candidates: candidates,
            next_shiny: shiny,
            target_seq: target,
            overflow: false,
            scan_age: 0,
        }
    }

    #[test]
    fn compact_shiny_set_latches_and_fires_exactly_at_target() {
        unsafe { LIVE = AutoPauseStats::default(); FIRE_PENDING = false; }
        let a = adp(0x18, 7);
        let s = observe(100, a, fc(106, 7, 1));
        assert!(s.latched);
        assert_eq!(s.remain, 6);
        for seq in 101..106 {
            assert!(!observe(seq, a, fc(200, 7, 1)).fired);
            assert!(!take_fire());
        }
        let s = observe(106, a, fc(200, 7, 1));
        assert!(s.fired);
        assert!(take_fire());
        assert!(!take_fire());
    }

    #[test]
    fn wide_or_nonshiny_set_never_latches() {
        unsafe { LIVE = AutoPauseStats::default(); FIRE_PENDING = false; }
        let a = adp(0x18, 7);
        assert!(!observe(100, a, fc(105, 9, 1)).latched);
        assert!(!observe(101, a, fc(105, 8, 0)).latched);
    }

    #[test]
    fn model_change_cancels_stale_target() {
        unsafe { LIVE = AutoPauseStats::default(); FIRE_PENDING = false; }
        let a = adp(0x18, 7);
        assert!(observe(100, a, fc(106, 7, 1)).latched);
        let b = adp(0x0E, 3);
        assert!(!observe(101, b, ForecastStats { valid: true, ..ForecastStats::default() }).latched);
        assert!(!take_fire());
    }
}
