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
    fn host_blue_dvtrace_rng() -> u32;
    fn host_blue_dvtrace_div() -> u32;
    fn host_blue_dvtrace_raw_dv() -> u32;
    fn host_blue_dvtrace_trigger_seq() -> u32;
    fn host_blue_dvtrace_physical_a_seq() -> u32;
    fn host_blue_dvtrace_game_a_seq() -> u32;
    fn host_blue_dvtrace_battle_seq() -> u32;
    fn host_blue_dvtrace_arm_source() -> u32;
    fn host_blue_dvtrace_save_slot() -> u32;
    fn host_blue_dvtrace_save_error() -> u32;

    fn host_blue_gbrelease_reset();
    fn host_blue_gbrelease_mark();
    fn host_blue_gbrelease_append_csv(
        slot: u32,
        pre_seq: u32,
        pre_rng: u32,
        pre_div: u32,
        phase_offset: u32,
        dvhigh_first_div: u32,
    ) -> u32;
    fn host_blue_gbrelease_seq() -> u32;
    fn host_blue_gbrelease_valid() -> u32;
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
struct ResultInfo {
    battle: Snapshot,
    physical_start: Option<Snapshot>,
    physical_release: Option<Snapshot>,
    gb_release: Option<Snapshot>,
    final_pre: Option<Snapshot>,
    phase_offset: u8,
    dvhigh_first_div: u8,
    phase_valid: bool,
    fixed_run_id: u32,
    source: u32,
}

struct RunState {
    last_snapshot: Snapshot,
    normal_trigger: Option<Snapshot>,
    physical_start: Option<Snapshot>,
    physical_release: Option<Snapshot>,
    gb_release: Option<Snapshot>,
    fixed_target: Option<Snapshot>,
    fixed_run_id: u32,
    result: Option<ResultInfo>,
    was_battle: bool,
    was_physical_a: bool,
    was_game_a_held: bool,
    saw_game_a_held: bool,
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
    normal_trigger: None,
    physical_start: None,
    physical_release: None,
    gb_release: None,
    fixed_target: None,
    fixed_run_id: 0,
    result: None,
    was_battle: false,
    was_physical_a: false,
    was_game_a_held: false,
    saw_game_a_held: false,
};

// Intentionally empty. The abandoned FastRNG experiment created a raw SVC
// thread at startup and froze the VC opening. v7.3.2 keeps the v7.2 safety
// property: no Blue-specific work is started here.
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
        rng: unsafe { host_blue_dvtrace_rng() },
        div: unsafe { host_blue_dvtrace_div() } as u8,
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

// For the second DV BattleRandom, hRandomAdd enters as the raw low byte and the
// normal battle path enters Random_ with carry=1. Therefore its first rDIV byte
// is high-low-1. Subtracting the immediately preceding sampled DIV gives the
// unfolded final-frame phase class modulo 256. Existing traces 0011-0020 fall
// into decimal offsets 90, 91 or 94.
fn microphase(raw: u16, pre_div: u8) -> (u8, u8) {
    let low = raw as u8;
    let high = (raw >> 8) as u8;
    let dvhigh_first_div = high.wrapping_sub(low).wrapping_sub(1);
    let phase_offset = dvhigh_first_div.wrapping_sub(pre_div);
    (phase_offset, dvhigh_first_div)
}

fn known_phase(phase: u8) -> bool {
    matches!(phase, 90 | 91 | 94)
}

