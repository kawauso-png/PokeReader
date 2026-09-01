use core::fmt::Write;

use super::{
    hook::{
        adiv_subtick, adiv_tick, call_log_count, call_log_entry, call_log_stop, measured_div,
        rng_advance, sdiv_subtick, CALL_LOG_LEN,
    },
    reader::Gen2Reader,
};
use crate::pnp;

/// One-shot comprehensive boot trace.
///
/// Design rule:
/// - lightweight state is sampled every presented frame;
/// - expensive full HRAM / CPU / WRAM snapshots are taken only on important
///   edges (physical input, Crystal input edge, menu/map mode change, RNG
///   stall start/end, first RNG activation, or Random() activity).
/// This maximizes information per cold boot without putting heavy copies on
/// every frame or inside the rDIV hook itself.
const MAX_BOOT_FRAMES: usize = 4096;
const MAX_EVENTS: usize = 192;

const CPU_CTX_BASE: u32 = 0x0022_f5e0;
const WRAM0_PTR_SLOT: u32 = 0x0022_f6c8;
const HRAM_PTR_SLOT: u32 = 0x0022_f6d8;
const CPU_CTX_LEN: usize = 64;
const HRAM_LEN: usize = 128;
const WRAM_LEN: usize = 128; // D200-D27F

// Crystal HRAM addresses, FF80-based. Keep this table explicit so offline
// analysis never has to infer which revision/layout was sampled.
//
// FF90 hVBlankCounter
// FF92 hROMBank
// FF93 hVBlank
// FF94 hMapEntryMethod
// FF95 hMenuReturn
// FF97 hJoypadReleased
// FF98 hJoypadPressed
// FF99 hJoypadDown
// FF9A hJoypadSum
// FF9B hJoyReleased
// FF9C hJoyPressed
// FF9D hJoyDown
// FF9E hJoyLast
// FF9F hInMenu
// FFE1 hRandomAdd
// FFE2 hRandomSub
const OFF_RTC_DAY_HI: usize = 0x03;
const OFF_RTC_DAY_LO: usize = 0x04;
const OFF_RTC_HOURS: usize = 0x05;
const OFF_RTC_MINUTES: usize = 0x06;
const OFF_RTC_SECONDS: usize = 0x07;
const OFF_H_HOURS: usize = 0x0a;
const OFF_H_MINUTES: usize = 0x0c;
const OFF_H_SECONDS: usize = 0x0e;
const OFF_VBLANK_COUNTER: usize = 0x10;
const OFF_ROM_BANK: usize = 0x12;
const OFF_VBLANK: usize = 0x13;
const OFF_MAP_ENTRY: usize = 0x14;
const OFF_MENU_RETURN: usize = 0x15;
const OFF_JOYPAD_RELEASED: usize = 0x17;
const OFF_JOYPAD_PRESSED: usize = 0x18;
const OFF_JOYPAD_DOWN: usize = 0x19;
const OFF_JOYPAD_SUM: usize = 0x1a;
const OFF_JOY_RELEASED: usize = 0x1b;
const OFF_JOY_PRESSED: usize = 0x1c;
const OFF_JOY_DOWN: usize = 0x1d;
const OFF_JOY_LAST: usize = 0x1e;
const OFF_IN_MENU: usize = 0x1f;
const OFF_RANDOM_ADD: usize = 0x61;
const OFF_RANDOM_SUB: usize = 0x62;

const EV_FIRST: u32 = 1 << 0;
const EV_PHYS_KEYS: u32 = 1 << 1;
const EV_JOY_EDGE: u32 = 1 << 2;
const EV_MAP: u32 = 1 << 3;
const EV_MENU: u32 = 1 << 4;
const EV_VBLANK_MODE: u32 = 1 << 5;
const EV_STALL_START: u32 = 1 << 6;
const EV_STALL_END: u32 = 1 << 7;
const EV_RANDOM: u32 = 1 << 8;
const EV_RNG_START: u32 = 1 << 9;
const EV_ADV_RESET: u32 = 1 << 10;

