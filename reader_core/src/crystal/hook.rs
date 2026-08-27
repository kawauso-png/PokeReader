use super::reader::Gen2Reader;
use crate::utils;

const DIV_INCREMENTS: [u8; 16] = [
    0x12, 0x12, 0x12, 0x13, 0x12, 0x12, 0x13, 0x12, 0x12, 0x13, 0x12, 0x12, 0x13, 0x12, 0x12, 0x13,
];

// Don't worry, I don't feel great about this either
// This is hacky while explorations are happening
static mut RNG_ADVANCE: u32 = 0;
static mut ADIV: u8 = 0;
static mut SDIV: u8 = 0;
static mut CYCLE_COUNTER: u32 = 0;
// Cycle counter sampled at the moment each of the two VBlank rDIV reads
// happens. The difference between these and the frame boundary is the
// sub-tick position that the DIV byte alone cannot show.
static mut ACYCLES: u32 = 0;
static mut SCYCLES: u32 = 0;

// Diagnostics for the Japanese release: is the hook firing at all, and what
// program counter does it see when the game reads the DIV register?
static mut FF04_HITS: u32 = 0;
static mut ANY_HITS: u32 = 0;
static mut LAST_PC: u16 = 0;
static mut PC_SEEN_1: u16 = 0;
static mut PC_SEEN_2: u16 = 0;

// Per-Random-call log. The hook fires on every rDIV read, which is exactly
// once per Random call, so this captures the intra-frame calls that a
// per-frame trace cannot see. Ring buffer: the tail is what matters.
// 12 bytes an entry. Sized to cover a full 8192 frame trace: a map transition
// puts the stall region far from the tail, so a short ring would drop it.
pub const CALL_LOG_LEN: usize = 16384;

#[derive(Clone, Copy, Default)]
pub struct CallEntry {
    pub pc: u16,
    pub div: u16,
    pub add: u8,
    pub sub: u8,
    pub advance: u32,
    pub cycles: u32,
}

static mut CALL_LOG: [CallEntry; CALL_LOG_LEN] = [CallEntry {
    pc: 0,
    div: 0,
    add: 0,
    sub: 0,
    advance: 0,
    cycles: 0,
}; CALL_LOG_LEN];
static mut CALL_WRITE: usize = 0;
static mut CALL_COUNT: u32 = 0;
static mut CALL_LOGGING: bool = false;

pub fn call_log_start() {
    unsafe {
        CALL_WRITE = 0;
        CALL_COUNT = 0;
        CALL_LOGGING = true;
    }
}

pub fn call_log_stop() {
    unsafe { CALL_LOGGING = false };
}

pub fn call_log_count() -> u32 {
    unsafe { CALL_COUNT }
}

/// Entries in order, oldest first, capped at the ring size.
pub fn call_log_entry(index: usize) -> CallEntry {
    unsafe {
        let total = CALL_COUNT as usize;
        let len = total.min(CALL_LOG_LEN);
        let start = if total > CALL_LOG_LEN {
            CALL_WRITE
        } else {
            0
        };
        CALL_LOG[(start + index) % CALL_LOG_LEN]
    }
}

pub fn ff04_hits() -> u32 {
    unsafe { FF04_HITS }
}

pub fn any_hits() -> u32 {
    unsafe { ANY_HITS }
}

pub fn last_pc() -> u16 {
    unsafe { LAST_PC }
}

pub fn pc_seen() -> (u16, u16) {
    unsafe { (PC_SEEN_1, PC_SEEN_2) }
}

pub fn measured_div() -> u16 {
    unsafe { (ADIV as u16) << 8 | SDIV as u16 }
}

/// Cycle counter as of the first VBlank rDIV read of the current frame.
pub fn adiv_cycles() -> u32 {
    unsafe { ACYCLES }
}

/// Cycle counter as of the second VBlank rDIV read of the current frame.
pub fn sdiv_cycles() -> u32 {
    unsafe { SCYCLES }
}

/// Raw accumulated cycle counter. Stays at zero if the counter hook never
/// fires, which is how to tell that its address is wrong for this release.
pub fn cycle_counter() -> u32 {
    unsafe { CYCLE_COUNTER }
}

pub fn rng_advance() -> u32 {
    unsafe { RNG_ADVANCE }
}

pub fn reset_rng_advance() {
    unsafe { RNG_ADVANCE = 0 };
}

// This isn't currently used, but it's been helpful
fn update_cycle_counter(regs: &[u32], _stack_pointer: *mut u32) {
    let cycle_counter = regs[0];
    unsafe { CYCLE_COUNTER = CYCLE_COUNTER.wrapping_add(cycle_counter) };
}

