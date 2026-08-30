use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;
const WHITE: u32 = 0xFFFFFF;
const YELLOW: u32 = 0xFFFF00;
const MAX_A_TO_BATTLE_HOST_FRAMES: u32 = 120;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_dvtrace_sample() -> u32;
    fn host_blue_dvtrace_arm() -> u32;
    fn host_blue_dvtrace_finalize() -> u32;
    fn host_blue_dvtrace_seq() -> u32;
    fn host_blue_dvtrace_rng() -> u32;
    fn host_blue_dvtrace_div() -> u32;
    fn host_blue_dvtrace_raw_dv() -> u32;
    fn host_blue_dvtrace_trigger_seq() -> u32;
    fn host_blue_dvtrace_dvwrite_seq() -> u32;
    fn host_blue_dvtrace_battle_seq() -> u32;
    fn host_blue_dvtrace_dvwrite_rng() -> u32;
    fn host_blue_dvtrace_dvwrite_div() -> u32;
    fn host_blue_dvtrace_pre_rng() -> u32;
    fn host_blue_dvtrace_pre_div() -> u32;
    fn host_blue_dvtrace_d2_pair() -> u32;
    fn host_blue_dvtrace_add2_match() -> u32;
    fn host_blue_dvtrace_two_call_ok() -> u32;
    fn host_blue_dvtrace_solve() -> u32;
    fn host_blue_dvtrace_save_slot() -> u32;
    fn host_blue_dvtrace_save_error() -> u32;
}

#[derive(Clone, Copy, Default)]
struct Snapshot {
    host_frame: u32,
    seq: u32,
    status: u32,
    rng: u32,
    div: u8,
    raw_dv: u16,
}

impl Snapshot {
    fn all_ptrs_ok(self) -> bool {
        self.status & 0x07 == 0x07
    }

    fn in_mewtwo_battle(self) -> bool {
        self.status & (1 << 3) != 0
    }
}

#[derive(Clone, Copy, Default)]
struct ResultPair {
    trigger: Snapshot,
    battle: Snapshot,
    fixed_run_id: u32,
}

struct RunState {
    last_snapshot: Snapshot,
    a_pending: Option<Snapshot>,
    last_valid_2f: Option<Snapshot>,
    fixed_target: Option<Snapshot>,
    fixed_run_id: u32,
    result: Option<ResultPair>,
    was_battle: bool,
    valid_2f: u32,
    reject_1f: u32,
    completed_runs: u32,
}

static mut RUN_STATE: RunState = RunState {
    last_snapshot: Snapshot {
        host_frame: 0,
        seq: 0,
        status: 0,
        rng: 0,
        div: 0,
        raw_dv: 0,
    },
    a_pending: None,
    last_valid_2f: None,
    fixed_target: None,
    fixed_run_id: 0,
    result: None,
    was_battle: false,
    valid_2f: 0,
    reject_1f: 0,
    completed_runs: 0,
};

pub fn init_blue() {}

// Called by the C pause loop immediately before the audited exact-2F run.
#[no_mangle]
pub extern "C" fn blue_capture_target(run_id: u32) -> u32 {
    unsafe {
        let s = RUN_STATE.last_snapshot;
        if s.all_ptrs_ok() && !s.in_mewtwo_battle() && s.seq != 0 {
            let q = host_blue_dvtrace_arm();
            if q == 0 {
                return 0;
            }
            RUN_STATE.fixed_target = Some(s);
            RUN_STATE.fixed_run_id = run_id;
            RUN_STATE.result = None;
            return 1;
        }
    }
    0
}

fn shiny_from_raw(raw: u16) -> bool {
    let atk = ((raw >> 12) & 0xF) as u8;
    let def = ((raw >> 8) & 0xF) as u8;
    let spe = ((raw >> 4) & 0xF) as u8;
    let spc = (raw & 0xF) as u8;
    def == 10
        && spe == 10
        && spc == 10
        && matches!(atk, 2 | 3 | 6 | 7 | 10 | 11 | 14 | 15)
}

