use core::fmt::Write;

use super::game_lib::gb_mem;
use super::hook::{add_div_tracker, measured_div, rng_advance, sub_div_tracker};
use super::reader::Gen2Reader;
use crate::pnp;

/// Frames kept in RAM. At 28 bytes an entry this is about 57 KB.
const MAX_FRAMES: usize = 2048;

/// First byte of the window copied every frame. The Japanese enemy Pokémon
/// struct starts at D237 (species), so this also captures the two bytes in
/// front of it that hold the species copy.
const WINDOW_START: u32 = 0xd235;
const WINDOW_LEN: usize = 10;

/// Default watch pair: the enemy DVs on the Japanese release, D237 + 6.
const DEFAULT_WATCH: u32 = 0xd23d;

/// Celebi's species number, so the frames where the struct is populated can be
/// picked out of the CSV afterwards.
const CELEBI_SPECIES: u8 = 0xfb;

#[derive(Clone, Copy, Default)]
pub struct TraceEntry {
    pub advance: u32,
    pub state: u16,
    pub div: u16,
    pub adiv: u16,
    pub sdiv: u16,
    pub keys: u16,
    pub flags: u8,
    pub window: [u8; WINDOW_LEN],
}

pub const FLAG_A_PRESSED: u8 = 1;
pub const FLAG_WATCH_CHANGED: u8 = 2;
pub const FLAG_CELEBI_SPECIES: u8 = 4;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TraceState {
    Off,
    /// Armed from the pause loop. Recording begins on the first frame that
    /// actually runs, which is the first frame after the target.
    Armed,
    Recording,
    Done,
}

pub fn status_text(state: TraceState) -> &'static str {
    match state {
        TraceState::Off => "OFF",
        TraceState::Armed => "ARMED",
        TraceState::Recording => "REC",
        TraceState::Done => "DONE",
    }
}

/// Small stack formatter so a CSV row can be built without allocating.
struct LineBuf {
    buf: [u8; 192],
    len: usize,
}

impl LineBuf {
    fn new() -> Self {
        Self {
            buf: [0; 192],
            len: 0,
        }
    }

    fn as_bytes(&self) -> &[u8] {
        &self.buf[..self.len]
    }

