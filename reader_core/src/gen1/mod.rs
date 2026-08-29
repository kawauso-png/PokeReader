use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const WRAM0_PTR_SLOT: u32 = 0x0022_F6C8;
const HRAM_PTR_SLOT: u32 = 0x0022_F6D8;
const DIV_PTR_SLOT: u32 = 0x0022_F794;
const PC_REG_ADDR: u32 = 0x0022_F5FC;

const H_RANDOM_ADD: u16 = 0xFFD3;
const H_RANDOM_SUB: u16 = 0xFFD4;
const H_FRAME_COUNTER: u16 = 0xFFD5;
const W_BATTLE_STATE: u16 = 0xD034;
const W_OPPONENT: u16 = 0xD036;
const W_ENEMY_SPECIES: u16 = 0xCFCC;
const W_ENEMY_DV_ATK_DEF: u16 = 0xCFD8;
const W_ENEMY_DV_SPE_SPC: u16 = 0xCFD9;
const W_ENEMY_LEVEL: u16 = 0xCFDA;

const MEWTWO_INTERNAL_ID: u8 = 0x83;
const MEWTWO_LEVEL: u8 = 70;
const MAX_A_TO_BATTLE_HOST_FRAMES: u32 = 120;

const WHITE: u32 = 0xFFFFFF;
const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;

#[derive(Clone, Copy, Default)]
struct Snapshot {
    wram_base: Option<u32>,
    div_host: Option<u32>,
    pc: Option<u16>,
    div: Option<u8>,
    random_add: Option<u8>,
    random_sub: Option<u8>,
    frame_counter: Option<u8>,
    battle_state: Option<u8>,
    opponent: Option<u8>,
    enemy_species: Option<u8>,
    enemy_level: Option<u8>,
    dv_atk_def: Option<u8>,
    dv_spe_spc: Option<u8>,
}

impl Snapshot {
    fn pointer_ok(&self) -> bool {
        self.wram_base.is_some() && self.div_host.is_some()
    }

    fn is_mewtwo_battle(&self) -> bool {
        self.battle_state == Some(1)
            && self.opponent == Some(MEWTWO_INTERNAL_ID)
            && self.enemy_species == Some(MEWTWO_INTERNAL_ID)
            && self.enemy_level == Some(MEWTWO_LEVEL)
    }

    fn raw_dv(&self) -> Option<u16> {
        Some(((self.dv_atk_def? as u16) << 8) | self.dv_spe_spc? as u16)
    }
}

#[derive(Clone, Copy)]
struct Sample {
    host_frame: u32,
    snapshot: Snapshot,
}

#[derive(Clone, Copy)]
struct CalResult {
    trigger_a: Sample,
    battle: Sample,
}

struct CalState {
    host_frame: u32,
    a_pending: Option<Sample>,
    last_valid_2f_a: Option<Sample>,
    result: Option<CalResult>,
    was_mewtwo_battle: bool,
    one_frame_rejected: u32,
    two_frame_valid: u32,
    battle_without_valid_a: bool,
}

static mut CAL_STATE: CalState = CalState {
    host_frame: 0,
    a_pending: None,
    last_valid_2f_a: None,
    result: None,
    was_mewtwo_battle: false,
    one_frame_rejected: 0,
    two_frame_valid: 0,
    battle_without_valid_a: false,
};

pub fn init_blue() {}

fn mapped(addr: u32) -> bool {
    addr != 0 && pnp::is_memory_mapped(addr)
}

fn resolve_ptr_slot(slot: u32) -> Option<u32> {
    if !mapped(slot) {
        return None;
    }
    let ptr = pnp::read::<u32>(slot);
    mapped(ptr).then_some(ptr)
}

fn read_host_u8(addr: u32) -> Option<u8> {
    mapped(addr).then(|| pnp::read::<u8>(addr))
}

fn read_host_u16(addr: u32) -> Option<u16> {
    mapped(addr).then(|| pnp::read::<u16>(addr))
}

fn wram_addr(base: u32, gb_addr: u16) -> Option<u32> {
    if !(0xC000..=0xDFFF).contains(&gb_addr) {
        return None;
    }
    let host = base.wrapping_add((gb_addr - 0xC000) as u32);
    mapped(host).then_some(host)
}

fn hram_addr(base: u32, gb_addr: u16) -> Option<u32> {
    if !(0xFF80..=0xFFFF).contains(&gb_addr) {
        return None;
    }
    let host = base.wrapping_add((gb_addr - 0xFF80) as u32);
    mapped(host).then_some(host)
}

fn read_wram_u8(base: Option<u32>, gb_addr: u16) -> Option<u8> {
    read_host_u8(wram_addr(base?, gb_addr)?)
}

fn read_hram_u8(base: Option<u32>, gb_addr: u16) -> Option<u8> {
    read_host_u8(hram_addr(base?, gb_addr)?)
}