#[derive(Clone, Copy)]
struct LightHram {
    valid: u8,
    rtc_day_hi: u8,
    rtc_day_lo: u8,
    rtc_hours: u8,
    rtc_minutes: u8,
    rtc_seconds: u8,
    hours: u8,
    minutes: u8,
    seconds: u8,
    vblank_counter: u8,
    rom_bank: u8,
    vblank: u8,
    map_entry: u8,
    menu_return: u8,
    joypad_released: u8,
    joypad_pressed: u8,
    joypad_down: u8,
    joypad_sum: u8,
    joy_released: u8,
    joy_pressed: u8,
    joy_down: u8,
    joy_last: u8,
    in_menu: u8,
    random_add: u8,
    random_sub: u8,
}

impl LightHram {
    const EMPTY: Self = Self {
        valid: 0,
        rtc_day_hi: 0,
        rtc_day_lo: 0,
        rtc_hours: 0,
        rtc_minutes: 0,
        rtc_seconds: 0,
        hours: 0,
        minutes: 0,
        seconds: 0,
        vblank_counter: 0,
        rom_bank: 0,
        vblank: 0,
        map_entry: 0,
        menu_return: 0,
        joypad_released: 0,
        joypad_pressed: 0,
        joypad_down: 0,
        joypad_sum: 0,
        joy_released: 0,
        joy_pressed: 0,
        joy_down: 0,
        joy_last: 0,
        in_menu: 0,
        random_add: 0,
        random_sub: 0,
    };
}

#[derive(Clone, Copy)]
struct BootFrame {
    advance: u32,
    state: u16,
    div: u16,
    keys: u16,
    pc: u16,
    asub: u8,
    ssub: u8,
    atick: u64,
    call_count: u32,
    hram: LightHram,
}

impl BootFrame {
    const EMPTY: Self = Self {
        advance: 0,
        state: 0,
        div: 0,
        keys: 0,
        pc: 0,
        asub: 0,
        ssub: 0,
        atick: 0,
        call_count: 0,
        hram: LightHram::EMPTY,
    };
}

#[derive(Clone, Copy)]
struct EventSnapshot {
    frame_index: u32,
    reasons: u32,
    advance: u32,
    state: u16,
    div: u16,
    keys: u16,
    pc: u16,
    asub: u8,
    ssub: u8,
    host_tick: u64,
    call_count: u32,
    snapshot_tick_before: u64,
    snapshot_tick_after: u64,
    hram_valid: u8,
    cpu_valid: u8,
    wram_valid: u8,
    hram: [u8; HRAM_LEN],
    cpu_ctx: [u8; CPU_CTX_LEN],
    wram_d200: [u8; WRAM_LEN],
}

impl EventSnapshot {
    const EMPTY: Self = Self {
        frame_index: 0,
        reasons: 0,
        advance: 0,
        state: 0,
        div: 0,
        keys: 0,
        pc: 0,
        asub: 0,
        ssub: 0,
        host_tick: 0,
        call_count: 0,
        snapshot_tick_before: 0,
        snapshot_tick_after: 0,
        hram_valid: 0,
        cpu_valid: 0,
        wram_valid: 0,
        hram: [0; HRAM_LEN],
        cpu_ctx: [0; CPU_CTX_LEN],
        wram_d200: [0; WRAM_LEN],
    };
}

static mut BOOT_FRAMES: [BootFrame; MAX_BOOT_FRAMES] = [BootFrame::EMPTY; MAX_BOOT_FRAMES];
static mut EVENTS: [EventSnapshot; MAX_EVENTS] = [EventSnapshot::EMPTY; MAX_EVENTS];

struct LineBuf {
    buf: [u8; 1024],
    len: usize,
}

impl LineBuf {
    fn new() -> Self {
        Self {
            buf: [0; 1024],
            len: 0,
        }
    }

    fn clear(&mut self) {
        self.len = 0;
    }

    fn as_bytes(&self) -> &[u8] {
        &self.buf[..self.len]
    }
}

impl Write for LineBuf {
    fn write_str(&mut self, s: &str) -> core::fmt::Result {
        for byte in s.as_bytes() {
            if self.len >= self.buf.len() {
                return Err(core::fmt::Error);
            }
            self.buf[self.len] = *byte;
            self.len += 1;
        }
        Ok(())
    }
}

fn m14(div: u8, subtick: u8) -> u16 {
    (((div as u16) << 6) | ((subtick as u16) & 0x3f)) & 0x3fff
}

