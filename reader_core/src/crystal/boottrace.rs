use core::fmt::Write;

use super::{
    hook::{
        adiv_subtick, adiv_tick, call_log_count, call_log_entry, call_log_stop, measured_div,
        rng_advance, sdiv_subtick, CALL_LOG_LEN,
    },
    reader::Gen2Reader,
};
use crate::pnp;

/// Keep the earliest presented frames from process start. 4096 frames is about
/// 68 seconds at GB/CGB speed, enough for a controlled cold-boot -> Continue
/// experiment while keeping the diagnostic branch reasonably small.
const MAX_BOOT_FRAMES: usize = 4096;

/// JP VC host pointer to the emulated FF80-FFFF HRAM block. This is the same
/// pointer already used by the existing Crystal deep probe. Boot v2 samples a
/// few bytes after each presented frame so we can distinguish physical 3DS
/// input from the key edge that Crystal actually consumed.
const CRYSTAL_HRAM_PTR: u32 = 0x0022f6d8;
const H_VBLANK: u32 = 0x13;          // FF93
const H_MAP_ENTRY_METHOD: u32 = 0x14; // FF94
const H_JOYPAD_PRESSED: u32 = 0x18;  // FF98
const H_JOYPAD_DOWN: u32 = 0x19;     // FF99
const H_JOY_PRESSED: u32 = 0x1c;     // FF9C
const H_JOY_DOWN: u32 = 0x1d;        // FF9D
const H_JOY_LAST: u32 = 0x1e;        // FF9E
const H_IN_MENU: u32 = 0x1f;         // FF9F

#[derive(Clone, Copy)]
struct BootHram {
    valid: u8,
    vblank: u8,
    map_entry: u8,
    joypad_pressed: u8,
    joypad_down: u8,
    joy_pressed: u8,
    joy_down: u8,
    joy_last: u8,
    in_menu: u8,
}

impl BootHram {
    const EMPTY: Self = Self {
        valid: 0,
        vblank: 0,
        map_entry: 0,
        joypad_pressed: 0,
        joypad_down: 0,
        joy_pressed: 0,
        joy_down: 0,
        joy_last: 0,
        in_menu: 0,
    };
}

fn read_boot_hram() -> BootHram {
    let base = pnp::read::<u32>(CRYSTAL_HRAM_PTR);
    if !pnp::is_memory_mapped(base) || !pnp::is_memory_mapped(base.wrapping_add(H_IN_MENU)) {
        return BootHram::EMPTY;
    }

    BootHram {
        valid: 1,
        vblank: pnp::read::<u8>(base.wrapping_add(H_VBLANK)),
        map_entry: pnp::read::<u8>(base.wrapping_add(H_MAP_ENTRY_METHOD)),
        joypad_pressed: pnp::read::<u8>(base.wrapping_add(H_JOYPAD_PRESSED)),
        joypad_down: pnp::read::<u8>(base.wrapping_add(H_JOYPAD_DOWN)),
        joy_pressed: pnp::read::<u8>(base.wrapping_add(H_JOY_PRESSED)),
        joy_down: pnp::read::<u8>(base.wrapping_add(H_JOY_DOWN)),
        joy_last: pnp::read::<u8>(base.wrapping_add(H_JOY_LAST)),
        in_menu: pnp::read::<u8>(base.wrapping_add(H_IN_MENU)),
    }
}

#[derive(Clone, Copy)]
struct BootFrame {
    advance: u32,
    state: u16,
    div: u16,
    keys: u16,
    asub: u8,
    ssub: u8,
    atick: u64,
    hram: BootHram,
}

impl BootFrame {
    const EMPTY: Self = Self {
        advance: 0,
        state: 0,
        div: 0,
        keys: 0,
        asub: 0,
        ssub: 0,
        atick: 0,
        hram: BootHram::EMPTY,
    };
}

static mut BOOT_FRAMES: [BootFrame; MAX_BOOT_FRAMES] = [BootFrame::EMPTY; MAX_BOOT_FRAMES];

struct LineBuf {
    buf: [u8; 512],
    len: usize,
}

