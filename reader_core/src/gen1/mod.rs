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
    fn host_blue_lab_sample() -> u32;
    fn host_blue_lab_wram() -> u32;
    fn host_blue_lab_hram() -> u32;
    fn host_blue_lab_div_host() -> u32;
    fn host_blue_lab_rng_pack() -> u32;
    fn host_blue_lab_div_value() -> u32;
    fn host_blue_lab_raw_dv() -> u32;
    fn host_blue_lab_div_changes() -> u32;
    fn host_blue_lab_div_steps() -> u32;

    fn host_blue_lab_seq() -> u32;
    fn host_blue_lab_hist_count() -> u32;
    fn host_blue_lab_roll_zero() -> u32;
    fn host_blue_lab_roll_one() -> u32;
    fn host_blue_lab_roll_multi() -> u32;
    fn host_blue_lab_roll_phase() -> u32;
    fn host_blue_lab_roll_phase_n() -> u32;

    fn host_blue_lab_pc_addr() -> u32;
    fn host_blue_lab_pc_value() -> u32;
    fn host_blue_lab_pc_samples() -> u32;
    fn host_blue_lab_pc_changes() -> u32;
    fn host_blue_lab_pc_rom() -> u32;
    fn host_blue_lab_pc_map_hits() -> u32;
    fn host_blue_lab_pc_swap_hits() -> u32;
    fn host_blue_lab_pc_scan_passes() -> u32;
    fn host_blue_lab_pc_scan_hits() -> u32;

    fn host_blue_lab_analyze_window(start_seq: u32, end_seq: u32) -> u32;
    fn host_blue_lab_window_valid() -> u32;
    fn host_blue_lab_window_frames() -> u32;
    fn host_blue_lab_window_zero() -> u32;
    fn host_blue_lab_window_one() -> u32;
    fn host_blue_lab_window_multi() -> u32;
    fn host_blue_lab_window_phase() -> u32;
    fn host_blue_lab_window_phase_n() -> u32;
    fn host_blue_lab_window_map_hits() -> u32;
    fn host_blue_lab_window_hash() -> u32;
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
struct WindowInfo {
    valid: bool,
    frames: u32,
    zero: u32,
    one: u32,
    multi: u32,
    phase: u8,
    phase_n: u32,
    map_hits: u32,
    hash: u32,
}