fn is_vblank_a(pc: u16) -> bool {
    pc == 0x02b5 || pc == 0x02b6
}

fn is_random_call(pc: u16) -> bool {
    pc == 0x2f60 || pc == 0x2f68
}

fn call_kind(pc: u16) -> &'static str {
    match pc {
        0x02b5 | 0x02b6 => "VB_A",
        0x02bd | 0x02be => "VB_S",
        0x2f60 => "RND_A",
        0x2f68 => "RND_S",
        _ => "DIV",
    }
}

fn reason_text(mask: u32) -> &'static str {
    match mask {
        EV_FIRST => "FIRST",
        EV_PHYS_KEYS => "PHYS",
        EV_JOY_EDGE => "JOY",
        EV_MAP => "MAP",
        EV_MENU => "MENU",
        EV_VBLANK_MODE => "VBLANK",
        EV_STALL_START => "STALL_START",
        EV_STALL_END => "STALL_END",
        EV_RANDOM => "RANDOM",
        EV_RNG_START => "RNG_START",
        EV_ADV_RESET => "ADV_RESET",
        _ => "MULTI",
    }
}

fn resolve_ptr(slot: u32) -> u32 {
    let ptr = pnp::read::<u32>(slot);
    if pnp::is_memory_mapped(ptr) {
        ptr
    } else {
        0
    }
}

fn read_light_hram(base: u32) -> LightHram {
    if base == 0 || !pnp::is_memory_mapped(base) {
        return LightHram::EMPTY;
    }

    // One small contiguous read for FF83-FFA2, plus two bytes for FFE1/FFE2.
    // This avoids many per-byte game-dispatch calls on every frame.
    let head = pnp::read_array::<32>(base.wrapping_add(OFF_RTC_DAY_HI as u32));
    let random = pnp::read_array::<2>(base.wrapping_add(OFF_RANDOM_ADD as u32));
    let at = |offset: usize| head[offset - OFF_RTC_DAY_HI];

    LightHram {
        valid: 1,
        rtc_day_hi: at(OFF_RTC_DAY_HI),
        rtc_day_lo: at(OFF_RTC_DAY_LO),
        rtc_hours: at(OFF_RTC_HOURS),
        rtc_minutes: at(OFF_RTC_MINUTES),
        rtc_seconds: at(OFF_RTC_SECONDS),
        hours: at(OFF_H_HOURS),
        minutes: at(OFF_H_MINUTES),
        seconds: at(OFF_H_SECONDS),
        vblank_counter: at(OFF_VBLANK_COUNTER),
        rom_bank: at(OFF_ROM_BANK),
        vblank: at(OFF_VBLANK),
        map_entry: at(OFF_MAP_ENTRY),
        menu_return: at(OFF_MENU_RETURN),
        joypad_released: at(OFF_JOYPAD_RELEASED),
        joypad_pressed: at(OFF_JOYPAD_PRESSED),
        joypad_down: at(OFF_JOYPAD_DOWN),
        joypad_sum: at(OFF_JOYPAD_SUM),
        joy_released: at(OFF_JOY_RELEASED),
        joy_pressed: at(OFF_JOY_PRESSED),
        joy_down: at(OFF_JOY_DOWN),
        joy_last: at(OFF_JOY_LAST),
        in_menu: at(OFF_IN_MENU),
        random_add: random[0],
        random_sub: random[1],
    }
}

fn write_hex<const N: usize>(line: &mut LineBuf, bytes: &[u8; N]) {
    for byte in bytes {
        let _ = write!(line, "{:02X}", byte);
    }
}

pub struct BootTrace {
    len: usize,
    event_len: usize,
    event_dropped: u32,
    frozen: bool,
    save_index: u32,
    save_result: Option<bool>,

    hram_base: u32,
    wram0_base: u32,

    prev_valid: bool,
    prev_keys: u16,
    prev_hram: LightHram,
    prev_advance: u32,
    prev_state: u16,
    prev_call_count: u32,
    stall_active: bool,
}

