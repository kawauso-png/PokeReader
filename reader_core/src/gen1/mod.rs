use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;
const WHITE: u32 = 0xFFFFFF;
const YELLOW: u32 = 0xFFFF00;
const MAX_A_TO_BATTLE_HOST_FRAMES: u32 = 120;

// Japanese Blue uses the same Gen-I Random_ path as pokered:
// two rDIV reads are 44 T-cycles apart inside Random_, and the first rDIV read
// of the second back-to-back BattleRandom is 480 T-cycles after the first one.
const RANDOM_DIV_READ_GAP_T: u16 = 44;
const DV_CALL_GAP_T: u16 = 480;
const DIV_T_CYCLES: u16 = 256;

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
    fn host_blue_dvtrace_add2_match() -> u32;
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

#[derive(Clone, Copy)]
struct ThreeCallAnalysis {
    valid: bool,
    frame_ticks: u16,
    configs: u16,
    call0_min: u8,
    call0_max: u8,
    dv1_min: u8,
    dv1_max: u8,
    dv2_min: u8,
    dv2_max: u8,
    dv2_tick_min: u16,
    dv2_tick_max: u16,
    pre_add_min: u8,
    pre_add_max: u8,
    pre_sub_min: u8,
    pre_sub_max: u8,
}

impl Default for ThreeCallAnalysis {
    fn default() -> Self {
        Self {
            valid: false,
            frame_ticks: 0,
            configs: 0,
            call0_min: 0xff,
            call0_max: 0,
            dv1_min: 0xff,
            dv1_max: 0,
            dv2_min: 0xff,
            dv2_max: 0,
            dv2_tick_min: u16::MAX,
            dv2_tick_max: 0,
            pre_add_min: 0xff,
            pre_add_max: 0,
            pre_sub_min: 0xff,
            pre_sub_max: 0,
        }
    }
}

struct RunState {
    last_snapshot: Snapshot,
    dialogue_a: Option<Snapshot>,
    dialogue_seen: bool,
    final_a: Option<Snapshot>,
    final_armed: bool,
    fixed_target: Option<Snapshot>,
    fixed_run_id: u32,
    result: Option<ResultPair>,
    was_battle: bool,
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
    dialogue_a: None,
    dialogue_seen: false,
    final_a: None,
    final_armed: false,
    fixed_target: None,
    fixed_run_id: 0,
    result: None,
    was_battle: false,
    completed_runs: 0,
};

pub fn init_blue() {}

fn reset_encounter_stage(state: &mut RunState) {
    state.dialogue_a = None;
    state.dialogue_seen = false;
    state.final_a = None;
    state.final_armed = false;
    state.fixed_target = None;
    state.fixed_run_id = 0;
}

