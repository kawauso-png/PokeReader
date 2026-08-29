use crate::pnp;

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
const MAX_TARGET_TO_BATTLE_FRAMES: u32 = 180;
const DV_MIN_BATTLE_AGE: u8 = 3;
const DV_STABLE_COUNT: u8 = 2;

const WHITE: u32 = 0xFFFFFF;
const GREEN: u32 = 0x00CC00;
const RED: u32 = 0xFF0000;
const BLUE: u32 = 0x005FFF;

#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
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
        self.wram_base.is_some()
            && self.hram_base.is_some()
            && self.div_host.is_some()
            && self.pc.is_some()
            && self.random_add.is_some()
            && self.random_sub.is_some()
            && self.frame_counter.is_some()
            && self.div.is_some()
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

#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
struct Sample {
    host_frame: u32,
    snapshot: Snapshot,
}

#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
struct TrialResult {
    run_id: u32,
    target: Sample,
    battle: Sample,
}

#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
struct DvStability {
    battle_age: u8,
    last_raw: Option<u16>,
    same_count: u8,
}

impl DvStability {
    fn reset(&mut self) {
        *self = Self::default();
    }

    fn observe(&mut self, in_mewtwo_battle: bool, raw: Option<u16>) -> bool {
        if !in_mewtwo_battle {
            self.reset();
            return false;
        }

        self.battle_age = self.battle_age.saturating_add(1);
        let Some(raw) = raw else {
            self.last_raw = None;
            self.same_count = 0;
            return false;
        };

        if self.last_raw == Some(raw) {
            self.same_count = self.same_count.saturating_add(1);
        } else {
            self.last_raw = Some(raw);
            self.same_count = 1;
        }

        self.battle_age >= DV_MIN_BATTLE_AGE && self.same_count >= DV_STABLE_COUNT
    }
}

#[derive(Clone, Copy, Default)]
struct TrialState {
    host_frame: u32,
    run_id: u32,
    target: Option<Sample>,
    result: Option<TrialResult>,
    stability: DvStability,
    expired: bool,
}

impl TrialState {
    fn begin(&mut self, run_id: u32, target: Sample) {
        self.run_id = run_id;
        self.target = Some(target);
        self.result = None;
        self.stability.reset();
        self.expired = false;
    }
}

static mut STATE: TrialState = TrialState {
    host_frame: 0,
    run_id: 0,
    target: None,
    result: None,
    stability: DvStability {
        battle_age: 0,
        last_raw: None,
        same_count: 0,
    },
    expired: false,
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

#[no_mangle]
pub extern "C" fn blue_capture_target(run_id: u32) -> u32 {
    if pnp::title_id() != BLUE_JP_TITLE_ID {
        return 0;
    }

    let snap = snapshot();
    if !snap.pointer_ok() {
        return 0;
    }

    unsafe {
        let state = &mut STATE;
        let target = Sample {
            host_frame: state.host_frame,
            snapshot: snap,
        };
        state.begin(run_id, target);
    }
    1
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
            pnp::println!("{} R{:02X}{:02X} F{:02X}", label, a, sub, f);
            pnp::println!(" D{:02X} PC{:04X}", d, pc);
        }
        _ => pnp::println!(color = RED, "{} snapshot incomplete", label),
    }
}

