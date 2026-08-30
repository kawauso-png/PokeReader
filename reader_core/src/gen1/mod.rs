use crate::pnp;

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const WRAM_SCAN_MIN: u32 = 0x08B0_0000;
const WRAM_SCAN_MAX: u32 = 0x08C0_0000;
const OFF_ENEMY_SPECIES: u32 = 0x0FCC;
const OFF_ENEMY_DV_ATK_DEF: u32 = 0x0FD8;
const OFF_ENEMY_DV_SPE_SPC: u32 = 0x0FD9;
const OFF_ENEMY_LEVEL: u32 = 0x0FDA;
const OFF_BATTLE_STATE: u32 = 0x1034;
const OFF_OPPONENT: u32 = 0x1036;
const MAX_OFFSET: u32 = OFF_OPPONENT;
const SCAN_END: u32 = WRAM_SCAN_MAX - MAX_OFFSET;
const CANDIDATES_PER_FRAME: u32 = 512;

static mut HOST_FRAME: u32 = 0;
static mut SCAN_CURSOR: u32 = WRAM_SCAN_MIN;
static mut ALIGN_PHASE: u32 = 0;
static mut FULL_PASSES: u32 = 0;
static mut FOUND_BASE: u32 = 0;

pub fn init_blue() {}

// Keep the C ABI expected by the known-good Blue framebuffer hook. Stage 3 is
// observational only and does not trigger the encounter or write game memory.
#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
    0
}

fn read_u8(addr: u32) -> u8 {
    pnp::read_array::<1>(addr)[0]
}

fn scan_window_mapped(first: u32, last: u32) -> bool {
    // The corrected Stage-2 C gate rejects FREE/RESERVED memory. Check both
    // ends of every offset window before any direct byte read in this chunk.
    for offset in [
        OFF_ENEMY_SPECIES,
        OFF_ENEMY_LEVEL,
        OFF_BATTLE_STATE,
        OFF_OPPONENT,
    ] {
        if !pnp::is_memory_mapped(first + offset) || !pnp::is_memory_mapped(last + offset) {
            return false;
        }
    }
    true
}

fn mewtwo_fingerprint(base: u32) -> bool {
    // Japanese Blue Mewtwo battle fingerprint, relative to GB C000 backing:
    // CFCC=83 species, CFDA=46 level 70, D034=01 battle, D036=83 opponent.
    // Check rare bytes first so almost every candidate exits after one read.
    if read_u8(base + OFF_ENEMY_SPECIES) != 0x83 {
        return false;
    }
    if read_u8(base + OFF_ENEMY_LEVEL) != 0x46 {
        return false;
    }
    if read_u8(base + OFF_OPPONENT) != 0x83 {
        return false;
    }
    read_u8(base + OFF_BATTLE_STATE) == 0x01
}

unsafe fn advance_phase() {
    ALIGN_PHASE = (ALIGN_PHASE + 1) & 3;
    if ALIGN_PHASE == 0 {
        FULL_PASSES = FULL_PASSES.wrapping_add(1);
    }
    SCAN_CURSOR = WRAM_SCAN_MIN + ALIGN_PHASE;
}

fn scan_chunk() {
    unsafe {
        if FOUND_BASE != 0 {
            return;
        }

        if SCAN_CURSOR >= SCAN_END {
            advance_phase();
        }

        let first = SCAN_CURSOR;
        let remaining = ((SCAN_END - first - 1) / 4) + 1;
        let count = core::cmp::min(CANDIDATES_PER_FRAME, remaining);
        let last = first + (count - 1) * 4;

        if scan_window_mapped(first, last) {
            let mut base = first;
            for _ in 0..count {
                if mewtwo_fingerprint(base) {
                    FOUND_BASE = base;
                    break;
                }
                base = base.wrapping_add(4);
            }
        }

        if FOUND_BASE == 0 {
            SCAN_CURSOR = first + count * 4;
            if SCAN_CURSOR >= SCAN_END {
                advance_phase();
            }
        }
    }
}

pub fn run_frame() {
    pnp::set_print_max_len(31);
    scan_chunk();

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
        pnp::println!(color = 0x005FFF, "BLUE MINIMAL STAGE3");
        pnp::println!("WRAM fingerprint search");
        pnp::println!("HostF {}", HOST_FRAME);

        if FOUND_BASE != 0 {
            let base = FOUND_BASE;
            let dv_hi = read_u8(base + OFF_ENEMY_DV_ATK_DEF);
            let dv_lo = read_u8(base + OFF_ENEMY_DV_SPE_SPC);
            pnp::println!(color = 0x00CC00, "WRAM FOUND {:08X}", base);
            pnp::println!("SIG 01 83 83 46");
            pnp::println!("DV {:02X}{:02X}", dv_hi, dv_lo);
            pnp::println!("FOUND locked");
        } else {
            pnp::println!("Range 08B00000-08C00000");
            pnp::println!("Scan {:08X} A{} P{}", SCAN_CURSOR, ALIGN_PHASE, FULL_PASSES);
            pnp::println!("Enter Mewtwo battle");
            pnp::println!("Leave battle screen open");
        }
    }
}