#[derive(Clone, Copy, Default)]
struct ResultPair {
    trigger: Snapshot,
    battle: Snapshot,
    window: WindowInfo,
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

// main.c invokes this while paused immediately before it releases exactly two
// emulated A frames.  Returning 1 is what enables the already-audited Blue
// fixed-2F controller.  We capture the most recent live RNG/DIV/history sample
// so the later battle can be analyzed against the exact pre-run state.
#[no_mangle]
pub extern "C" fn blue_capture_target(run_id: u32) -> u32 {
    unsafe {
        let s = RUN_STATE.last_snapshot;
        if s.all_ptrs_ok() && !s.in_mewtwo_battle() && s.seq != 0 {
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
    let status = unsafe { host_blue_lab_sample() };
    Snapshot {
        host_frame: unsafe { HOST_FRAME },
        seq: unsafe { host_blue_lab_seq() },
        status,
        rng: unsafe { host_blue_lab_rng_pack() },
        div: unsafe { host_blue_lab_div_value() } as u8,
        raw_dv: unsafe { host_blue_lab_raw_dv() } as u16,
    }
}

fn load_window(start_seq: u32, end_seq: u32) -> WindowInfo {
    let ok = unsafe { host_blue_lab_analyze_window(start_seq, end_seq) } != 0;
    if !ok || unsafe { host_blue_lab_window_valid() } == 0 {
        return WindowInfo::default();
    }
    WindowInfo {
        valid: true,
        frames: unsafe { host_blue_lab_window_frames() },
        zero: unsafe { host_blue_lab_window_zero() },
        one: unsafe { host_blue_lab_window_one() },
        multi: unsafe { host_blue_lab_window_multi() },
        phase: unsafe { host_blue_lab_window_phase() } as u8,
        phase_n: unsafe { host_blue_lab_window_phase_n() },
        map_hits: unsafe { host_blue_lab_window_map_hits() },
        hash: unsafe { host_blue_lab_window_hash() },
    }
}

fn draw_snapshot(label: &str, s: Snapshot) {
    let add = ((s.rng >> 16) & 0xFF) as u8;
    let sub = ((s.rng >> 8) & 0xFF) as u8;
    let frame = (s.rng & 0xFF) as u8;
    pnp::println!("{} H{} R{:02X}{:02X}", label, s.host_frame, add, sub);
    pnp::println!("  F{:02X} D{:02X} Q{}", frame, s.div, s.seq);
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

        // Keep ordinary physical-A diagnostics, but production-quality runs use
        // the C-side fixed controller armed while paused.  This path remains
        // useful when checking that a fresh A edge was actually seen.
        if !in_battle && pnp::is_just_pressed(Button::A) {
            state.a_pending = Some(current);
            state.result = None;
        } else if !in_battle {
            if let Some(start) = state.a_pending {
                if current.host_frame == start.host_frame.wrapping_add(1) {
                    if pnp::is_pressing(Button::A) {
                        state.last_valid_2f = Some(start);
                        state.valid_2f = state.valid_2f.wrapping_add(1);
                    } else {
                        state.last_valid_2f = None;
                        state.reject_1f = state.reject_1f.wrapping_add(1);
                    }
                    state.a_pending = None;
                } else if current.host_frame.wrapping_sub(start.host_frame) > 1 {
                    state.a_pending = None;
                }
            }
        }

        if in_battle && !state.was_battle {
            if let Some((trigger, fixed_run_id)) = choose_trigger(state, current) {
                let window = load_window(trigger.seq, current.seq);
                state.result = Some(ResultPair {
                    trigger,
                    battle: current,
                    window,
                    fixed_run_id,
                });
                state.completed_runs = state.completed_runs.wrapping_add(1);
            }
            state.fixed_target = None;
            state.last_valid_2f = None;
        }
        state.was_battle = in_battle;

        let wram = host_blue_lab_wram();
        let hram = host_blue_lab_hram();
        let div_host = host_blue_lab_div_host();
        let hist_n = host_blue_lab_hist_count();
        let rz = host_blue_lab_roll_zero();
        let ro = host_blue_lab_roll_one();
        let rm = host_blue_lab_roll_multi();
        let rph = host_blue_lab_roll_phase();
        let rphn = host_blue_lab_roll_phase_n();

        let pc_addr = host_blue_lab_pc_addr();
        let pc_value = host_blue_lab_pc_value() as u16;
        let pc_n = host_blue_lab_pc_samples();
        let pc_ch = host_blue_lab_pc_changes();
        let pc_rom = host_blue_lab_pc_rom();
        let pc_map = host_blue_lab_pc_map_hits();
        let pc_swap = host_blue_lab_pc_swap_hits();
        let scan_pass = host_blue_lab_pc_scan_passes();
        let scan_hits = host_blue_lab_pc_scan_hits();

        let fixed = pnp::blue_fixed_state();
        let fixed_id = pnp::blue_fixed_run_id();

        pnp::println!(color = BLUE, "BLUE MEWTWO HUNT LAB v1");
        pnp::println!(
            color = if current.all_ptrs_ok() { GREEN } else { RED },
            "PTR3 {} H{} Q{}",
            if current.all_ptrs_ok() { "OK" } else { "NO" },
            hist_n,
            current.seq
        );
        pnp::println!("W {:08X} H {:08X}", wram, hram);
        pnp::println!("D {:08X}", div_host);

        let add = ((current.rng >> 16) & 0xFF) as u8;
        let sub = ((current.rng >> 8) & 0xFF) as u8;
        let frame = (current.rng & 0xFF) as u8;
        pnp::println!("NOW R{:02X}{:02X} F{:02X} D{:02X}", add, sub, frame, current.div);
        pnp::println!("DIV ch{} ds{}", host_blue_lab_div_changes(), host_blue_lab_div_steps());

        pnp::println!("PC {:08X}>{:04X}", pc_addr, pc_value);
        pnp::println!("PC n{} ch{} rom{}", pc_n, pc_ch, pc_rom);
        pnp::println!("MAP {} SW{} scan{}/{}", pc_map, pc_swap, scan_hits, scan_pass);
        pnp::println!("RNG Z{} O{} M{}", rz, ro, rm);
        pnp::println!(color = YELLOW, "P16cand {} n{}", rph & 15, rphn);

        pnp::println!(
            "FIX id{} rem{} p{} a{}",
            fixed_id,
            fixed.remaining,
            if fixed.pending { 1 } else { 0 },
            if fixed.physical_a { 1 } else { 0 }
        );
        if fixed.error != 0 {
            pnp::println!(color = RED, "FIX ERR {}", fixed.error);
        }

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
            if result.window.valid {
                pnp::println!(
                    "WIN{} Z{} O{} M{}",
                    result.window.frames,
                    result.window.zero,
                    result.window.one,
                    result.window.multi
                );
                pnp::println!(
                    color = if result.window.multi == 0 { GREEN } else { YELLOW },
                    "P16 {} n{} MAP{}",
                    result.window.phase,
                    result.window.phase_n,
                    result.window.map_hits
                );
                pnp::println!("HASH {:08X} FID{}", result.window.hash, result.fixed_run_id);
                if result.window.multi == 0 {
                    pnp::println!(color = GREEN, "TRACE CLEAN: replay candidate");
                } else {
                    pnp::println!(color = YELLOW, "TRACE MULTI: learning calls");
                }
            } else {
                pnp::println!(color = RED, "WINDOW unavailable");
            }
        } else if state.fixed_target.is_some() {
            pnp::println!(color = GREEN, "TARGET CAPTURED; run 2F");
        } else {
            pnp::println!("Pause -> hold A+Y -> tap L");
            pnp::println!("Release Y/L; keep A 2F");
        }

        // Deliberate safety gate: this integrated build learns the current Blue
        // call/phase path but does not claim a shiny target until a raw-DV
        // predictor has reproduced independent runs exactly.
        pnp::println!(color = YELLOW, "HUNT LOCKED: RAW model learning");
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
