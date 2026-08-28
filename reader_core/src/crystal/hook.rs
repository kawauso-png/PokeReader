use super::reader::Gen2Reader;
use crate::{pnp, utils};

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
// High-resolution host tick at the same two VBlank rDIV reads.  The legacy
// cycle hook is currently zero on JP VC, so these provide a safe timing
// fallback without guessing and patching an unverified emulator code address.
static mut ATICKS: u64 = 0;
static mut STICKS: u64 = 0;

// Diagnostics for the legacy cycle hook.  On JP VC the accumulated counter
// has stayed at zero.  Recording both the original instruction word and the
// hook macro's resolved return address tells us whether 0x1A8360 was actually
// a BL call site without trying risky alternate addresses.
static mut CYC_HOOK_WORD: u32 = 0;
static mut CYC_HOOK_RET: u32 = 0;

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
    pub host_tick: u64,
}

// Deep Suicune probe.  Unlike CALL_LOG, this only samples the first rDIV read
// inside Random (02:2F60 on the Japanese VC).  That keeps the hot-path cost
// low while preserving enough host/emulator state to identify the hidden
// 3-call/4-call branch with only a few trials.
//
// The snapshots deliberately include raw emulator context bytes instead of
// pretending that every field's meaning is already known.  In particular,
// CRYSTAL_CPU_CTX_BASE contains the known emulated PC at offset 0x1c; nearby
// bytes are strong candidates for the other LR35902 registers, including SP.
// The complete HRAM snapshot then lets an offline analyzer recover the GB
// return address once SP is identified.
pub const DEEP_LOG_LEN: usize = 256;
const CRYSTAL_CPU_CTX_BASE: u32 = 0x0022f5e0;
const CRYSTAL_WRAM0_PTR: u32 = 0x0022f6c8;
const CRYSTAL_HRAM_PTR: u32 = 0x0022f6d8;
const CPU_CTX_LEN: usize = 64;
const WRAM_SNAPSHOT_LEN: usize = 128; // D200-D27F
const HRAM_SNAPSHOT_LEN: usize = 128; // FF80-FFFF
const HOST_STACK_WORDS: usize = 8;

// Short-lived wide snapshot used only to locate the emulator's internal
// 16-bit DIV counter.  Eight first-VBlank samples are enough to correlate the
// visible DIV byte with the missing low byte while keeping probe overhead
// bounded.  The 1 KiB context window covers 0x22F400..0x22F7FF, including the
// known emulator-side pointers around 0x22F6xx/0x22F794.  A second 512-byte
// window is centered around the host byte pointer that Gen2Reader already uses
// to read rDIV.
pub const WIDE_LOG_LEN: usize = 8;
pub const CTX_WIDE_BASE: u32 = 0x0022f400;
pub const CTX_WIDE_LEN: usize = 1024;
pub const DIV_NEAR_LEN: usize = 512;
const DIV_NEAR_BEFORE: u32 = 0x100;

#[derive(Clone, Copy, Default)]
pub struct WideMeta {
    pub pc: u16,
    pub advance: u32,
    pub div: u8,
    pub host_tick: u64,
    pub div_ptr: u32,
    pub ctx_base: u32,
    pub ctx_valid: u8,
    pub near_base: u32,
    pub near_valid: u8,
}

static mut WIDE_META: [WideMeta; WIDE_LOG_LEN] = [WideMeta {
    pc: 0,
    advance: 0,
    div: 0,
    host_tick: 0,
    div_ptr: 0,
    ctx_base: CTX_WIDE_BASE,
    ctx_valid: 0,
    near_base: 0,
    near_valid: 0,
}; WIDE_LOG_LEN];
static mut WIDE_CTX: [[u8; CTX_WIDE_LEN]; WIDE_LOG_LEN] = [[0; CTX_WIDE_LEN]; WIDE_LOG_LEN];
static mut WIDE_NEAR: [[u8; DIV_NEAR_LEN]; WIDE_LOG_LEN] = [[0; DIV_NEAR_LEN]; WIDE_LOG_LEN];
static mut WIDE_COUNT: u32 = 0;
static mut WIDE_LOGGING: bool = false;

