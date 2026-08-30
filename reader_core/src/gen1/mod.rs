use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;
const WHITE: u32 = 0xFFFFFF;
const YELLOW: u32 = 0xFFFF00;

const ARM_SOURCE_GAME_A: u32 = 1;
const ARM_SOURCE_EXACT2F: u32 = 2;
const ARM_SOURCE_PHYSICAL_A: u32 = 3;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_dvtrace_sample() -> u32;
    fn host_blue_dvtrace_set_arm_source(source: u32);
    fn host_blue_dvtrace_arm() -> u32;
    fn host_blue_dvtrace_finalize() -> u32;
    fn host_blue_dvtrace_mark_physical_a();
    fn host_blue_dvtrace_mark_game_a();
    fn host_blue_dvtrace_seq() -> u32;
    fn host_blue_dvtrace_raw_dv() -> u32;
    fn host_blue_dvtrace_trigger_seq() -> u32;
    fn host_blue_dvtrace_physical_a_seq() -> u32;
    fn host_blue_dvtrace_game_a_seq() -> u32;
    fn host_blue_dvtrace_battle_seq() -> u32;
    fn host_blue_dvtrace_arm_source() -> u32;
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
    physical_start: Option<Snapshot>,
    physical_release: Option<Snapshot>,
    fixed_run_id: u32,
    source: u32,
}

struct RunState {
    last_snapshot: Snapshot,
    normal_trigger: Option<Snapshot>,
    physical_start: Option<Snapshot>,
    physical_release: Option<Snapshot>,
    fixed_target: Option<Snapshot>,
    fixed_run_id: u32,
    result: Option<ResultInfo>,
    was_battle: bool,
    was_physical_a: bool,
}

static mut RUN_STATE: RunState = RunState {
    last_snapshot: Snapshot {
        host_frame: 0,
        seq: 0,
        status: 0,
        raw_dv: 0,
    },
    normal_trigger: None,
    physical_start: None,
    physical_release: None,
    fixed_target: None,
    fixed_run_id: 0,
    result: None,
    was_battle: false,
    was_physical_a: false,
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

fn source_name(source: u32) -> &'static str {
    match source {
        ARM_SOURCE_GAME_A => "GAME",
        ARM_SOURCE_EXACT2F => "EXACT2F",
        ARM_SOURCE_PHYSICAL_A => "PHYS",
        _ => "UNKNOWN",
    }
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

        if !in_battle {
            // v7.1 rule: the physical A press is the authoritative start of a
            // new Mewtwo attempt. This is intentionally independent of the VC
            // reset lifecycle because the 3GX process survives a VC reset.
            let physical_a = pnp::is_pressing(Button::A);
            let physical_edge = physical_a && !state.was_physical_a;
            let physical_release = !physical_a && state.was_physical_a;

            if physical_edge {
                host_blue_dvtrace_mark_physical_a();
                host_blue_dvtrace_set_arm_source(ARM_SOURCE_PHYSICAL_A);
                if host_blue_dvtrace_arm() != 0 {
                    state.normal_trigger = Some(current);
                    state.physical_start = Some(current);
                    state.physical_release = None;
                    state.result = None;
                }
            }

            if physical_release && state.physical_start.is_some() {
                state.physical_release = Some(current);
            }

            state.was_physical_a = physical_a;

            // Keep the Game Boy hJoyPressed edge as diagnostic data only.
            // Do NOT re-arm from it: after a VC reset an old game_a_seq can
            // survive in the plugin process, while physical A is always tied
            // to the current human attempt. This also keeps every normal CSV
            // anchored to the same physical-press definition.
            if pnp::is_just_pressed(Button::A) {
                host_blue_dvtrace_mark_game_a();
            }
        } else {
            state.was_physical_a = pnp::is_pressing(Button::A);
        }

        if in_battle && !state.was_battle {
            let finalized = host_blue_dvtrace_finalize();
            if finalized != 0 {
                let fixed_run_id = if state.fixed_target.is_some() {
                    state.fixed_run_id
                } else {
                    0
                };
                state.result = Some(ResultInfo {
                    battle: current,
                    physical_start: state.physical_start,
                    physical_release: state.physical_release,
                    fixed_run_id,
                    source: host_blue_dvtrace_arm_source(),
                });
            }
            state.fixed_target = None;
            state.normal_trigger = None;
        }
        state.was_battle = in_battle;

        pnp::println!(color = BLUE, "BLUE MEWTWO RNG v7.1");
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
            let pq = host_blue_dvtrace_physical_a_seq();
            let gq = host_blue_dvtrace_game_a_seq();
            pnp::println!("SRC {}", source_name(result.source));
            if tq != 0 && bq >= tq {
                pnp::println!("TRIG->DV {}F", bq.wrapping_sub(tq));
            }
            if pq != 0 && bq >= pq {
                pnp::println!("PHY->DV {}F", bq.wrapping_sub(pq));
            }

            if let (Some(start), Some(release)) = (result.physical_start, result.physical_release) {
                if release.seq >= start.seq && bq >= release.seq {
                    pnp::println!("A HOLD {}F", release.seq.wrapping_sub(start.seq));
                    pnp::println!(color = GREEN, "REL->DV {}F", bq.wrapping_sub(release.seq));
                }
            }

            // A Game Boy edge is only valid for this attempt if it is not
            // older than the authoritative physical press. This filters stale
            // game_a_seq values left behind by a VC reset.
            if pq != 0 && gq >= pq && bq >= gq {
                pnp::println!("GAME->DV {}F", bq.wrapping_sub(gq));
            }

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
            pnp::println!(color = YELLOW, "PHY/RELEASE AUTH");
        } else if state.fixed_target.is_some() {
            pnp::println!(color = GREEN, "EXACT2F ARMED");
        } else {
            pnp::println!("FINAL-A AUTO TRACK");
            pnp::println!("VC RESET SAFE / PHY AUTH");
            pnp::println!("CSV AUTO-SAVE V7 COMPAT");
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

    #[test]
    fn source_names_are_stable() {
        assert_eq!(source_name(ARM_SOURCE_GAME_A), "GAME");
        assert_eq!(source_name(ARM_SOURCE_EXACT2F), "EXACT2F");
        assert_eq!(source_name(ARM_SOURCE_PHYSICAL_A), "PHYS");
    }
}