    fn clear(&mut self) {
        self.len = 0;
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

pub struct Trace {
    entries: [TraceEntry; MAX_FRAMES],
    len: usize,
    state: TraceState,
    watch_addr: u32,
    watch_last: u16,
    watch_changes: u32,
    first_change: Option<usize>,
    start_advance: u32,
    start_state: u16,
    last_run_id: u32,
    last_arm_id: u32,
    last_stop_req: u32,
    last_save_req: u32,
    save_index: u32,
    save_result: Option<bool>,
    /// Row shown first in the on screen table.
    pub cursor: usize,
}

impl Default for Trace {
    fn default() -> Self {
        Self {
            entries: [TraceEntry::default(); MAX_FRAMES],
            len: 0,
            state: TraceState::Off,
            watch_addr: DEFAULT_WATCH,
            watch_last: 0,
            watch_changes: 0,
            first_change: None,
            start_advance: 0,
            start_state: 0,
            last_run_id: 0,
            last_arm_id: 0,
            last_stop_req: 0,
            last_save_req: 0,
            save_index: 1,
            save_result: None,
            cursor: 0,
        }
    }
}

impl Trace {
    pub fn status_line(&self) -> (&'static str, u32, usize) {
        (status_text(self.state), self.start_advance, self.len)
    }

    /// Short save indicator for the rng page: "-", "OK" or the error code.
    pub fn save_status(&self) -> (&'static str, u32) {
        match self.save_result {
            Some(true) => ("OK", pnp::trace_written_slot()),
            Some(false) => ("ERR", pnp::trace_last_error()),
            None => ("-", 0),
        }
    }

    pub fn set_watch_addr(&mut self, addr: u32) {
        self.watch_addr = addr;
    }

    fn entry(&self, index: usize) -> Option<&TraceEntry> {
        if index < self.len {
            self.entries.get(index)
        } else {
            None
        }
    }

    /// Queue a recording. Values are latched on the first frame that runs,
    /// because nothing moves while the game is paused.
    pub fn arm(&mut self) {
        self.reset();
        self.state = TraceState::Armed;
    }

    fn reset(&mut self) {
        self.len = 0;
        self.cursor = 0;
        self.watch_changes = 0;
        self.first_change = None;
        self.save_result = None;
    }

    pub fn start(&mut self, reader: &Gen2Reader) {
        self.reset();
        self.start_advance = rng_advance();
        self.start_state = reader.rng_state();
        self.watch_last = gb_mem::read_u16(self.watch_addr);
        self.state = TraceState::Recording;
    }

    pub fn stop(&mut self) {
        if self.state == TraceState::Recording || self.state == TraceState::Armed {
            self.state = TraceState::Done;
        }
    }

    /// Called once per frame. Copies numbers only, no allocation or IO.
    pub fn record(&mut self, reader: &Gen2Reader) {
        // Y + START in the pause loop arms or clears the trace.
        let (arm_id, armed) = pnp::trace_request();
        if arm_id != self.last_arm_id {
            self.last_arm_id = arm_id;
            if armed {
                self.arm();
            } else {
                self.stop();
            }
        }

        // Y + SELECT stops, Y + A saves. Both are queued from the pause loop.
        let (stop_req, save_req) = pnp::trace_cmds();
        if stop_req != self.last_stop_req {
            self.last_stop_req = stop_req;
            self.stop();
        }
        if save_req != self.last_save_req {
            self.last_save_req = save_req;
            if self.state != TraceState::Recording {
                self.save();
            }
        }

        // A Fixed A Frame run starts the trace too, unless one is already set
        // up, so arming first and running second keeps the armed start point.
        let run_id = pnp::fixed_run_id();
        if run_id != self.last_run_id {
            self.last_run_id = run_id;
            if self.state == TraceState::Off || self.state == TraceState::Done {
                self.start(reader);
            }
        }

        if self.state == TraceState::Armed {
            self.start(reader);
        }

        if self.state != TraceState::Recording {
            return;
        }

        if self.len >= MAX_FRAMES {
            self.state = TraceState::Done;
            return;
        }

        let mut window = [0u8; WINDOW_LEN];
        for (offset, slot) in window.iter_mut().enumerate() {
            *slot = gb_mem::read_u8(WINDOW_START + offset as u32);
        }

        let watch = gb_mem::read_u16(self.watch_addr);
        let changed = watch != self.watch_last;
        if changed {
            self.watch_last = watch;
            self.watch_changes += 1;
            if self.first_change.is_none() {
                self.first_change = Some(self.len);
            }
        }

        let mut flags = 0u8;
        if pnp::is_pressing(pnp::Button::A) {
            flags |= FLAG_A_PRESSED;
        }
        if changed {
            flags |= FLAG_WATCH_CHANGED;
        }
        // D237 holds the enemy species once the struct is populated.
        if window[2] == CELEBI_SPECIES {
            flags |= FLAG_CELEBI_SPECIES;
        }

        self.entries[self.len] = TraceEntry {
            advance: rng_advance(),
            state: reader.rng_state(),
            div: measured_div(),
            adiv: add_div_tracker().index().unwrap_or(0) as u16,
            sdiv: sub_div_tracker().index().unwrap_or(0) as u16,
            keys: pnp::current_keys() as u16,
            flags,
            window,
        };

        self.len += 1;
    }

    /// Streams the buffer out as CSV. Only ever called after recording stops.
    fn save(&mut self) {
        if self.len == 0 {
            self.save_result = Some(false);
            return;
        }

        if !pnp::trace_file_open(self.save_index) {
            self.save_result = Some(false);
            return;
        }

        let mut line = LineBuf::new();
        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\n"
        );
        pnp::trace_file_write(line.as_bytes());

        for index in 0..self.len {
            let entry = self.entries[index];
            line.clear();
            let _ = write!(
                line,
                "{},{},{},{:04X},{:04X},{},{},{:04X},{},",
                index,
                entry.advance.wrapping_sub(self.start_advance),
                entry.advance,
                entry.state,
                entry.div,
                entry.adiv,
                entry.sdiv,
                entry.keys,
                (entry.flags & FLAG_A_PRESSED != 0) as u8
            );
            for byte in entry.window.iter() {
                let _ = write!(line, "{:02X},", byte);
            }
            let _ = write!(
                line,
                "{},{}\n",
                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,
                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8
            );
            pnp::trace_file_write(line.as_bytes());
        }

        pnp::trace_file_close();
        self.save_index += 1;
        self.save_result = Some(true);
    }

    pub fn draw(&mut self, reader: &Gen2Reader, is_locked: bool) {
        if is_locked {
            if pnp::is_just_pressed(pnp::Button::Ddown) {
                self.cursor = self
                    .cursor
                    .saturating_add(4)
                    .min(self.len.saturating_sub(1));
            } else if pnp::is_just_pressed(pnp::Button::Dup) {
                self.cursor = self.cursor.saturating_sub(4);
            } else if pnp::is_just_pressed(pnp::Button::A) {
                match self.state {
                    TraceState::Recording | TraceState::Armed => self.stop(),
                    _ => self.start(reader),
                }
            } else if pnp::is_just_pressed(pnp::Button::B) {
                if let Some(frame) = self.first_change {
                    self.cursor = frame.saturating_sub(2);
                }
            } else if pnp::is_just_pressed(pnp::Button::Select)
                && self.state != TraceState::Recording
            {
                self.save();
            }
        }

        pnp::println!(
            "Trace {} {}/{}",
            status_text(self.state),
            self.len,
            MAX_FRAMES
        );
        pnp::println!("from adv {}", self.start_advance);
        pnp::println!("from st  {:04X}", self.start_state);
        pnp::println!("watch {:04X}", self.watch_addr);
        pnp::println!("changes {}", self.watch_changes);
        match self.save_result {
            Some(true) => pnp::println!("saved #{}", pnp::trace_written_slot()),
            Some(false) => pnp::println!("FAIL {:08X}", pnp::trace_last_error()),
            None => pnp::println!("SEL saves csv"),
        }

        pnp::println!("");
        pnp::println!("f   adv sp  dv   chg");
        for row in 0..6usize {
            let index = self.cursor + row;
            match self.entry(index) {
                Some(entry) => pnp::println!(
                    "{:<3} {:<3} {:02X}  {:02X}{:02X} {}",
                    index,
                    entry.advance.wrapping_sub(self.start_advance),
                    entry.window[2],
                    entry.window[8],
                    entry.window[9],
                    (entry.flags & FLAG_WATCH_CHANGED != 0) as u8
                ),
                None => break,
            }
        }

        pnp::println!("");
        pnp::println!("A rec B chg ^v SEL");
    }
}
