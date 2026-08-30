use super::adaptive_model::AdaptiveStats;
use super::shiny_forecast::ForecastStats;

const MAX_NOW_CANDIDATES: u16 = 12;

#[derive(Clone, Copy, Default)]
pub struct AutoPauseStats {
    pub enabled: bool,
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
    enabled: false,
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

fn reset_all(enabled: bool) {
    unsafe {
        LIVE = AutoPauseStats { enabled, ..AutoPauseStats::default() };
        FIRE_PENDING = false;
    }
}

pub fn observe(
    seq: u32,
    adp: AdaptiveStats,
    fc: ForecastStats,
    enabled: bool,
) -> AutoPauseStats {
    unsafe {
        if !enabled {
            reset_all(false);
            return LIVE;
        }
        LIVE.enabled = true;

        if LIVE.fired {
            LIVE.remain = 0;
            return LIVE;
        }

        // v7.7.1 deliberately stops on the CURRENT sampled state. The top hook
        // has already observed this GB frame, while the bottom hook has not yet
        // let another emulated frame through. This avoids future-branch growth.
        if !adp.ready || !fc.valid {
            LIVE.latched = false;
            LIVE.remain = 0;
            return LIVE;
        }

        if fc.now_candidates != 0
            && fc.now_candidates <= MAX_NOW_CANDIDATES
            && fc.now_shiny != 0
        {
            LIVE.latched = false;
            LIVE.fired = true;
            LIVE.target_seq = seq;
            LIVE.candidates = fc.now_candidates;
            LIVE.shiny = fc.now_shiny;
            LIVE.remain = 0;
            LIVE.base = adp.base;
            LIVE.residue20 = adp.residue20;
            FIRE_PENDING = true;
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

    fn fc(now_candidates: u16, now_shiny: u8) -> ForecastStats {
        ForecastStats {
            valid: true,
            phase_count: 4,
            now_candidates,
            now_shiny,
            next_horizon: 6,
            next_candidates: 40,
            next_shiny: 1,
            target_seq: 106,
            overflow: false,
            scan_age: 0,
        }
    }

    #[test]
    fn disabled_mode_never_fires() {
        unsafe { reset_all(false); }
        let s = observe(100, adp(0x18, 7), fc(6, 1), false);
        assert!(!s.enabled);
        assert!(!s.fired);
        assert!(!take_fire());
    }

    #[test]
    fn current_compact_shiny_set_fires_immediately() {
        unsafe { reset_all(false); }
        let s = observe(100, adp(0x18, 7), fc(6, 1), true);
        assert!(s.enabled);
        assert!(s.fired);
        assert_eq!(s.target_seq, 100);
        assert_eq!(s.candidates, 6);
        assert_eq!(s.shiny, 1);
        assert!(take_fire());
        assert!(!take_fire());
    }

    #[test]
    fn future_shiny_does_not_matter_when_now_is_not_shiny() {
        unsafe { reset_all(false); }
        let s = observe(100, adp(0x18, 7), fc(6, 0), true);
        assert!(!s.fired);
        assert!(!take_fire());
    }

    #[test]
    fn current_set_over_cap_does_not_fire() {
        unsafe { reset_all(false); }
        let s = observe(100, adp(0x18, 7), fc(13, 1), true);
        assert!(!s.fired);
        assert!(!take_fire());
    }
}