fn wide_log_start() {
    unsafe {
        WIDE_COUNT = 0;
        WIDE_LOGGING = true;
    }
}

fn wide_log_stop() {
    unsafe { WIDE_LOGGING = false };
}

fn wide_log_clear() {
    unsafe {
        WIDE_COUNT = 0;
        WIDE_LOGGING = false;
    }
}

pub fn wide_log_count() -> u32 {
    unsafe { WIDE_COUNT.min(WIDE_LOG_LEN as u32) }
}

pub fn wide_log_meta(index: usize) -> WideMeta {
    unsafe {
        if index < WIDE_COUNT.min(WIDE_LOG_LEN as u32) as usize {
            WIDE_META[index]
        } else {
            WideMeta::default()
        }
    }
}

pub fn wide_ctx_byte(index: usize, offset: usize) -> u8 {
    unsafe {
        if index < WIDE_COUNT.min(WIDE_LOG_LEN as u32) as usize && offset < CTX_WIDE_LEN {
            WIDE_CTX[index][offset]
        } else {
            0
        }
    }
}

pub fn wide_near_byte(index: usize, offset: usize) -> u8 {
    unsafe {
        if index < WIDE_COUNT.min(WIDE_LOG_LEN as u32) as usize && offset < DIV_NEAR_LEN {
            WIDE_NEAR[index][offset]
        } else {
            0
        }
    }
}

fn capture_wide_vblank(reader: &Gen2Reader, pc: u16, div: u8, host_tick: u64) {
    let index = unsafe {
        if !WIDE_LOGGING || WIDE_COUNT as usize >= WIDE_LOG_LEN {
            WIDE_LOGGING = false;
            return;
        }
        WIDE_COUNT as usize
    };

    let div_ptr = reader.div_host_ptr();
    let near_base = div_ptr.saturating_sub(DIV_NEAR_BEFORE);
    let ctx_valid = pnp::is_memory_mapped(CTX_WIDE_BASE)
        && pnp::is_memory_mapped(CTX_WIDE_BASE + CTX_WIDE_LEN as u32 - 1);
    let near_valid = div_ptr != 0
        && pnp::is_memory_mapped(near_base)
        && pnp::is_memory_mapped(near_base + DIV_NEAR_LEN as u32 - 1);

    unsafe {
        let ctx_out = core::ptr::addr_of_mut!(WIDE_CTX)
            .cast::<u8>()
            .add(index * CTX_WIDE_LEN);
        core::ptr::write_bytes(ctx_out, 0, CTX_WIDE_LEN);
        if ctx_valid {
            pnp::read_into_raw(CTX_WIDE_BASE, ctx_out, CTX_WIDE_LEN);
        }

        let near_out = core::ptr::addr_of_mut!(WIDE_NEAR)
            .cast::<u8>()
            .add(index * DIV_NEAR_LEN);
        core::ptr::write_bytes(near_out, 0, DIV_NEAR_LEN);
        if near_valid {
            pnp::read_into_raw(near_base, near_out, DIV_NEAR_LEN);
        }

        WIDE_META[index] = WideMeta {
            pc,
            advance: RNG_ADVANCE,
            div,
            host_tick,
            div_ptr,
            ctx_base: CTX_WIDE_BASE,
            ctx_valid: ctx_valid as u8,
            near_base: if near_valid { near_base } else { 0 },
            near_valid: near_valid as u8,
        };
        WIDE_COUNT = WIDE_COUNT.wrapping_add(1);
        if WIDE_COUNT as usize >= WIDE_LOG_LEN {
            WIDE_LOGGING = false;
        }
    }
}

