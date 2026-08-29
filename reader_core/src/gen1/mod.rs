use crate::pnp::{self, Button};

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

// Nintendo GB VC host-process state confirmed on Japanese VC Blue hardware.
const WRAM0_PTR_SLOT: u32 = 0x0022_F6C8; // GB C000-DFFF backing pointer
const HRAM_PTR_SLOT: u32 = 0x0022_F6D8; // GB FF80-FFFF backing pointer
const DIV_PTR_SLOT: u32 = 0x0022_F794; // emulated rDIV (FF04) byte pointer
const PC_REG_ADDR: u32 = 0x0022_F5FC; // emulated LR35902 PC

// Gen I Japanese Blue addresses used by this clean Mewtwo calibration build.
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
    hram_base: Option<u32>,
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
        self.wram_base.is_some() && self.hram_base.is_some() && self.div_host.is_some()
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
    last_a: Option<Sample>,
    result: Option<CalResult>,
    was_mewtwo_battle: bool,
    battle_without_recent_a: bool,
}

static mut CAL_STATE: CalState = CalState {
    host_frame: 0,
    last_a: None,
    result: None,
    was_mewtwo_battle: false,
    battle_without_recent_a: false,
};

pub fn init_blue() {
    // Intentionally empty.  CLEAN CAL installs no Gen II Random-call hook,
    // no Fixed-A runner, no phase/bucket model, and no automatic pause.
}

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
        hram_base,
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

fn draw_ptr(label: &str, value: Option<u32>) {
    match value {
        Some(v) => pnp::println!("{} {:08X}", label, v),
        None => pnp::println!(color = RED, "{} --------", label),
    }
}

fn draw_live(snapshot: &Snapshot) {
    match (
        snapshot.random_add,
        snapshot.random_sub,
        snapshot.frame_counter,
        snapshot.div,
    ) {
        (Some(a), Some(s), Some(f), Some(d)) => {
            pnp::println!("NOW R{:02X}{:02X} F{:02X} D{:02X}", a, s, f, d)
        }
        _ => pnp::println!(color = RED, "NOW R---- F-- D--"),
    }
}

fn draw_sample(label: &str, sample: Sample) {
    let s = sample.snapshot;
    match (s.random_add, s.random_sub) {
        (Some(a), Some(sub)) => pnp::println!("{} H{} R{:02X}{:02X}", label, sample.host_frame, a, sub),
        _ => pnp::println!(color = RED, "{} H{} R----", label, sample.host_frame),
    }

    match (s.frame_counter, s.div, s.pc) {
        (Some(f), Some(d), Some(pc)) => pnp::println!("  F{:02X} D{:02X} PC{:04X}", f, d, pc),
        _ => pnp::println!(color = RED, "  F-- D-- PC----"),
    }
}

fn draw_result(result: CalResult) {
    let raw = result.battle.snapshot.raw_dv();
    match raw {
        Some(raw) => {
            let shiny = shiny_from_raw(raw);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "RESULT RAW {:04X} {}",
                raw,
                if shiny { "SHINY" } else { "normal" }
            );
            let atk = (raw >> 12) & 0xF;
            let def = (raw >> 8) & 0xF;
            let spe = (raw >> 4) & 0xF;
            let spc = raw & 0xF;
            pnp::println!("DV A{} D{} S{} C{}", atk, def, spe, spc);
        }
        None => pnp::println!(color = RED, "RESULT RAW ----"),
    }

    draw_sample("A", result.trigger_a);
    draw_sample("B", result.battle);

    let dh = result
        .battle
        .host_frame
        .wrapping_sub(result.trigger_a.host_frame);
    match (
        result.trigger_a.snapshot.frame_counter,
        result.battle.snapshot.frame_counter,
    ) {
        (Some(a), Some(b)) => pnp::println!("Delta H{} F{}", dh, b.wrapping_sub(a)),
        _ => pnp::println!("Delta H{} F--", dh),
    }
}

fn draw(state: &CalState, current: &Snapshot) {
    pnp::println!(color = BLUE, "JP Blue / Mewtwo CLEAN CAL");
    pnp::println!("HostF {}", state.host_frame);
    draw_ptr("C000", current.wram_base);
    draw_ptr("FF04", current.div_host);
    pnp::println!(
        color = if current.pointer_ok() { GREEN } else { RED },
        "CAL PTR {}",
        if current.pointer_ok() { "OK" } else { "CHECK" }
    );
    draw_live(current);
    pnp::println!("");

    if let Some(result) = state.result {
        draw_result(result);
        pnp::println!("Result locked; reset/retry");
        return;
    }

    if state.battle_without_recent_a {
        pnp::println!(color = RED, "BATTLE: no recent A");
    } else if let Some(last_a) = state.last_a {
        pnp::println!(color = GREEN, "CAL LAST A captured");
        draw_sample("A", last_a);
        pnp::println!("Waiting for Mewtwo battle");
    } else {
        pnp::println!(color = GREEN, "CAL READY");
        pnp::println!("Last A before battle wins");
    }

    pnp::println!("Normal A taps only");
    pnp::println!("No hold / no L-R / no pause");
}

pub fn run_frame() {
    pnp::set_print_max_len(31);
    let current = snapshot();

    unsafe {
        let state = &mut CAL_STATE;
        state.host_frame = state.host_frame.wrapping_add(1);

        let in_mewtwo_battle = current.is_mewtwo_battle();

        // Track every normal physical A edge outside battle.  This deliberately
        // avoids hJoyPressed latches and avoids asking the user to hold A.
        // The last A edge before the Mewtwo battle transition is the trigger.
        if !in_mewtwo_battle && pnp::is_just_pressed(Button::A) {
            state.last_a = Some(Sample {
                host_frame: state.host_frame,
                snapshot: current,
            });
            state.result = None;
            state.battle_without_recent_a = false;
        }

        if in_mewtwo_battle && !state.was_mewtwo_battle {
            let battle = Sample {
                host_frame: state.host_frame,
                snapshot: current,
            };

            match state.last_a {
                Some(trigger_a)
                    if battle
                        .host_frame
                        .wrapping_sub(trigger_a.host_frame)
                        <= MAX_A_TO_BATTLE_HOST_FRAMES =>
                {
                    state.result = Some(CalResult { trigger_a, battle });
                    state.battle_without_recent_a = false;
                }
                _ => {
                    state.result = None;
                    state.battle_without_recent_a = true;
                }
            }
        }

        // Leaving battle (soft reset / retry) rearms transition detection.  The
        // next normal A press replaces last_a automatically, so no extra hotkey
        // or startup sequence is required.
        state.was_mewtwo_battle = in_mewtwo_battle;

        draw(state, &current);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gen2_transfer_shiny_rule() {
        for atk in [2u16, 3, 6, 7, 10, 11, 14, 15] {
            assert!(shiny_from_raw((atk << 12) | 0x0AAA));
        }
        assert!(!shiny_from_raw(0x1AAA));
        assert!(!shiny_from_raw(0x2BAA));
        assert!(!shiny_from_raw(0x2AAB));
    }
}
