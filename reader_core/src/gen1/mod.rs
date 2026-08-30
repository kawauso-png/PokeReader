use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;
const WHITE: u32 = 0xFFFFFF;
const MAX_A_TO_BATTLE_HOST_FRAMES: u32 = 120;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_stage8_sample() -> u32;
    fn host_blue_stage8_wram_slot() -> u32;
    fn host_blue_stage8_hram_slot() -> u32;
    fn host_blue_stage8_div_slot() -> u32;
    fn host_blue_stage8_wram() -> u32;
    fn host_blue_stage8_hram() -> u32;
    fn host_blue_stage8_div_host() -> u32;
    fn host_blue_stage8_rng_pack() -> u32;
    fn host_blue_stage8_div_value() -> u32;
    fn host_blue_stage8_raw_dv() -> u32;
    fn host_blue_stage8_div_changes() -> u32;
    fn host_blue_stage8_div_steps() -> u32;

    fn host_blue_stage8_pc_slot() -> u32;
    fn host_blue_stage8_pc() -> u32;
    fn host_blue_stage8_pc_changes() -> u32;
    fn host_blue_stage8_pc_samples() -> u32;
    fn host_blue_stage8_map_pc() -> u32;
    fn host_blue_stage8_map_hits() -> u32;
    fn host_blue_stage8_map_hit_sample() -> u32;
    fn host_blue_stage8_map_rng_pack() -> u32;
    fn host_blue_stage8_map_div_value() -> u32;
}

#[derive(Clone, Copy, Default)]
struct Snapshot {
    host_frame: u32,
    status: u32,
    rng: u32,
    div: u8,
    raw_dv: u16,
}

impl Snapshot {
    fn all_ptrs_ok(self) -> bool {
        self.status & 0x07 == 0x07
    }

    fn pc_ok(self) -> bool {
        self.status & (1 << 4) != 0
    }

    fn in_mewtwo_battle(self) -> bool {
        self.status & (1 << 3) != 0
    }
}

#[derive(Clone, Copy, Default)]
struct ResultPair {
    trigger: Snapshot,
    battle: Snapshot,
}

struct RunState {
    a_pending: Option<Snapshot>,
    last_valid_2f: Option<Snapshot>,
    result: Option<ResultPair>,
    was_battle: bool,
    valid_2f: u32,
    reject_1f: u32,
}

static mut RUN_STATE: RunState = RunState {
    a_pending: None,
    last_valid_2f: None,
    result: None,
    was_battle: false,
    valid_2f: 0,
    reject_1f: 0,
};

pub fn init_blue() {}

#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
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
    let status = unsafe { host_blue_stage8_sample() };
    Snapshot {
        host_frame: unsafe { HOST_FRAME },
        status,
        rng: unsafe { host_blue_stage8_rng_pack() },
        div: unsafe { host_blue_stage8_div_value() } as u8,
        raw_dv: unsafe { host_blue_stage8_raw_dv() } as u16,
    }
}

fn draw_snapshot(label: &str, s: Snapshot) {
    let add = ((s.rng >> 16) & 0xFF) as u8;
    let sub = ((s.rng >> 8) & 0xFF) as u8;
    let frame = (s.rng & 0xFF) as u8;
    pnp::println!("{} H{} R{:02X}{:02X}", label, s.host_frame, add, sub);
    pnp::println!("  F{:02X} D{:02X}", frame, s.div);
}

pub fn run_frame() {
    pnp::set_print_max_len(31);

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
    }
    let current = sample();

    unsafe {
        let state = &mut RUN_STATE;
        let in_battle = current.in_mewtwo_battle();

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
            if let Some(trigger) = state.last_valid_2f {
                if current.host_frame.wrapping_sub(trigger.host_frame) <= MAX_A_TO_BATTLE_HOST_FRAMES {
                    state.result = Some(ResultPair {
                        trigger,
                        battle: current,
                    });
                }
            }
        }
        state.was_battle = in_battle;

        let wslot = host_blue_stage8_wram_slot();
        let hslot = host_blue_stage8_hram_slot();
        let dslot = host_blue_stage8_div_slot();
        let wram = host_blue_stage8_wram();
        let hram = host_blue_stage8_hram();
        let div_host = host_blue_stage8_div_host();
        let dchg = host_blue_stage8_div_changes();
        let dsteps = host_blue_stage8_div_steps();

        let pc_slot = host_blue_stage8_pc_slot();
        let pc = host_blue_stage8_pc() as u16;
        let pc_ch = host_blue_stage8_pc_changes();
        let pc_samples = host_blue_stage8_pc_samples();
        let map_pc = host_blue_stage8_map_pc() as u16;
        let map_hits = host_blue_stage8_map_hits();
        let map_sample = host_blue_stage8_map_hit_sample();
        let map_rng = host_blue_stage8_map_rng_pack();
        let map_div = host_blue_stage8_map_div_value() as u8;

        pnp::println!(color = BLUE, "BLUE RECOVERED STAGE8 PC");
        pnp::println!(
            color = if current.all_ptrs_ok() && current.pc_ok() { GREEN } else { RED },
            "PTR3 {} PC {} ST{:02X}",
            if current.all_ptrs_ok() { "OK" } else { "NO" },
            if current.pc_ok() { "OK" } else { "NO" },
            current.status & 0x1F
        );
        pnp::println!("W {:08X}>{:08X}", wslot, wram);
        pnp::println!("H {:08X}>{:08X}", hslot, hram);
        pnp::println!("D {:08X}>{:08X}", dslot, div_host);

        let add = ((current.rng >> 16) & 0xFF) as u8;
        let sub = ((current.rng >> 8) & 0xFF) as u8;
        let frame = (current.rng & 0xFF) as u8;
        pnp::println!("NOW R{:02X}{:02X} F{:02X} D{:02X}", add, sub, frame, current.div);
        pnp::println!("DIV ch{} ds{}", dchg, dsteps);

        pnp::println!(
            color = if current.pc_ok() { GREEN } else { RED },
            "PC {:08X}>{:04X} ch{}",
            pc_slot,
            pc,
            pc_ch
        );
        pnp::println!("PC samples {} map {:04X}", pc_samples, map_pc);
        pnp::println!(
            color = if map_hits != 0 { GREEN } else { WHITE },
            "MapPC hits {} lastS{}",
            map_hits,
            map_sample
        );
        if map_hits != 0 {
            let ma = ((map_rng >> 16) & 0xFF) as u8;
            let ms = ((map_rng >> 8) & 0xFF) as u8;
            let mf = (map_rng & 0xFF) as u8;
            pnp::println!("MAP R{:02X}{:02X} F{:02X} D{:02X}", ma, ms, mf, map_div);
        }

        pnp::println!("2F ok{} / 1F rej{}", state.valid_2f, state.reject_1f);

        if in_battle {
            let shiny = shiny_from_raw(current.raw_dv);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "BATTLE DV {:04X} {}",
                current.raw_dv,
                if shiny { "SHINY" } else { "normal" }
            );
        } else if let Some(pending) = state.a_pending {
            pnp::println!("A started H{}; KEEP A", pending.host_frame);
        } else if let Some(valid) = state.last_valid_2f {
            pnp::println!(color = GREEN, "A 2F VALID H{}", valid.host_frame);
        } else {
            pnp::println!("Stand before Mewtwo 5 sec");
        }

        if let Some(result) = state.result {
            pnp::println!(color = GREEN, "CAPTURED A2F -> BATTLE");
            draw_snapshot("A2F", result.trigger);
            draw_snapshot("B", result.battle);
            pnp::println!("RESULT DV {:04X}", result.battle.raw_dv);
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