#[derive(Clone, Copy)]
pub struct DeepEntry {
    pub pc: u16,
    pub div: u16,
    pub add: u8,
    pub sub: u8,
    pub advance: u32,
    pub cycles: u32,
    pub host_tick: u64,
    pub regs: [u32; 15],
    pub host_stack: [u32; HOST_STACK_WORDS],
    pub cpu_ctx: [u8; CPU_CTX_LEN],
    pub wram_d200: [u8; WRAM_SNAPSHOT_LEN],
    pub hram: [u8; HRAM_SNAPSHOT_LEN],
}

impl DeepEntry {
    const EMPTY: Self = Self {
        pc: 0,
        div: 0,
        add: 0,
        sub: 0,
        advance: 0,
        cycles: 0,
        host_tick: 0,
        regs: [0; 15],
        host_stack: [0; HOST_STACK_WORDS],
        cpu_ctx: [0; CPU_CTX_LEN],
        wram_d200: [0; WRAM_SNAPSHOT_LEN],
        hram: [0; HRAM_SNAPSHOT_LEN],
    };
}

static mut DEEP_LOG: [DeepEntry; DEEP_LOG_LEN] = [DeepEntry::EMPTY; DEEP_LOG_LEN];
static mut DEEP_WRITE: usize = 0;
static mut DEEP_COUNT: u32 = 0;
static mut DEEP_LOGGING: bool = false;

pub fn deep_log_start() {
    unsafe {
        DEEP_WRITE = 0;
        DEEP_COUNT = 0;
        DEEP_LOGGING = true;
    }
    wide_log_start();
}

pub fn deep_log_stop() {
    unsafe { DEEP_LOGGING = false };
    wide_log_stop();
}

/// Clear stale deep samples as well as stopping capture.  Regular Trace saves
/// must never inherit Deep rows from a previous Suicune probe.
pub fn deep_log_clear() {
    unsafe {
        DEEP_WRITE = 0;
        DEEP_COUNT = 0;
        DEEP_LOGGING = false;
    }
    wide_log_clear();
}

pub fn deep_log_count() -> u32 {
    unsafe { DEEP_COUNT }
}

pub fn deep_log_entry(index: usize) -> DeepEntry {
    unsafe {
        let total = DEEP_COUNT as usize;
        let start = if total > DEEP_LOG_LEN { DEEP_WRITE } else { 0 };
        DEEP_LOG[(start + index) % DEEP_LOG_LEN]
    }
}

fn capture_deep_random(
    reader: &Gen2Reader,
    regs: &[u32],
    stack_pointer: *mut u32,
    pc: u16,
    host_tick: u64,
) {
    // Only one snapshot per Random call.  2F68 is the second rDIV read of the
    // same call and would nearly double the overhead without adding much.
    if pc != 0x2f60 {
        return;
    }

    unsafe {
        if !DEEP_LOGGING {
            return;
        }
    }

    let mut saved_regs = [0u32; 15];
    for (dst, src) in saved_regs.iter_mut().zip(regs.iter().take(15)) {
        *dst = *src;
    }

    let mut saved_stack = [0u32; HOST_STACK_WORDS];
    unsafe {
        for (i, slot) in saved_stack.iter_mut().enumerate() {
            *slot = core::ptr::read_volatile(stack_pointer.add(i));
        }
    }

    // These are direct host-memory copies, not calls back through the GB memory
    // dispatcher.  That avoids recursive hook traffic and keeps probe timing
    // much lighter than reading 128 GB addresses one by one.
    let cpu_ctx = pnp::read_array::<CPU_CTX_LEN>(CRYSTAL_CPU_CTX_BASE);

    let mut wram_d200 = [0u8; WRAM_SNAPSHOT_LEN];
    let wram0 = pnp::read::<u32>(CRYSTAL_WRAM0_PTR);
    if pnp::is_memory_mapped(wram0) {
        wram_d200 = pnp::read_array::<WRAM_SNAPSHOT_LEN>(wram0.wrapping_add(0x1200));
    }

    let mut hram = [0u8; HRAM_SNAPSHOT_LEN];
    let hram_base = pnp::read::<u32>(CRYSTAL_HRAM_PTR);
    if pnp::is_memory_mapped(hram_base) {
        hram = pnp::read_array::<HRAM_SNAPSHOT_LEN>(hram_base);
    }

    let state = reader.rng_state();
    let entry = DeepEntry {
        pc,
        div: reader.div() as u16,
        add: (state >> 8) as u8,
        sub: state as u8,
        advance: rng_advance(),
        cycles: cycle_counter(),
        host_tick,
        regs: saved_regs,
        host_stack: saved_stack,
        cpu_ctx,
        wram_d200,
        hram,
    };

    unsafe {
        DEEP_LOG[DEEP_WRITE] = entry;
        DEEP_WRITE = (DEEP_WRITE + 1) % DEEP_LOG_LEN;
        DEEP_COUNT = DEEP_COUNT.wrapping_add(1);
    }
}