// Called by the C pause loop immediately before the audited exact-2F run.
// v3 deliberately accepts this only after the first conversation A was seen:
// the exact run is the SECOND A, the one that actually starts the battle.
#[no_mangle]
pub extern "C" fn blue_capture_target(run_id: u32) -> u32 {
    unsafe {
        let s = RUN_STATE.last_snapshot;
        if RUN_STATE.dialogue_seen
            && !RUN_STATE.final_armed
            && s.all_ptrs_ok()
            && !s.in_mewtwo_battle()
            && s.seq != 0
        {
            let q = host_blue_dvtrace_arm();
            if q == 0 {
                return 0;
            }
            RUN_STATE.final_a = Some(s);
            RUN_STATE.final_armed = true;
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

fn add_of(rng: u32) -> u8 {
    ((rng >> 16) & 0xff) as u8
}

fn sub_of(rng: u32) -> u8 {
    ((rng >> 8) & 0xff) as u8
}

fn frame_of(rng: u32) -> u8 {
    (rng & 0xff) as u8
}

fn update_range_u8(min: &mut u8, max: &mut u8, value: u8) {
    *min = (*min).min(value);
    *max = (*max).max(value);
}

fn update_range_u16(min: &mut u16, max: &mut u16, value: u16) {
    *min = (*min).min(value);
    *max = (*max).max(value);
}

fn carry_add(a: u8, b: u8, carry: u8) -> u8 {
    ((a as u16 + b as u16 + carry as u16) > 0xff) as u8
}

fn sub_result(a: u8, b: u8, carry: u8) -> u8 {
    a.wrapping_sub(b).wrapping_sub(carry)
}

fn borrow_sub(a: u8, b: u8, carry: u8) -> u8 {
    ((a as u16) < b as u16 + carry as u16) as u8
}

fn occurrence_before(value: u8, start: u8, limit: u16) -> Option<u16> {
    let base = value.wrapping_sub(start) as u16;
    if base <= limit {
        Some(base)
    } else if base + 256 <= limit {
        Some(base + 256)
    } else {
        None
    }
}

// Solve the final host frame under the model supported by this trial:
//   one ordinary Random_ update + two back-to-back DV BattleRandom calls.
// The DV pair is solved with exact instruction timing. We do not assume the
// incoming carry to the ordinary call or first DV call; all valid branches are
// retained and reported as ranges.
fn analyze_three_call(
    pre_rng: u32,
    pre_div: u8,
    final_rng: u32,
    final_div: u8,
    raw_dv: u16,
) -> ThreeCallAnalysis {
    let mut out = ThreeCallAnalysis::default();
    let pre_add = add_of(pre_rng);
    let pre_sub = sub_of(pre_rng);
    let final_add = add_of(final_rng);
    let final_sub = sub_of(final_rng);
    let dv2 = (raw_dv >> 8) as u8; // CFD8 = second BattleRandom output
    let dv1 = raw_dv as u8; // CFD9 = first BattleRandom output

    if final_add != dv2 {
        return out;
    }

    // Consecutive presented GB frames advance DIV by 0x12/0x13 modulo 256,
    // i.e. 274/275 real rDIV ticks. The +256 restores the hidden wrap.
    out.frame_ticks = 256 + final_div.wrapping_sub(pre_div) as u16;

    for phase in 0..256u16 {
        let dv_call_delta = (phase + DV_CALL_GAP_T) / DIV_T_CYCLES;
        let phase2 = (phase + DV_CALL_GAP_T) % DIV_T_CYCLES;
        let y1_inc = ((phase + RANDOM_DIV_READ_GAP_T) / DIV_T_CYCLES) as u8;
        let y2_inc = ((phase2 + RANDOM_DIV_READ_GAP_T) / DIV_T_CYCLES) as u8;

        for first_in_carry in 0..=1u8 {
            for second_in_carry in 0..=1u8 {
                let x2 = dv2.wrapping_sub(dv1).wrapping_sub(second_in_carry);
                let x1 = x2.wrapping_sub(dv_call_delta as u8);
                let y1 = x1.wrapping_add(y1_inc);
                let y2 = x2.wrapping_add(y2_inc);

                let before_add = dv1.wrapping_sub(x1).wrapping_sub(first_in_carry);
                let add_carry1 = carry_add(before_add, x1, first_in_carry);
                let add_carry2 = carry_add(dv1, x2, second_in_carry);

                let after_first_sub = final_sub.wrapping_add(y2).wrapping_add(add_carry2);
                let before_sub = after_first_sub.wrapping_add(y1).wrapping_add(add_carry1);

                // Carry entering the second BattleRandom is exactly the borrow
                // flag left by the first Random_ SBC.
                if borrow_sub(before_sub, y1, add_carry1) != second_in_carry {
                    continue;
                }
                if sub_result(before_sub, y1, add_carry1) != after_first_sub {
                    continue;
                }
                if sub_result(after_first_sub, y2, add_carry2) != final_sub {
                    continue;
                }

                // Fit exactly one ordinary Random_ call from the preceding host
                // frame sample to the state immediately before the DV pair.
                for ordinary_in_carry in 0..=1u8 {
                    let x0 = before_add
                        .wrapping_sub(pre_add)
                        .wrapping_sub(ordinary_in_carry);
                    let add_carry0 = carry_add(pre_add, x0, ordinary_in_carry);

                    for y0_inc in 0..=1u8 {
                        let y0 = x0.wrapping_add(y0_inc);
                        if sub_result(pre_sub, y0, add_carry0) != before_sub {
                            continue;
                        }

                        let Some(dv1_tick) = occurrence_before(x1, pre_div, out.frame_ticks) else {
                            continue;
                        };
                        let dv2_tick = dv1_tick + dv_call_delta;
                        if dv2_tick > out.frame_ticks {
                            continue;
                        }
                        let Some(call0_tick) = occurrence_before(x0, pre_div, dv1_tick) else {
                            continue;
                        };
                        if call0_tick > dv1_tick {
                            continue;
                        }

                        out.valid = true;
                        out.configs = out.configs.saturating_add(1);
                        update_range_u8(&mut out.call0_min, &mut out.call0_max, x0);
                        update_range_u8(&mut out.dv1_min, &mut out.dv1_max, x1);
                        update_range_u8(&mut out.dv2_min, &mut out.dv2_max, x2);
                        update_range_u16(&mut out.dv2_tick_min, &mut out.dv2_tick_max, dv2_tick);
                        update_range_u8(&mut out.pre_add_min, &mut out.pre_add_max, before_add);
                        update_range_u8(&mut out.pre_sub_min, &mut out.pre_sub_max, before_sub);
                    }
                }
            }
        }
    }

    out
}

fn draw_snapshot(label: &str, s: Snapshot) {
    pnp::println!(
        "{} H{} Q{} R{:02X}{:02X} D{:02X}",
        label,
        s.host_frame,
        s.seq,
        add_of(s.rng),
        sub_of(s.rng),
        s.div
    );
}

fn draw_rng(label: &str, rng: u32, div: u8) {
    pnp::println!(
        "{} R{:02X}{:02X} F{:02X} D{:02X}",
        label,
        add_of(rng),
        sub_of(rng),
        frame_of(rng),
        div
    );
}

fn choose_trigger(state: &RunState, battle: Snapshot) -> Option<(Snapshot, u32)> {
    if let Some(s) = state.fixed_target {
        if battle.host_frame.wrapping_sub(s.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
            return Some((s, state.fixed_run_id));
        }
    }
    if let Some(s) = state.final_a {
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

        // A battle -> non-battle transition is a clean retry boundary.
        if state.was_battle && !in_battle {
            reset_encounter_stage(state);
            state.result = None;
        }

        // Mewtwo interaction has two distinct A presses:
        // A1 talks to Mewtwo and shows the cry/text; A2 actually starts battle.
        if !in_battle && pnp::is_just_pressed(Button::A) {
            if !state.dialogue_seen {
                state.dialogue_seen = true;
                state.dialogue_a = Some(current);
                state.result = None;
            } else if !state.final_armed {
                if host_blue_dvtrace_arm() != 0 {
                    state.final_a = Some(current);
                    state.final_armed = true;
                    state.result = None;
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
        }
        state.was_battle = in_battle;

        let fixed = pnp::blue_fixed_state();
        pnp::println!(color = BLUE, "BLUE MEWTWO HUNT LAB v3");
        pnp::println!(
            color = if current.all_ptrs_ok() { GREEN } else { RED },
            "PTR3 {} H{} Q{}",
            if current.all_ptrs_ok() { "OK" } else { "NO" },
            current.host_frame,
            current.seq
        );
        pnp::println!(
            "NOW R{:02X}{:02X} F{:02X} D{:02X}",
            add_of(current.rng),
            sub_of(current.rng),
            frame_of(current.rng),
            current.div
        );
        pnp::println!(
            "FIX id{} rem{} p{} a{}",
            pnp::blue_fixed_run_id(),
            fixed.remaining,
            if fixed.pending { 1 } else { 0 },
            if fixed.physical_a { 1 } else { 0 }
        );

        if let Some(result) = state.result {
            let shiny = shiny_from_raw(result.battle.raw_dv);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "RUN{} DV {:04X} {}",
                state.completed_runs,
                result.battle.raw_dv,
                if shiny { "SHINY" } else { "normal" }
            );
            draw_snapshot("A2", result.trigger);
            draw_snapshot("B", result.battle);

            let tq = host_blue_dvtrace_trigger_seq();
            let wq = host_blue_dvtrace_dvwrite_seq();
            let bq = host_blue_dvtrace_battle_seq();
            let dw_rng = host_blue_dvtrace_dvwrite_rng();
            let dw_div = host_blue_dvtrace_dvwrite_div() as u8;
            let pre_rng = host_blue_dvtrace_pre_rng();
            let pre_div = host_blue_dvtrace_pre_div() as u8;

            if wq != 0 {
                pnp::println!(color = GREEN, "DVWRITE Q{} lag{}", wq, bq.wrapping_sub(wq));
                draw_rng("DW", dw_rng, dw_div);
                draw_rng("PRE", pre_rng, pre_div);

                let a = analyze_three_call(pre_rng, pre_div, dw_rng, dw_div, result.battle.raw_dv);
                if a.valid && host_blue_dvtrace_add2_match() != 0 {
                    pnp::println!(color = GREEN, "3CALL FIT YES branches{}", a.configs);
                    pnp::println!(
                        "R0 {:02X}-{:02X} D1 {:02X}-{:02X}",
                        a.call0_min,
                        a.call0_max,
                        a.dv1_min,
                        a.dv1_max
                    );
                    pnp::println!("D2 {:02X}-{:02X} frame{}t", a.dv2_min, a.dv2_max, a.frame_ticks);
                    pnp::println!("DV2 pos +{}-{} ticks", a.dv2_tick_min, a.dv2_tick_max);
                    pnp::println!(
                        "preDV R{:02X}-{:02X}/{:02X}-{:02X}",
                        a.pre_add_min,
                        a.pre_add_max,
                        a.pre_sub_min,
                        a.pre_sub_max
                    );
                } else {
                    pnp::println!(color = YELLOW, "3CALL FIT NO - need hook");
                }
            } else {
                pnp::println!(color = RED, "DVWRITE not isolated");
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
            pnp::println!(color = GREEN, "A2 Exact2F target captured");
        } else if state.final_armed {
            pnp::println!(color = GREEN, "A2 battle A captured");
            if let Some(s) = state.final_a {
                draw_snapshot("A2", s);
            }
            pnp::println!("Hands off; waiting battle");
        } else if state.dialogue_seen {
            pnp::println!(color = GREEN, "A1 dialogue captured");
            if let Some(s) = state.dialogue_a {
                draw_snapshot("A1", s);
            }
            pnp::println!(color = YELLOW, "NEXT A is the battle A2");
            pnp::println!("Calibration: press A normally");
            pnp::println!("Exact: pause here, A+Y then L");
        } else {
            pnp::println!("STEP1: face Mewtwo, press A");
            pnp::println!("Wait for Mewtwo cry/text");
            pnp::println!("STEP2: press A again -> battle");
        }

        pnp::println!(color = YELLOW, "HUNT LOCKED: final-A learning");
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
    fn observed_ad40_frame_has_three_call_fit() {
        // Hardware trial: PRE A375 D12 -> DW AD6C D24, DV AD40.
        let a = analyze_three_call(0xA37514, 0x12, 0xAD6C13, 0x24, 0xAD40);
        assert!(a.valid);
        assert_eq!(a.frame_ticks, 274);
        assert_eq!(a.call0_min, 0x30);
        assert_eq!(a.call0_max, 0x32);
        assert_eq!(a.dv1_min, 0x6A);
        assert_eq!(a.dv1_max, 0x6B);
        assert_eq!(a.dv2_min, 0x6C);
        assert_eq!(a.dv2_max, 0x6C);
        assert_eq!(a.dv2_tick_min, 90);
        assert_eq!(a.dv2_tick_max, 90);
        assert_eq!(a.pre_add_min, 0xD4);
        assert_eq!(a.pre_add_max, 0xD6);
        assert_eq!(a.pre_sub_min, 0x43);
        assert_eq!(a.pre_sub_max, 0x45);
    }
}
