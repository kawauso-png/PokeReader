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

// One-shot same-frame differential probe used to locate cycle/subtick state.
//
// The old wide probe compared consecutive 02B6 samples, so fast accumulators
// unrelated to DIV could look promising.  This probe instead snapshots one
// 64 KiB emulator-state region at the first VBlank rDIV read (02B5/02B6), then
// compares the exact same region at the second read of that same VBlank
// (02BD/02BE).  Only changed bytes are retained.  The emulated CPU is stopped
// while the host memcpy runs, so the pair still brackets the same LR35902
// instruction interval even though host wall-clock time is perturbed.
pub const DIFF_REGION_BASE: u32 = 0x00220000;
pub const DIFF_REGION_LEN: usize = 0x10000;
pub const DIFF_MAX_CHANGES: usize = 2048;

#[derive(Clone, Copy, Default)]
pub struct DiffMeta {
    pub region_base: u32,
    pub region_len: u32,
    pub valid: u8,
    pub completed: u8,
    pub pair_ok: u8,
    pub start_pc: u16,
    pub end_pc: u16,
    pub start_advance: u32,
    pub end_advance: u32,
    pub start_div: u8,
    pub end_div: u8,
    pub start_tick: u64,
    pub end_tick: u64,
    pub total_changes: u32,
    pub stored_changes: u32,
}

#[derive(Clone, Copy)]
pub struct DiffEntry {
    pub offset: u16,
    pub before: u8,
    pub after: u8,
    // Little-endian views starting at this changed byte.  These make it
    // possible to recognize a 16/32-bit counter even when only its low byte
    // changed during the 02B6 -> 02BE interval.
    pub before16: u16,
    pub after16: u16,
    pub before32: u32,
    pub after32: u32,
}

impl DiffEntry {
    const EMPTY: Self = Self {
        offset: 0,
        before: 0,
        after: 0,
        before16: 0,
        after16: 0,
        before32: 0,
        after32: 0,
    };
}

static mut DIFF_BEFORE: [u8; DIFF_REGION_LEN] = [0; DIFF_REGION_LEN];
static mut DIFF_AFTER: [u8; DIFF_REGION_LEN] = [0; DIFF_REGION_LEN];
static mut DIFF_ENTRIES: [DiffEntry; DIFF_MAX_CHANGES] =
    [DiffEntry::EMPTY; DIFF_MAX_CHANGES];
static mut DIFF_META: DiffMeta = DiffMeta {
    region_base: DIFF_REGION_BASE,
    region_len: DIFF_REGION_LEN as u32,
    valid: 0,
    completed: 0,
    pair_ok: 0,
    start_pc: 0,
    end_pc: 0,
    start_advance: 0,
    end_advance: 0,
    start_div: 0,
    end_div: 0,
    start_tick: 0,
    end_tick: 0,
    total_changes: 0,
    stored_changes: 0,
};
static mut DIFF_ARMED: bool = false;
static mut DIFF_PENDING: bool = false;

fn diff_region_mapped() -> bool {
    // Check every 4 KiB page rather than assuming that matching endpoints mean
    // the full 64 KiB range is readable.
    for offset in (0..DIFF_REGION_LEN).step_by(0x1000) {
        if !pnp::is_memory_mapped(DIFF_REGION_BASE + offset as u32) {
            return false;
        }
    }
    true
}

fn raw_le16(ptr: *const u8, offset: usize) -> u16 {
    unsafe {
        let b0 = core::ptr::read(ptr.add(offset)) as u16;
        let b1 = if offset + 1 < DIFF_REGION_LEN {
            core::ptr::read(ptr.add(offset + 1)) as u16
        } else {
            0
        };
        b0 | (b1 << 8)
    }
}

fn raw_le32(ptr: *const u8, offset: usize) -> u32 {
    unsafe {
        let mut value = 0u32;
        for i in 0..4usize {
            if offset + i < DIFF_REGION_LEN {
                value |= (core::ptr::read(ptr.add(offset + i)) as u32) << (i * 8);
            }
        }
        value
    }
}

fn diff_probe_start() {
    unsafe {
        DIFF_META = DiffMeta {
            region_base: DIFF_REGION_BASE,
            region_len: DIFF_REGION_LEN as u32,
            ..DiffMeta::default()
        };
        DIFF_ARMED = true;
        DIFF_PENDING = false;
    }
}

fn diff_probe_stop() {
    unsafe {
        DIFF_ARMED = false;
        DIFF_PENDING = false;
    }
}

fn diff_probe_clear() {
    unsafe {
        DIFF_META = DiffMeta {
            region_base: DIFF_REGION_BASE,
            region_len: DIFF_REGION_LEN as u32,
            ..DiffMeta::default()
        };
        DIFF_ARMED = false;
        DIFF_PENDING = false;
    }
}