fn draw_result(result: TrialResult) {
    match result.battle.snapshot.raw_dv() {
        Some(raw) => {
            let shiny = shiny_from_raw(raw);
            pnp::println!(
                color = if shiny { GREEN } else { WHITE },
                "ACT {:04X} {}",
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
        None => pnp::println!(color = RED, "ACT ----"),
    }
    draw_sample("TARGET", result.target);
    draw_sample("BATTLE", result.battle);
}

fn fixed_status_text(f: pnp::BlueFixedState) -> &'static str {
    if f.error != 0 {
        return "ERROR";
    }
    if f.pending {
        return "WAIT MOD RELEASE";
    }
    if f.remaining != 0 {
        return "RUN 2F";
    }
    if f.wait_a_release {
        return "RELEASE A";
    }
    if f.paused {
        return "PAUSED";
    }
    "LIVE"
}

fn draw(state: &TrialState, current: &Snapshot) {
    let fixed = pnp::blue_fixed_state();
    pnp::println!(color = BLUE, "JP Blue Mewtwo AUDITED");
    pnp::println!("HostF {} Run {}", state.host_frame, pnp::blue_fixed_run_id());
    pnp::println!(
        color = if current.pointer_ok() { GREEN } else { RED },
        "PTR {}",
        if current.pointer_ok() { "OK" } else { "WAIT" }
    );
    match (current.random_add, current.random_sub, current.frame_counter, current.div) {
        (Some(a), Some(s), Some(f), Some(d)) => pnp::println!("NOW R{:02X}{:02X} F{:02X} D{:02X}", a, s, f, d),
        _ => pnp::println!(color = RED, "NOW R---- F-- D--"),
    }
    pnp::println!("2F {} rem{}", fixed_status_text(fixed), fixed.remaining);
    if fixed.error != 0 {
        pnp::println!(color = RED, "2F error {} (B clears)", fixed.error);
    }

    if let Some(result) = state.result {
        draw_result(result);
        pnp::println!(color = GREEN, "LOCK run {} stable", result.run_id);
        return;
    }

    if state.expired {
        pnp::println!(color = RED, "Trial expired; arm again");
    } else if let Some(target) = state.target {
        draw_sample("TARGET", target);
        if state.stability.battle_age != 0 {
            pnp::println!("DV settle {}/{} age{}", state.stability.same_count, DV_STABLE_COUNT, state.stability.battle_age);
        } else {
            pnp::println!("Run {} armed", state.run_id);
        }
    } else {
        pnp::println!("L+R pause");
        pnp::println!("Hold A+Y, tap L");
        pnp::println!("Release Y/L; keep A");
        pnp::println!("After 2F release A, R");
    }
}

pub fn run_frame() {
    pnp::set_print_max_len(31);
    let current = snapshot();

    unsafe {
        let state = &mut STATE;
        state.host_frame = state.host_frame.wrapping_add(1);

        if state.result.is_none() {
            if let Some(target) = state.target {
                let elapsed = state.host_frame.wrapping_sub(target.host_frame);
                if elapsed > MAX_TARGET_TO_BATTLE_FRAMES {
                    state.target = None;
                    state.stability.reset();
                    state.expired = true;
                } else {
                    let in_battle = current.is_mewtwo_battle();
                    let stable = state.stability.observe(in_battle, current.raw_dv());
                    if stable {
                        state.result = Some(TrialResult {
                            run_id: state.run_id,
                            target,
                            battle: Sample {
                                host_frame: state.host_frame,
                                snapshot: current,
                            },
                        });
                    }
                }
            } else {
                state.stability.reset();
            }
        }

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

    #[test]
    fn dv_requires_battle_age_and_stability() {
        let mut d = DvStability::default();
        assert!(!d.observe(true, Some(0x1234))); // age 1, count 1
        assert!(!d.observe(true, Some(0x1234))); // age 2, count 2 but too early
        assert!(d.observe(true, Some(0x1234)));  // age 3, stable
    }

    #[test]
    fn dv_change_restarts_stability_count() {
        let mut d = DvStability::default();
        assert!(!d.observe(true, Some(0x1111)));
        assert!(!d.observe(true, Some(0x2222)));
        assert!(d.observe(true, Some(0x2222)));
    }

    #[test]
    fn leaving_battle_resets_dv_stability() {
        let mut d = DvStability::default();
        assert!(!d.observe(true, Some(0x1111)));
        assert!(!d.observe(false, None));
        assert_eq!(d, DvStability::default());
    }

    #[test]
    fn new_run_clears_previous_result_and_expiry() {
        let mut s = TrialState {
            host_frame: 9,
            run_id: 1,
            target: None,
            result: Some(TrialResult::default()),
            stability: DvStability { battle_age: 9, last_raw: Some(1), same_count: 9 },
            expired: true,
        };
        s.begin(7, Sample::default());
        assert_eq!(s.run_id, 7);
        assert!(s.result.is_none());
        assert!(!s.expired);
        assert_eq!(s.stability, DvStability::default());
    }
}