pub fn run_frame() {
    pnp::set_print_max_len(31);
    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
    }
    let current = sample();

    unsafe {
        let state = &mut RUN_STATE;
        let previous = state.last_snapshot;
        state.last_snapshot = current;
        let in_battle = current.in_mewtwo_battle();

        if !in_battle {
            let physical_a = pnp::is_pressing(Button::A);
            let physical_edge = physical_a && !state.was_physical_a;
            let physical_release = !physical_a && state.was_physical_a;

            // Refresh the Game Boy-side hJoyPressed/hJoyHeld cache every host
            // sample. The edge itself remains diagnostic only.
            let game_edge = pnp::is_just_pressed(Button::A);
            let (_, game_held_raw) = pnp::blue_game_joy();
            let game_a_held = (game_held_raw & 0x01) != 0;

            if physical_edge {
                // VC Reset does not reload the 3GX process. Clear all marker
                // state at the new physical Final-A edge so no previous trial
                // can leak into the new CSV.
                host_blue_gbrelease_reset();
                host_blue_dvtrace_mark_physical_a();
                host_blue_dvtrace_set_arm_source(ARM_SOURCE_PHYSICAL_A);
                if host_blue_dvtrace_arm() != 0 {
                    state.normal_trigger = Some(current);
                    state.physical_start = Some(current);
                    state.physical_release = None;
                    state.gb_release = None;
                    state.saw_game_a_held = game_a_held;
                    state.result = None;
                }
            }

            if physical_release && state.physical_start.is_some() {
                state.physical_release = Some(current);
            }

            if game_edge {
                host_blue_dvtrace_mark_game_a();
            }

            // The first GB-side hJoyHeld.A 1->0 transition is the authoritative
            // release anchor. Critical path remains a tiny copy only.
            if state.physical_start.is_some() {
                if game_a_held {
                    state.saw_game_a_held = true;
                }
                if state.gb_release.is_none()
                    && state.saw_game_a_held
                    && state.was_game_a_held
                    && !game_a_held
                {
                    state.gb_release = Some(current);
                    host_blue_gbrelease_mark();
                }
            }

            state.was_physical_a = physical_a;
            state.was_game_a_held = game_a_held;
        } else {
            state.was_physical_a = pnp::is_pressing(Button::A);
        }

        if in_battle && !state.was_battle {
            let finalized = host_blue_dvtrace_finalize();
            if finalized != 0 {
                // `previous` is the ordinary host sample immediately before the
                // battle/DV sample. Classification and SD I/O happen only now,
                // after the Mewtwo DVs have already been generated.
                let pre_ok = previous.seq != 0 && previous.seq.wrapping_add(1) == current.seq;
                let (phase_offset, dvhigh_first_div) = if pre_ok {
                    microphase(current.raw_dv, previous.div)
                } else {
                    (0, 0)
                };

                let slot = host_blue_dvtrace_save_slot();
                if slot != 0 && pre_ok {
                    let _ = host_blue_gbrelease_append_csv(
                        slot,
                        previous.seq,
                        previous.rng,
                        previous.div as u32,
                        phase_offset as u32,
                        dvhigh_first_div as u32,
                    );
                }

                let fixed_run_id = if state.fixed_target.is_some() {
                    state.fixed_run_id
                } else {
                    0
                };
                state.result = Some(ResultInfo {
                    battle: current,
                    physical_start: state.physical_start,
                    physical_release: state.physical_release,
                    gb_release: state.gb_release,
                    final_pre: if pre_ok { Some(previous) } else { None },
                    phase_offset,
                    dvhigh_first_div,
                    phase_valid: pre_ok,
                    fixed_run_id,
                    source: host_blue_dvtrace_arm_source(),
                });
            }
            state.fixed_target = None;
            state.normal_trigger = None;
        }
        state.was_battle = in_battle;

        pnp::println!(color = BLUE, "BLUE MEWTWO RNG v7.3.2 SAFE");
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
                    pnp::println!("PHYREL->DV {}F", bq.wrapping_sub(release.seq));
                }
            }

            if let Some(gb_release) = result.gb_release {
                if bq >= gb_release.seq {
                    let delta = bq.wrapping_sub(gb_release.seq);
                    pnp::println!(
                        color = if delta == 9 { GREEN } else { RED },
                        "GBREL->DV {}F",
                        delta
                    );
                }
            } else {
                pnp::println!(color = RED, "GB RELEASE MISSED");
            }

            if result.phase_valid {
                pnp::println!(
                    color = if known_phase(result.phase_offset) { GREEN } else { YELLOW },
                    "PHASE +{} D{:02X}",
                    result.phase_offset,
                    result.dvhigh_first_div
                );
                if let Some(pre) = result.final_pre {
                    pnp::println!("PRE Q{} DIV {:02X}", pre.seq, pre.div);
                }
            } else {
                pnp::println!(color = RED, "PHASE PRE MISSED");
            }

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

            let mark_ok = host_blue_gbrelease_valid();
            let mark_seq = host_blue_gbrelease_seq();
            pnp::println!(
                color = if mark_ok != 0 { GREEN } else { RED },
                "GBMARK {} Q{}",
                if mark_ok != 0 { "OK" } else { "MISS" },
                mark_seq
            );

            if result.fixed_run_id != 0 {
                pnp::println!("Exact2F run {}", result.fixed_run_id);
            }
            pnp::println!(color = YELLOW, "SAFE / POSTCLASS");
        } else if state.fixed_target.is_some() {
            pnp::println!(color = GREEN, "EXACT2F ARMED");
        } else {
            pnp::println!("FINAL-A AUTO TRACK");
            pnp::println!("GB RELEASE 9F ANCHOR");
            pnp::println!("NO THREAD / NO FAST HOOK");
            pnp::println!(color = YELLOW, "PRED LOCKED: phase learn");
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

    #[test]
    fn known_microphase_regressions() {
        // Trace 0011: raw B67F, final-pre DIV DC -> +90.
        assert_eq!(microphase(0xB67F, 0xDC), (90, 0x36));
        // Trace 0013: raw 746E, final-pre DIV A7 -> +94.
        assert_eq!(microphase(0x746E, 0xA7), (94, 0x05));
        // Trace 0020: raw AD5D, final-pre DIV F4 -> +91.
        assert_eq!(microphase(0xAD5D, 0xF4), (91, 0x4F));
        assert!(known_phase(90));
        assert!(known_phase(91));
        assert!(known_phase(94));
        assert!(!known_phase(92));
    }
}