pub fn diff_meta() -> DiffMeta {
    unsafe { DIFF_META }
}

pub fn diff_change_count() -> u32 {
    unsafe { DIFF_META.stored_changes }
}

pub fn diff_total_changes() -> u32 {
    unsafe { DIFF_META.total_changes }
}

pub fn diff_entry(index: usize) -> DiffEntry {
    unsafe {
        if index < DIFF_META.stored_changes.min(DIFF_MAX_CHANGES as u32) as usize {
            DIFF_ENTRIES[index]
        } else {
            DiffEntry::EMPTY
        }
    }
}

fn capture_diff_begin(pc: u16, div: u8, host_tick: u64) {
    unsafe {
        if !DIFF_ARMED || DIFF_PENDING || DIFF_META.completed != 0 {
            return;
        }
    }

    let valid = diff_region_mapped();
    unsafe {
        DIFF_META.region_base = DIFF_REGION_BASE;
        DIFF_META.region_len = DIFF_REGION_LEN as u32;
        DIFF_META.valid = valid as u8;
        DIFF_META.start_pc = pc;
        DIFF_META.start_advance = RNG_ADVANCE;
        DIFF_META.start_div = div;
        DIFF_META.start_tick = host_tick;
        DIFF_META.total_changes = 0;
        DIFF_META.stored_changes = 0;

        if !valid {
            DIFF_META.completed = 1;
            DIFF_ARMED = false;
            return;
        }

        let before = core::ptr::addr_of_mut!(DIFF_BEFORE).cast::<u8>();
        pnp::read_into_raw(DIFF_REGION_BASE, before, DIFF_REGION_LEN);
        DIFF_PENDING = true;
    }
}

fn capture_diff_end(pc: u16, div: u8, host_tick: u64) {
    unsafe {
        if !DIFF_ARMED || !DIFF_PENDING || DIFF_META.completed != 0 {
            return;
        }

        let after_ptr = core::ptr::addr_of_mut!(DIFF_AFTER).cast::<u8>();
        pnp::read_into_raw(DIFF_REGION_BASE, after_ptr, DIFF_REGION_LEN);
        let before_ptr = core::ptr::addr_of!(DIFF_BEFORE).cast::<u8>();
        let after_ptr_const = core::ptr::addr_of!(DIFF_AFTER).cast::<u8>();

        let mut total = 0u32;
        let mut stored = 0usize;
        for offset in 0..DIFF_REGION_LEN {
            let before = core::ptr::read(before_ptr.add(offset));
            let after = core::ptr::read(after_ptr_const.add(offset));
            if before == after {
                continue;
            }

            total = total.wrapping_add(1);
            if stored < DIFF_MAX_CHANGES {
                DIFF_ENTRIES[stored] = DiffEntry {
                    offset: offset as u16,
                    before,
                    after,
                    before16: raw_le16(before_ptr, offset),
                    after16: raw_le16(after_ptr_const, offset),
                    before32: raw_le32(before_ptr, offset),
                    after32: raw_le32(after_ptr_const, offset),
                };
                stored += 1;
            }
        }

        DIFF_META.end_pc = pc;
        DIFF_META.end_advance = RNG_ADVANCE;
        DIFF_META.end_div = div;
        DIFF_META.end_tick = host_tick;
        // RNG_ADVANCE increments immediately after the first VBlank read, so
        // the second read of the same VBlank should observe start+1.
        DIFF_META.pair_ok =
            (RNG_ADVANCE == DIFF_META.start_advance.wrapping_add(1)) as u8;
        DIFF_META.total_changes = total;
        DIFF_META.stored_changes = stored as u32;
        DIFF_META.completed = 1;
        DIFF_PENDING = false;
        DIFF_ARMED = false;
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
    diff_probe_start();
}

pub fn deep_log_stop() {
    unsafe { DEEP_LOGGING = false };
    diff_probe_stop();
}

/// Clear stale deep samples as well as stopping capture.  Regular Trace saves
/// must never inherit Deep rows from a previous Suicune probe.
pub fn deep_log_clear() {
    unsafe {
        DEEP_WRITE = 0;
        DEEP_COUNT = 0;
        DEEP_LOGGING = false;
    }
    diff_probe_clear();
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
        capture_diff_begin(pc, div, host_tick);
        unsafe { ADIV = div };
        unsafe { ACYCLES = CYCLE_COUNTER };
        unsafe { ATICKS = host_tick };

        unsafe { ADD_DIV_TRACKER.update(div) };
        unsafe { RNG_ADVANCE = RNG_ADVANCE.wrapping_add(1) };
    }
    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();
        capture_diff_end(pc, div, host_tick);
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
    // with the differential metadata.
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