impl Default for BootTrace {
    fn default() -> Self {
        Self {
            len: 0,
            event_len: 0,
            event_dropped: 0,
            frozen: false,
            save_index: 1,
            save_result: None,
            hram_base: 0,
            wram0_base: 0,
            prev_valid: false,
            prev_keys: 0,
            prev_hram: LightHram::EMPTY,
            prev_advance: 0,
            prev_state: 0,
            prev_call_count: 0,
            stall_active: false,
        }
    }
}

impl BootTrace {
    fn random_since_previous_frame(&self, current_total: u32) -> bool {
        if current_total <= self.prev_call_count {
            return false;
        }

        let kept = (current_total as usize).min(CALL_LOG_LEN);
        let oldest_global = current_total.saturating_sub(kept as u32);
        let start_global = self.prev_call_count.max(oldest_global);

        for global_index in start_global..current_total {
            let local_index = global_index.saturating_sub(oldest_global) as usize;
            let e = call_log_entry(local_index);
            if is_random_call(e.pc) {
                return true;
            }
        }
        false
    }

    fn capture_event(&mut self, frame: &BootFrame, reasons: u32) {
        if reasons == 0 {
            return;
        }
        if self.event_len >= MAX_EVENTS {
            self.event_dropped = self.event_dropped.wrapping_add(1);
            return;
        }

        let before = pnp::system_tick();

        let (hram, hram_valid) = if self.hram_base != 0
            && pnp::is_memory_mapped(self.hram_base)
            && pnp::is_memory_mapped(self.hram_base.wrapping_add((HRAM_LEN - 1) as u32))
        {
            (pnp::read_array::<HRAM_LEN>(self.hram_base), 1)
        } else {
            ([0; HRAM_LEN], 0)
        };

        let (cpu_ctx, cpu_valid) = if pnp::is_memory_mapped(CPU_CTX_BASE)
            && pnp::is_memory_mapped(CPU_CTX_BASE.wrapping_add((CPU_CTX_LEN - 1) as u32))
        {
            (pnp::read_array::<CPU_CTX_LEN>(CPU_CTX_BASE), 1)
        } else {
            ([0; CPU_CTX_LEN], 0)
        };

        let wram_addr = self.wram0_base.wrapping_add(0x1200);
        let (wram_d200, wram_valid) = if self.wram0_base != 0
            && pnp::is_memory_mapped(wram_addr)
            && pnp::is_memory_mapped(wram_addr.wrapping_add((WRAM_LEN - 1) as u32))
        {
            (pnp::read_array::<WRAM_LEN>(wram_addr), 1)
        } else {
            ([0; WRAM_LEN], 0)
        };

        let after = pnp::system_tick();

        unsafe {
            EVENTS[self.event_len] = EventSnapshot {
                frame_index: self.len.saturating_sub(1) as u32,
                reasons,
                advance: frame.advance,
                state: frame.state,
                div: frame.div,
                keys: frame.keys,
                pc: frame.pc,
                asub: frame.asub,
                ssub: frame.ssub,
                host_tick: frame.atick,
                call_count: frame.call_count,
                snapshot_tick_before: before,
                snapshot_tick_after: after,
                hram_valid,
                cpu_valid,
                wram_valid,
                hram,
                cpu_ctx,
                wram_d200,
            };
        }
        self.event_len += 1;
    }