static mut CALL_LOG: [CallEntry; CALL_LOG_LEN] = [CallEntry {
    pc: 0,
    div: 0,
    add: 0,
    sub: 0,
    advance: 0,
    cycles: 0,
    host_tick: 0,
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

/// High-resolution host tick at the first VBlank rDIV read.
pub fn adiv_tick() -> u64 {
    unsafe { ATICKS }
}

/// High-resolution host tick at the second VBlank rDIV read.
pub fn sdiv_tick() -> u64 {
    unsafe { STICKS }
}

/// Raw accumulated cycle counter. Stays at zero if the counter hook never
/// fires, which is how to tell that its address is wrong for this release.
pub fn cycle_counter() -> u32 {
    unsafe { CYCLE_COUNTER }
}

pub fn cyc_hook_word() -> u32 {
    unsafe { CYC_HOOK_WORD }
}

pub fn cyc_hook_ret() -> u32 {
    unsafe { CYC_HOOK_RET }
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
    // Sample once and reuse the value for every record produced by this rDIV
    // hook.  This keeps the hot-path overhead deterministic.
    let host_tick = pnp::system_tick();

    capture_deep_random(&reader, regs, _stack_pointer, pc, host_tick);

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
                host_tick,
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
        capture_wide_vblank(&reader, pc, div, host_tick);
        unsafe { ADIV = div };
        unsafe { ACYCLES = CYCLE_COUNTER };
        unsafe { ATICKS = host_tick };

        unsafe { ADD_DIV_TRACKER.update(div) };
        unsafe { RNG_ADVANCE = RNG_ADVANCE.wrapping_add(1) };
    }
    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();
        unsafe { SDIV = div };
        unsafe { SCYCLES = CYCLE_COUNTER };
        unsafe { STICKS = host_tick };
        unsafe { SUB_DIV_TRACKER.update(div) };
    }
}

/// The `ldh a, [n8]` handler that reaches the GB memory read dispatcher sits at
/// a different call site on the Japanese release; 0x1af17c is never executed
/// there. Held in a static so the hook macro can be expanded once.
static mut GB_READ_MEM_HOOK: u32 = 0x1af17c;

pub fn init_crystal() {
    // Read the instruction before hook_game_branch potentially rewrites it.
    // If this is not an ARM BL (top byte EB), replace_arm_branch intentionally
    // leaves it untouched and returns 0; the pair is shown on Trace and saved
    // with the wide samples.
    unsafe { CYC_HOOK_WORD = pnp::read::<u32>(0x1a8360) };

    if let Ok(crate::title::LoadedTitle::CrystalJp) = crate::title::loaded_title() {
        unsafe { GB_READ_MEM_HOOK = 0x1af11c };
    }

    utils::hook_game_branch!(
        game_name = crystal,
        update_cycle_counter = 0x1a8360,
        gb_read_mem = GB_READ_MEM_HOOK,
    );

    unsafe { CYC_HOOK_RET = update_cycle_counter::return_addr };
}