fn snapshot() -> Snapshot {
    let wram_base = resolve_ptr_slot(WRAM0_PTR_SLOT);
    let hram_base = resolve_ptr_slot(HRAM_PTR_SLOT);
    let div_host = resolve_ptr_slot(DIV_PTR_SLOT);

    Snapshot {
        wram_base,
        div_host,
        pc: read_host_u16(PC_REG_ADDR),
        div: div_host.and_then(read_host_u8),
        random_add: read_hram_u8(hram_base, H_RANDOM_ADD),
        random_sub: read_hram_u8(hram_base, H_RANDOM_SUB),
        frame_counter: read_hram_u8(hram_base, H_FRAME_COUNTER),
        battle_state: read_wram_u8(wram_base, W_BATTLE_STATE),
        opponent: read_wram_u8(wram_base, W_OPPONENT),
        enemy_species: read_wram_u8(wram_base, W_ENEMY_SPECIES),
        enemy_level: read_wram_u8(wram_base, W_ENEMY_LEVEL),
        dv_atk_def: read_wram_u8(wram_base, W_ENEMY_DV_ATK_DEF),
        dv_spe_spc: read_wram_u8(wram_base, W_ENEMY_DV_SPE_SPC),
    }
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

fn draw_sample(label: &str, sample: Sample) {
    let s = sample.snapshot;
    match (s.random_add, s.random_sub, s.frame_counter, s.div, s.pc) {
        (Some(a), Some(sub), Some(f), Some(d), Some(pc)) => {
            pnp::println!("{} H{} R{:02X}{:02X}", label, sample.host_frame, a, sub);
            pnp::println!("  F{:02X} D{:02X} PC{:04X}", f, d, pc);
        }
        _ => pnp::println!(color = RED, "{} snapshot incomplete", label),
    }
}

fn draw_result(result: CalResult) {
    match result.battle.snapshot.raw_dv() {
        Some(raw) => {
            let shiny = shiny_from_raw(raw);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "RESULT RAW {:04X} {}",
                raw,
                if shiny { "SHINY" } else { "normal" }
            );
            pnp::println!(
                "DV A{} D{} S{} C{}",
                (raw >> 12) & 0xF,
                (raw >> 8) & 0xF,
                (raw >> 4) & 0xF,
                raw & 0xF
            );
        }
        None => pnp::println!(color = RED, "RESULT RAW ----"),
    }
    draw_sample("A2F", result.trigger_a);
    draw_sample("B", result.battle);
    pnp::println!(
        "Delta H{}",
        result
            .battle
            .host_frame
            .wrapping_sub(result.trigger_a.host_frame)
    );
}

fn draw(state: &CalState, current: &Snapshot) {
    pnp::println!(color = BLUE, "JP Blue / Mewtwo RESIDUAL v2");
    pnp::println!("HostF {}", state.host_frame);
    match current.wram_base {
        Some(v) => pnp::println!("C000 {:08X}", v),
        None => pnp::println!(color = RED, "C000 --------"),
    }
    match current.div_host {
        Some(v) => pnp::println!("FF04 {:08X}", v),
        None => pnp::println!(color = RED, "FF04 --------"),
    }
    pnp::println!(
        color = if current.pointer_ok() { GREEN } else { RED },
        "PTR {}",
        if current.pointer_ok() { "OK" } else { "CHECK" }
    );
    match (
        current.random_add,
        current.random_sub,
        current.frame_counter,
        current.div,
    ) {
        (Some(a), Some(s), Some(f), Some(d)) => {
            pnp::println!("NOW R{:02X}{:02X} F{:02X} D{:02X}", a, s, f, d)
        }
        _ => pnp::println!(color = RED, "NOW R---- F-- D--"),
    }
    pnp::println!("2F valid {} / 1F reject {}", state.two_frame_valid, state.one_frame_rejected);
    pnp::println!("");

    if let Some(result) = state.result {
        draw_result(result);
        pnp::println!("Locked; retry same protocol");
        return;
    }

    if let Some(pending) = state.a_pending {
        pnp::println!("A started H{}", pending.host_frame);
        pnp::println!("KEEP A for frame 2");
    } else if let Some(valid) = state.last_valid_2f_a {
        pnp::println!(color = GREEN, "A 2F VALID");
        draw_sample("A2F", valid);
        pnp::println!("Hands off; waiting battle");
    } else if state.battle_without_valid_a {
        pnp::println!(color = RED, "BATTLE: no valid 2F A");
    } else {
        pnp::println!(color = GREEN, "READY: final A must be 2F");
    }

    pnp::println!("1F A is rejected by design");
}

pub fn run_frame() {
    pnp::set_print_max_len(31);
    let current = snapshot();

    unsafe {
        let state = &mut CAL_STATE;
        state.host_frame = state.host_frame.wrapping_add(1);
        let in_battle = current.is_mewtwo_battle();

        // Hardware result: a 1F A pulse can be missed by the GB side, while
        // keeping A through the second host frame was recognized.  Preserve the
        // snapshot from frame 1, but only promote it after frame 2 still sees A.
        if !in_battle && pnp::is_just_pressed(Button::A) {
            state.a_pending = Some(Sample {
                host_frame: state.host_frame,
                snapshot: current,
            });
            state.result = None;
            state.battle_without_valid_a = false;
        } else if !in_battle {
            if let Some(start) = state.a_pending {
                if state.host_frame == start.host_frame.wrapping_add(1) {
                    if pnp::is_pressing(Button::A) {
                        state.last_valid_2f_a = Some(start);
                        state.two_frame_valid = state.two_frame_valid.wrapping_add(1);
                    } else {
                        state.last_valid_2f_a = None;
                        state.one_frame_rejected = state.one_frame_rejected.wrapping_add(1);
                    }
                    state.a_pending = None;
                } else if state.host_frame.wrapping_sub(start.host_frame) > 1 {
                    state.a_pending = None;
                }
            }
        }

        if in_battle && !state.was_mewtwo_battle {
            let battle = Sample {
                host_frame: state.host_frame,
                snapshot: current,
            };
            match state.last_valid_2f_a {
                Some(trigger_a)
                    if battle
                        .host_frame
                        .wrapping_sub(trigger_a.host_frame)
                        <= MAX_A_TO_BATTLE_HOST_FRAMES =>
                {
                    state.result = Some(CalResult { trigger_a, battle });
                    state.battle_without_valid_a = false;
                }
                _ => {
                    state.result = None;
                    state.battle_without_valid_a = true;
                }
            }
        }

        state.was_mewtwo_battle = in_battle;
        draw(state, &current);
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
        assert!(!shiny_from_raw(0x2AAB));
    }
}
