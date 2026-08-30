use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;
const WHITE: u32 = 0xFFFFFF;
const YELLOW: u32 = 0xFFFF00;
const MAX_A_TO_BATTLE_HOST_FRAMES: u32 = 120;
const ARM_SOURCE_GAME_A: u32 = 1;
const ARM_SOURCE_EXACT2F: u32 = 2;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_dvtrace_sample() -> u32;
    fn host_blue_dvtrace_set_arm_source(source: u32);
    fn host_blue_dvtrace_arm() -> u32;
    fn host_blue_dvtrace_finalize() -> u32;
    fn host_blue_dvtrace_seq() -> u32;
    fn host_blue_dvtrace_raw_dv() -> u32;
    fn host_blue_dvtrace_trigger_seq() -> u32;
    fn host_blue_dvtrace_battle_seq() -> u32;
    fn host_blue_dvtrace_save_slot() -> u32;
    fn host_blue_dvtrace_save_error() -> u32;
}

#[derive(Clone, Copy, Default)]
struct Snapshot {
    host_frame: u32,
    seq: u32,
    status: u32,
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
struct ResultInfo {
    battle: Snapshot,
    fixed_run_id: u32,
}

struct RunState {
    last_snapshot: Snapshot,
    normal_trigger: Option<Snapshot>,
    fixed_target: Option<Snapshot>,
    fixed_run_id: u32,
    result: Option<ResultInfo>,
    was_battle: bool,
}

static mut RUN_STATE: RunState = RunState {
    last_snapshot: Snapshot {
        host_frame: 0,
        seq: 0,
        status: 0,
        raw_dv: 0,
    },
    normal_trigger: None,
    fixed_target: None,
    fixed_run_id: 0,
    result: None,
    was_battle: false,
};

pub fn init_blue() {}

#[no_mangle]
pub extern "C" fn blue_capture_target(run_id: u32) -> u32 {
    unsafe {
        let s = RUN_STATE.last_snapshot;
        if s.all_ptrs_ok() && !s.in_mewtwo_battle() && s.seq != 0 {
            host_blue_dvtrace_set_arm_source(ARM_SOURCE_EXACT2F);
            if host_blue_dvtrace_arm() == 0 {
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
        raw_dv: unsafe { host_blue_dvtrace_raw_dv() } as u16,
    }
}

fn choose_fixed_run_id(state: &RunState, battle: Snapshot) -> Option<u32> {
    if let Some(s) = state.fixed_target {
        if battle.host_frame.wrapping_sub(s.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
            return Some(state.fixed_run_id);
        }
    }
    if let Some(s) = state.normal_trigger {
        if battle.host_frame.wrapping_sub(s.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
            return Some(0);
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

        // Blue A edges are sourced from hJoyPressed/hJoyHeld in pnp::input.
        // Re-arming on every game-recognized A means A2 overwrites A1.
        if !in_battle && pnp::is_just_pressed(Button::A) {
            host_blue_dvtrace_set_arm_source(ARM_SOURCE_GAME_A);
            if host_blue_dvtrace_arm() != 0 {
                state.normal_trigger = Some(current);
                state.result = None;
            }
        }

        if in_battle && !state.was_battle {
            let _ = host_blue_dvtrace_finalize();
            if let Some(fixed_run_id) = choose_fixed_run_id(state, current) {
                state.result = Some(ResultInfo {
                    battle: current,
                    fixed_run_id,
                });
            }
            state.fixed_target = None;
            state.normal_trigger = None;
        }
        state.was_battle = in_battle;

        pnp::println!(color = BLUE, "BLUE MEWTWO RNG v6");
        pnp::println!(
            color = if current.all_ptrs_ok() { GREEN } else { RED },
            "SYSTEM {}",
            if current.all_ptrs_ok() { "READY" } else { "PTR ERROR" }
        );

        if let Some(result) = state.result {
            let shiny = shiny_from_raw(result.battle.raw_dv);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "DV {:04X} {}",
                result.battle.raw_dv,
                if shiny { "SHINY" } else { "normal" }
            );

            let tq = host_blue_dvtrace_trigger_seq();
            let bq = host_blue_dvtrace_battle_seq();
            pnp::println!("A2->DV {}F", bq.wrapping_sub(tq));

            let slot = host_blue_dvtrace_save_slot();
            let err = host_blue_dvtrace_save_error();
            if slot != 0 {
                pnp::println!(color = GREEN, "CSV OK #{}", slot);
            } else {
                pnp::println!(color = RED, "CSV ERR {:08X}", err);
            }

            if result.fixed_run_id != 0 {
                pnp::println!("Exact2F run {}", result.fixed_run_id);
            }
            pnp::println!(color = YELLOW, "PRED LOCKED: learning");
        } else if state.fixed_target.is_some() {
            pnp::println!(color = GREEN, "EXACT2F ARMED");
        } else {
            pnp::println!("FINAL-A AUTO TRACK");
            pnp::println!("CSV AUTO-SAVE");
            pnp::println!(color = YELLOW, "PRED LOCKED: learning");
        }
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