impl LineBuf {
    fn new() -> Self {
        Self {
            buf: [0; 512],
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

fn call_kind(pc: u16) -> &'static str {
    match pc {
        0x02b5 | 0x02b6 => "VB_A",
        0x02bd | 0x02be => "VB_S",
        0x2f60 => "RND_A",
        0x2f68 => "RND_S",
        _ => "DIV",
    }
}

pub struct BootTrace {
    len: usize,
    frozen: bool,
    save_index: u32,
    save_result: Option<bool>,
}

impl Default for BootTrace {
    fn default() -> Self {
        Self {
            len: 0,
            frozen: false,
            save_index: 1,
            save_result: None,
        }
    }
}

impl BootTrace {
    /// Called before the legacy 01FF/0101 RNG_ADVANCE reset in frame.rs. That
    /// ordering is intentional: the CSV then contains both the real state seen
    /// on the presented frame and the subsequent logical-advance epoch change.
    pub fn record_frame(&mut self, reader: &Gen2Reader) {
        if self.frozen || self.len >= MAX_BOOT_FRAMES {
            return;
        }

        let hram = read_boot_hram();
        unsafe {
            BOOT_FRAMES[self.len] = BootFrame {
                advance: rng_advance(),
                state: reader.rng_state(),
                div: measured_div(),
                keys: pnp::current_keys() as u16,
                asub: adiv_subtick(),
                ssub: sdiv_subtick(),
                atick: adiv_tick(),
                hram,
            };
        }
        self.len += 1;
    }

    fn save(&mut self) {
        // Freeze both streams before filesystem IO. The diagnostic data is
        // already collected; any timing perturbation from saving is irrelevant.
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

        // Find the strongest boot markers directly in the rDIV-call stream.
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
            if have_prev && !reset_found && e.advance < prev_advance {
                reset_found = true;
                reset_index = total - shown + i;
            }
            prev_advance = e.advance;
            have_prev = true;
        }

        let _ = write!(line, "mode,BOOT_CALL_TRACE_V2\n");
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(
            line,
            "summary,frames_kept,{},frame_capacity,{},calls_total,{},calls_kept,{},calls_dropped,{}\n",
            self.len,
            MAX_BOOT_FRAMES,
            total,
            shown,
            dropped
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

        // Presented-frame stream. physical_keys is the 3DS HID state; the h*
        // fields are Crystal's own HRAM input/VBlank context sampled afterwards.
        line.clear();
        let _ = write!(
            line,
            "frame_index,advance,state,div,asub,ssub,m14_a,m14_s,host_tick,physical_keys,hram_valid,h_vblank,h_map_entry,h_joypad_pressed,h_joypad_down,h_joy_pressed,h_joy_down,h_joy_last,h_in_menu\n"
        );
        pnp::trace_file_write(line.as_bytes());
        for i in 0..self.len {
            let e = unsafe { BOOT_FRAMES[i] };
            line.clear();
            let _ = write!(
                line,
                "{},{},{:04X},{:04X},{:02X},{:02X},{:04X},{:04X},{},{:04X},{},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X}\n",
                i,
                e.advance,
                e.state,
                e.div,
                e.asub,
                e.ssub,
                m14((e.div >> 8) as u8, e.asub),
                m14(e.div as u8, e.ssub),
                e.atick,
                e.keys,
                e.hram.valid,
                e.hram.vblank,
                e.hram.map_entry,
                e.hram.joypad_pressed,
                e.hram.joypad_down,
                e.hram.joy_pressed,
                e.hram.joy_down,
                e.hram.joy_last,
                e.hram.in_menu
            );
            pnp::trace_file_write(line.as_bytes());
        }

        // Raw rDIV-call stream. epoch increments whenever frame.rs resets the
        // logical advance. rel_tick is relative to the oldest retained call.
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
        let last_hram = if self.len > 0 {
            unsafe { BOOT_FRAMES[self.len - 1].hram }
        } else {
            BootHram::EMPTY
        };

        pnp::println!("BOOT TRACE V2");
        pnp::println!(
            "{} f{}/{}",
            if self.frozen { "STOP" } else { "REC" },
            self.len,
            MAX_BOOT_FRAMES
        );
        pnp::println!("calls {} keep {}", total, shown);
        pnp::println!("drop {}", dropped);
        pnp::println!("adv {} st {:04X}", rng_advance(), reader.rng_state());
        pnp::println!("div {:04X}", div);
        pnp::println!(
            "M {:04X}/{:04X}",
            m14((div >> 8) as u8, adiv_subtick()),
            m14(div as u8, sdiv_subtick())
        );
        pnp::println!(
            "J {:02X}/{:02X} V{:02X}",
            last_hram.joy_pressed,
            last_hram.joy_down,
            last_hram.vblank
        );

        match self.save_result {
            Some(true) => pnp::println!("saved #{}", pnp::trace_written_slot()),
            Some(false) => pnp::println!("FAIL {:08X}", pnp::trace_last_error()),
            None if self.frozen => pnp::println!("stopped"),
            None => pnp::println!("SEL saves boot csv"),
        }

        pnp::println!("");
        pnp::println!("Input acceptance probe");
        pnp::println!("launch > Continue");
        pnp::println!("map then SEL save");
    }
}