    /// Called before frame.rs applies the legacy 01FF/0101 logical advance reset.
    pub fn record_frame(&mut self, reader: &Gen2Reader) {
        if self.frozen || self.len >= MAX_BOOT_FRAMES {
            return;
        }

        if self.hram_base == 0 {
            self.hram_base = resolve_ptr(HRAM_PTR_SLOT);
        }
        if self.wram0_base == 0 {
            self.wram0_base = resolve_ptr(WRAM0_PTR_SLOT);
        }

        let advance = rng_advance();
        let state = reader.rng_state();
        let div = measured_div();
        let keys = pnp::current_keys() as u16;
        let pc = reader.pc_reg();
        let asub = adiv_subtick();
        let ssub = sdiv_subtick();
        let atick = adiv_tick();
        let call_count = call_log_count();
        let hram = read_light_hram(self.hram_base);

        let frame = BootFrame {
            advance,
            state,
            div,
            keys,
            pc,
            asub,
            ssub,
            atick,
            call_count,
            hram,
        };

        unsafe {
            BOOT_FRAMES[self.len] = frame;
        }
        self.len += 1;

        let random_seen = self.random_since_previous_frame(call_count);
        let mut reasons = 0u32;

        if !self.prev_valid {
            reasons |= EV_FIRST;
        } else {
            if keys != self.prev_keys {
                reasons |= EV_PHYS_KEYS;
            }

            if hram.valid != 0
                && (hram.joypad_pressed != 0
                    || hram.joypad_released != 0
                    || hram.joy_pressed != 0
                    || hram.joy_released != 0)
            {
                reasons |= EV_JOY_EDGE;
            }

            if hram.valid != 0
                && self.prev_hram.valid != 0
                && hram.map_entry != self.prev_hram.map_entry
            {
                reasons |= EV_MAP;
            }

            if hram.valid != 0
                && self.prev_hram.valid != 0
                && (hram.in_menu != self.prev_hram.in_menu
                    || hram.menu_return != self.prev_hram.menu_return)
            {
                reasons |= EV_MENU;
            }

            if hram.valid != 0
                && self.prev_hram.valid != 0
                && hram.vblank != self.prev_hram.vblank
            {
                reasons |= EV_VBLANK_MODE;
            }

            let same_rng = advance == self.prev_advance && state == self.prev_state;
            if same_rng && !self.stall_active {
                self.stall_active = true;
                reasons |= EV_STALL_START;
            } else if !same_rng && self.stall_active {
                self.stall_active = false;
                reasons |= EV_STALL_END;
            }

            if self.prev_state == 0 && state != 0 {
                reasons |= EV_RNG_START;
            }

            if advance < self.prev_advance {
                reasons |= EV_ADV_RESET;
            }
        }

        if random_seen {
            reasons |= EV_RANDOM;
        }

        self.capture_event(&frame, reasons);

        self.prev_valid = true;
        self.prev_keys = keys;
        self.prev_hram = hram;
        self.prev_advance = advance;
        self.prev_state = state;
        self.prev_call_count = call_count;
    }

    fn save(&mut self) {
        self.frozen = true;
        call_log_stop();

        let total = call_log_count() as usize;
        let shown = total.min(CALL_LOG_LEN);
        if self.len == 0 && shown == 0 {
            self.save_result = Some(false);
            return;
        }
        if !pnp::trace_file_open(self.save_index) {
            self.save_result = Some(false);
            return;
        }

        let mut line = LineBuf::new();
        let dropped = total.saturating_sub(shown);
        let first_tick = if shown > 0 {
            call_log_entry(0).host_tick
        } else {
            0
        };

        let mut zero_found = false;
        let mut zero_index = 0usize;
        let mut zero_div = 0u8;
        let mut zero_subtick = 0u8;
        let mut zero_tick = 0u64;
        let mut zero_count = 0u32;
        let mut reset_found = false;
        let mut reset_index = 0usize;
        let mut prev_advance = 0u32;
        let mut have_prev = false;
        let mut random_calls = 0u32;

        for i in 0..shown {
            let e = call_log_entry(i);
            if is_vblank_a(e.pc) && e.add == 0 && e.sub == 0 {
                zero_count = zero_count.wrapping_add(1);
                if !zero_found {
                    zero_found = true;
                    zero_index = total - shown + i;
                    zero_div = e.div as u8;
                    zero_subtick = e.mcycle;
                    zero_tick = e.host_tick;
                }
            }
            if is_random_call(e.pc) {
                random_calls = random_calls.wrapping_add(1);
            }
            if have_prev && !reset_found && e.advance < prev_advance {
                reset_found = true;
                reset_index = total - shown + i;
            }
            prev_advance = e.advance;
            have_prev = true;
        }

        let _ = write!(line, "mode,BOOT_ONESHOT_TRACE_V3\n");
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "summary,frames_kept,{},frame_capacity,{},calls_total,{},calls_kept,{},calls_dropped,{},random_calls,{},events_kept,{},events_capacity,{},events_dropped,{},hram_base,{:08X},wram0_base,{:08X}\n",
            self.len,
            MAX_BOOT_FRAMES,
            total,
            shown,
            dropped,
            random_calls,
            self.event_len,
            MAX_EVENTS,
            self.event_dropped,
            self.hram_base,
            self.wram0_base
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "address_map,hVBlankCounter,FF90,hROMBank,FF92,hVBlank,FF93,hMapEntryMethod,FF94,hMenuReturn,FF95,hJoypadReleased,FF97,hJoypadPressed,FF98,hJoypadDown,FF99,hJoypadSum,FF9A,hJoyReleased,FF9B,hJoyPressed,FF9C,hJoyDown,FF9D,hJoyLast,FF9E,hInMenu,FF9F,hRandomAdd,FFE1,hRandomSub,FFE2\n"
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "event_bits,FIRST,{:08X},PHYS,{:08X},JOY,{:08X},MAP,{:08X},MENU,{:08X},VBLANK,{:08X},STALL_START,{:08X},STALL_END,{:08X},RANDOM,{:08X},RNG_START,{:08X},ADV_RESET,{:08X}\n",
            EV_FIRST,
            EV_PHYS_KEYS,
            EV_JOY_EDGE,
            EV_MAP,
            EV_MENU,
            EV_VBLANK_MODE,
            EV_STALL_START,
            EV_STALL_END,
            EV_RANDOM,
            EV_RNG_START,
            EV_ADV_RESET
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "zero_vblank,found,{},count,{},call_index,{},div,{:02X},mcycle,{:02X},m14,{:04X},host_tick,{}\n",
            zero_found as u8,
            zero_count,
            zero_index,
            zero_div,
            zero_subtick,
            m14(zero_div, zero_subtick),
            zero_tick
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "advance_reset,found,{},call_index,{}\n\n",
            reset_found as u8,
            reset_index
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "frame_index,advance,state,div,asub,ssub,m14_a,m14_s,host_tick,call_count,pc,rom_bank,physical_keys,rtc_day_hi,rtc_day_lo,rtc_h,rtc_m,rtc_s,hours,minutes,seconds,h_vblank_counter,h_vblank,h_map_entry,h_menu_return,h_joypad_released,h_joypad_pressed,h_joypad_down,h_joypad_sum,h_joy_released,h_joy_pressed,h_joy_down,h_joy_last,h_in_menu,h_random_add,h_random_sub\n"
        );
        pnp::trace_file_write(line.as_bytes());