#[repr(C)]
pub struct DivTracker {
    last_div: u8,
    index: usize,
    correct_index: bool,
}

impl DivTracker {
    const fn new() -> Self {
        Self {
            last_div: 0,
            index: 0,
            correct_index: false,
        }
    }

    fn update(&mut self, div: u8) {
        let small_index = self.index % DIV_INCREMENTS.len();
        let diff = div.wrapping_sub(self.last_div);
        self.last_div = div;

        if diff != 0x12 && diff != 0x13 {
            self.correct_index = false;
        }

        if diff != DIV_INCREMENTS[small_index]
            && [2, 3, 5, 6, 8, 9].contains(&(small_index))
            && (self.index >= DIV_INCREMENTS.len() || self.correct_index)
        {
            self.index = match small_index {
                2 => 1 + 0x562,
                3 => 1 + 0x563,
                5 => 1 + 0x22b5,
                6 => 1 + 0x22b6,
                8 => 1 + 8,
                9 => 1 + 9,
                _ => 0,
            };
            self.correct_index = true;
        } else if diff != DIV_INCREMENTS[small_index] {
            self.index = 0;
            self.correct_index = false;
        } else {
            self.index = (self.index + 1) % 0x4000;
        }
    }

    pub fn index(&self) -> Option<usize> {
        // Hides until ready
        match self.correct_index {
            true => Some(self.index),
            false => None,
        }
    }
}

static mut ADD_DIV_TRACKER: DivTracker = DivTracker::new();
static mut SUB_DIV_TRACKER: DivTracker = DivTracker::new();

pub fn add_div_tracker() -> &'static DivTracker {
    unsafe { &ADD_DIV_TRACKER }
}

pub fn sub_div_tracker() -> &'static DivTracker {
    unsafe { &SUB_DIV_TRACKER }
}

fn gb_read_mem(regs: &[u32], _stack_pointer: *mut u32) {
    unsafe { ANY_HITS = ANY_HITS.wrapping_add(1) };

    if regs[0] != 0xff04 {
        return;
    }

    let reader = Gen2Reader::crystal();
    let pc = reader.pc_reg();

    unsafe {
        if CALL_LOGGING {
            let state = reader.rng_state();
            CALL_LOG[CALL_WRITE] = CallEntry {
                pc,
                div: reader.div() as u16,
                add: (state >> 8) as u8,
                sub: state as u8,
                advance: RNG_ADVANCE,
                cycles: CYCLE_COUNTER,
            };
            CALL_WRITE = (CALL_WRITE + 1) % CALL_LOG_LEN;
            CALL_COUNT = CALL_COUNT.wrapping_add(1);
        }

        FF04_HITS = FF04_HITS.wrapping_add(1);
        LAST_PC = pc;
        if PC_SEEN_1 == 0 || PC_SEEN_1 == pc {
            PC_SEEN_1 = pc;
        } else if PC_SEEN_2 == 0 || PC_SEEN_2 == pc {
            PC_SEEN_2 = pc;
        }
    }
    // The VBlank RNG update reads rDIV twice, from opcodes at 0x2b5 and 0x2bd.
    // The program counter observed at the hook is one of the two bytes of each
    // instruction depending on the release, so accept both.
    const RNG_DIV_READ_1: [u16; 2] = [0x2b5, 0x2b6];
    const RNG_DIV_READ_2: [u16; 2] = [0x2bd, 0x2be];
    if RNG_DIV_READ_1.contains(&pc) {
        let div = reader.div();
        unsafe { ADIV = div };
        unsafe { ACYCLES = CYCLE_COUNTER };

        unsafe { ADD_DIV_TRACKER.update(div) };
        unsafe { RNG_ADVANCE = RNG_ADVANCE.wrapping_add(1) };
    }
    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();
        unsafe { SDIV = div };
        unsafe { SCYCLES = CYCLE_COUNTER };
        unsafe { SUB_DIV_TRACKER.update(div) };
    }
}

/// The `ldh a, [n8]` handler that reaches the GB memory read dispatcher sits at
/// a different call site on the Japanese release; 0x1af17c is never executed
/// there. Held in a static so the hook macro can be expanded once.
static mut GB_READ_MEM_HOOK: u32 = 0x1af17c;

pub fn init_crystal() {
    if let Ok(crate::title::LoadedTitle::CrystalJp) = crate::title::loaded_title() {
        unsafe { GB_READ_MEM_HOOK = 0x1af11c };
    }

    utils::hook_game_branch!(
        game_name = crystal,
        update_cycle_counter = 0x1a8360,
        gb_read_mem = GB_READ_MEM_HOOK,
    );
}