fn sample() -> Snapshot {
    let status = unsafe { host_blue_dvtrace_sample() };
    Snapshot {
        host_frame: unsafe { HOST_FRAME },
        seq: unsafe { host_blue_dvtrace_seq() },
        status,
        rng: unsafe { host_blue_dvtrace_rng() },
        div: unsafe { host_blue_dvtrace_div() } as u8,
        raw_dv: unsafe { host_blue_dvtrace_raw_dv() } as u16,
    }
}

fn draw_snapshot(label: &str, s: Snapshot) {
    let add = ((s.rng >> 16) & 0xFF) as u8;
    let sub = ((s.rng >> 8) & 0xFF) as u8;
    let frame = (s.rng & 0xFF) as u8;
    pnp::println!("{} H{} Q{} R{:02X}{:02X}", label, s.host_frame, s.seq, add, sub);
    pnp::println!("  F{:02X} D{:02X}", frame, s.div);
}

fn draw_rng(label: &str, rng: u32, div: u8) {
    let add = ((rng >> 16) & 0xFF) as u8;
    let sub = ((rng >> 8) & 0xFF) as u8;
    let frame = (rng & 0xFF) as u8;
    pnp::println!("{} R{:02X}{:02X} F{:02X} D{:02X}", label, add, sub, frame, div);
}

fn choose_trigger(state: &RunState, battle: Snapshot) -> Option<(Snapshot, u32)> {
    if let Some(s) = state.fixed_target {
        if battle.host_frame.wrapping_sub(s.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
            return Some((s, state.fixed_run_id));
        }
    }
    if let Some(s) = state.last_valid_2f {
        if battle.host_frame.wrapping_sub(s.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
            return Some((s, 0));
        }
    }
    if let Some(s) = state.a_pending {
        if battle.host_frame.wrapping_sub(s.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
            return Some((s, 0));
        }
    }
    None
}