        for i in 0..self.len {
            let e = unsafe { BOOT_FRAMES[i] };
            line.clear();
            let _ = write!(
                line,
                "{},{},{:04X},{:04X},{:02X},{:02X},{:04X},{:04X},{},{},{:04X},{:02X},{:04X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X}\n",
                i,
                e.advance,
                e.state,
                e.div,
                e.asub,
                e.ssub,
                m14((e.div >> 8) as u8, e.asub),
                m14(e.div as u8, e.ssub),
                e.atick,
                e.call_count,
                e.pc,
                e.hram.rom_bank,
                e.keys,
                e.hram.rtc_day_hi,
                e.hram.rtc_day_lo,
                e.hram.rtc_hours,
                e.hram.rtc_minutes,
                e.hram.rtc_seconds,
                e.hram.hours,
                e.hram.minutes,
                e.hram.seconds,
                e.hram.vblank_counter,
                e.hram.vblank,
                e.hram.map_entry,
                e.hram.menu_return,
                e.hram.joypad_released,
                e.hram.joypad_pressed,
                e.hram.joypad_down,
                e.hram.joypad_sum,
                e.hram.joy_released,
                e.hram.joy_pressed,
                e.hram.joy_down,
                e.hram.joy_last,
                e.hram.in_menu,
                e.hram.random_add,
                e.hram.random_sub
            );
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _ = write!(
            line,
            "\ncall_index,epoch,kind,pc,advance,add,sub,div,mcycle,m14,host_tick,rel_tick\n"
        );
        pnp::trace_file_write(line.as_bytes());

        let mut epoch = 0u32;
        let mut prev = 0u32;
        let mut prev_valid = false;
        for i in 0..shown {
            let e = call_log_entry(i);
            if prev_valid && e.advance < prev {
                epoch = epoch.wrapping_add(1);
            }
            prev = e.advance;
            prev_valid = true;

            line.clear();
            let _ = write!(
                line,
                "{},{},{},{:04X},{},{:02X},{:02X},{:02X},{:02X},{:04X},{},{}\n",
                total - shown + i,
                epoch,
                call_kind(e.pc),
                e.pc,
                e.advance,
                e.add,
                e.sub,
                e.div as u8,
                e.mcycle,
                m14(e.div as u8, e.mcycle),
                e.host_tick,
                e.host_tick.wrapping_sub(first_tick)
            );
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _ = write!(
            line,
            "\nevent_index,frame_index,reasons,reason_text,advance,state,pc,div,asub,ssub,m14_a,m14_s,physical_keys,call_count,host_tick,snapshot_tick_before,snapshot_tick_after,snapshot_tick_cost,hram_valid,cpu_valid,wram_valid\n"
        );
        pnp::trace_file_write(line.as_bytes());

        for i in 0..self.event_len {
            let e = unsafe { EVENTS[i] };
            line.clear();
            let _ = write!(
                line,
                "{},{},{:08X},{},{},{:04X},{:04X},{:04X},{:02X},{:02X},{:04X},{:04X},{:04X},{},{},{},{},{},{},{},{}\n",
                i,
                e.frame_index,
                e.reasons,
                reason_text(e.reasons),
                e.advance,
                e.state,
                e.pc,
                e.div,
                e.asub,
                e.ssub,
                m14((e.div >> 8) as u8, e.asub),
                m14(e.div as u8, e.ssub),
                e.keys,
                e.call_count,
                e.host_tick,
                e.snapshot_tick_before,
                e.snapshot_tick_after,
                e.snapshot_tick_after.wrapping_sub(e.snapshot_tick_before),
                e.hram_valid,
                e.cpu_valid,
                e.wram_valid
            );
            pnp::trace_file_write(line.as_bytes());

            line.clear();
            let _ = write!(line, "event_hram,{},", i);
            write_hex(&mut line, &e.hram);
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());

            line.clear();
            let _ = write!(line, "event_cpu,{},", i);
            write_hex(&mut line, &e.cpu_ctx);
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());

            line.clear();
            let _ = write!(line, "event_wram_d200,{},", i);
            write_hex(&mut line, &e.wram_d200);
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());
        }

        pnp::trace_file_close();
        self.save_index = self.save_index.wrapping_add(1);
        self.save_result = Some(true);
    }

    pub fn draw(&mut self, reader: &Gen2Reader, _is_locked: bool) {
        if pnp::is_just_pressed(pnp::Button::Select) && !self.frozen {
            self.save();
        }

        let total = call_log_count() as usize;
        let shown = total.min(CALL_LOG_LEN);
        let dropped = total.saturating_sub(shown);
        let div = measured_div();

        pnp::println!("BOOT ONESHOT V3");
        pnp::println!(
            "{} f{}/{} ev{}/{}",
            if self.frozen { "STOP" } else { "REC" },
            self.len,
            MAX_BOOT_FRAMES,
            self.event_len,
            MAX_EVENTS
        );
        pnp::println!("calls {} keep {} drop {}", total, shown, dropped);
        pnp::println!("evdrop {}", self.event_dropped);
        pnp::println!(
            "adv {} st {:04X} pc {:04X}",
            rng_advance(),
            reader.rng_state(),
            reader.pc_reg()
        );
        pnp::println!("div {:04X}", div);
        pnp::println!(
            "M {:04X}/{:04X}",
            m14((div >> 8) as u8, adiv_subtick()),
            m14(div as u8, sdiv_subtick())
        );

        if self.len > 0 {
            let last = unsafe { BOOT_FRAMES[self.len - 1] };
            pnp::println!(
                "JP {:02X} JD {:02X} M{:02X} V{:02X}",
                last.hram.joy_pressed,
                last.hram.joy_down,
                last.hram.in_menu,
                last.hram.vblank
            );
        }

        match self.save_result {
            Some(true) => pnp::println!("saved #{}", pnp::trace_written_slot()),
            Some(false) => pnp::println!("FAIL {:08X}", pnp::trace_last_error()),
            None if self.frozen => pnp::println!("stopped"),
            None => pnp::println!("SEL saves one-shot csv"),
        }

        pnp::println!("");
        pnp::println!("cold boot > Continue");
        pnp::println!("map > Boot > SELECT");
    }
}