pub fn run_frame() {
    pnp::set_print_max_len(31);
    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
    }
    let current = sample();

    unsafe {
        let state = &mut RUN_STATE;
        state.last_snapshot = current;
        let in_battle = current.in_mewtwo_battle();

        // Ordinary A calibration: arm the DV logger on the fresh physical A
        // edge. Exact-2F runs are armed separately by blue_capture_target().
        if !in_battle && pnp::is_just_pressed(Button::A) {
            let _ = host_blue_dvtrace_arm();
            state.a_pending = Some(current);
            state.result = None;
        } else if !in_battle {
            if let Some(start) = state.a_pending {
                if current.host_frame == start.host_frame.wrapping_add(1) {
                    if pnp::is_pressing(Button::A) {
                        state.last_valid_2f = Some(start);
                        state.valid_2f = state.valid_2f.wrapping_add(1);
                    } else {
                        state.reject_1f = state.reject_1f.wrapping_add(1);
                    }
                }
                // Keep a_pending as the ordinary-A trigger until battle or a
                // generous timeout; it is also useful when the human holds A
                // for longer than exactly two displayed frames.
                if current.host_frame.wrapping_sub(start.host_frame) > MAX_A_TO_BATTLE_HOST_FRAMES {
                    state.a_pending = None;
                }
            }
        }

        if in_battle && !state.was_battle {
            let _ = host_blue_dvtrace_finalize();
            if let Some((trigger, fixed_run_id)) = choose_trigger(state, current) {
                state.result = Some(ResultPair {
                    trigger,
                    battle: current,
                    fixed_run_id,
                });
                state.completed_runs = state.completed_runs.wrapping_add(1);
            }
            state.fixed_target = None;
            state.last_valid_2f = None;
            state.a_pending = None;
        }
        state.was_battle = in_battle;

        let add = ((current.rng >> 16) & 0xFF) as u8;
        let sub = ((current.rng >> 8) & 0xFF) as u8;
        let frame = (current.rng & 0xFF) as u8;
        let fixed = pnp::blue_fixed_state();

        pnp::println!(color = BLUE, "BLUE MEWTWO HUNT LAB v2");
        pnp::println!(
            color = if current.all_ptrs_ok() { GREEN } else { RED },
            "PTR3 {} H{} Q{}",
            if current.all_ptrs_ok() { "OK" } else { "NO" },
            current.host_frame,
            current.seq
        );
        pnp::println!("NOW R{:02X}{:02X} F{:02X} D{:02X}", add, sub, frame, current.div);
        pnp::println!(
            "FIX id{} rem{} p{} a{}",
            pnp::blue_fixed_run_id(),
            fixed.remaining,
            if fixed.pending { 1 } else { 0 },
            if fixed.physical_a { 1 } else { 0 }
        );
        pnp::println!("2F ok{} / 1F rej{}", state.valid_2f, state.reject_1f);

        if let Some(result) = state.result {
            let shiny = shiny_from_raw(result.battle.raw_dv);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "RUN{} DV {:04X} {}",
                state.completed_runs,
                result.battle.raw_dv,
                if shiny { "SHINY" } else { "normal" }
            );
            draw_snapshot("T", result.trigger);
            draw_snapshot("B", result.battle);

            let tq = host_blue_dvtrace_trigger_seq();
            let wq = host_blue_dvtrace_dvwrite_seq();
            let bq = host_blue_dvtrace_battle_seq();
            if wq != 0 {
                pnp::println!(color = GREEN, "DVWRITE Q{} lag{}", wq, bq.wrapping_sub(wq));
                draw_rng(
                    "DW",
                    host_blue_dvtrace_dvwrite_rng(),
                    host_blue_dvtrace_dvwrite_div() as u8,
                );
                draw_rng(
                    "PRE",
                    host_blue_dvtrace_pre_rng(),
                    host_blue_dvtrace_pre_div() as u8,
                );
            } else {
                pnp::println!(color = RED, "DVWRITE not isolated");
            }

            let pair = host_blue_dvtrace_d2_pair();
            pnp::println!(
                "DV2 rDIV {:02X}/{:02X} A2{}",
                (pair >> 8) & 0xFF,
                pair & 0xFF,
                if host_blue_dvtrace_add2_match() != 0 { "Y" } else { "N" }
            );

            if host_blue_dvtrace_two_call_ok() != 0 {
                let s = host_blue_dvtrace_solve();
                let d1 = (s >> 24) & 0xFF;
                let d2 = (s >> 16) & 0xFF;
                let gap = (s >> 8) & 0xFF;
                pnp::println!(color = GREEN, "2CALL YES d{:02X}>{:02X} g{}", d1, d2, gap);
                pnp::println!("flags c{}{} q{}{}", (s >> 3) & 1, (s >> 2) & 1, (s >> 1) & 1, s & 1);
            } else {
                pnp::println!(color = YELLOW, "2CALL NO: earlier calls same frame");
            }

            let slot = host_blue_dvtrace_save_slot();
            let err = host_blue_dvtrace_save_error();
            pnp::println!(
                color = if slot != 0 { GREEN } else { RED },
                "CSV {} slot{} e{:08X}",
                if slot != 0 { "OK" } else { "ERR" },
                slot,
                err
            );
            pnp::println!("trace Q{} -> Q{} FID{}", tq, bq, result.fixed_run_id);
        } else if state.fixed_target.is_some() {
            pnp::println!(color = GREEN, "Exact2F target captured");
        } else {
            pnp::println!("CAL: stand before Mewtwo");
            pnp::println!("Press A normally -> battle");
        }

        pnp::println!(color = YELLOW, "HUNT LOCKED: DV call learning");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shiny_rule() {
        for atk in [2u16, 3, 6, 7, 10, 11, 14, 15] {
            assert!(shiny_from_raw((atk << 12) | 0x0AAA));
        }
        assert!(!shiny_from_raw(0x1AAA));
        assert!(!shiny_from_raw(0x2BAA));
    }
}
