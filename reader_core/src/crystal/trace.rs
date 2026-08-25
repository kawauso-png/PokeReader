use super::game_lib::gb_mem;
use super::hook::{measured_div, rng_advance};
use super::reader::Gen2Reader;
use crate::pnp;

/// Frames kept in RAM. The plugin has no file IO, so the trace lives here and
/// is read back on screen.
const MAX_FRAMES: usize = 2048;

/// Keep recording for a while after the watched bytes change, so the frames
/// around DV generation are captured too.
const FRAMES_AFTER_WRITE: u32 = 30;

/// Default watch target: the enemy Pokémon's DVs on the international release.
/// The Japanese address is not confirmed yet, so it can be repointed at
/// runtime from the memory view.
const DEFAULT_WATCH: u32 = 0xd20c;

#[derive(Clone, Copy, Default)]
pub struct TraceEntry {
    pub advance: u32,
    pub state: u16,
    pub div: u16,
    pub watch: u16,
    pub flags: u8,
}

pub const FLAG_A_PRESSED: u8 = 1;
pub const FLAG_WATCH_CHANGED: u8 = 2;

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TraceState {
    Off,
    Recording,
    Done,
}

pub struct Trace {
    entries: [TraceEntry; MAX_FRAMES],
    len: usize,
    state: TraceState,
    watch_addr: u32,
    watch_start: u16,
    start_advance: u32,
    start_state: u16,
    write_frame: Option<usize>,
    frames_since_write: u32,
    last_run_id: u32,
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
            watch_start: 0,
            start_advance: 0,
            start_state: 0,
            write_frame: None,
            frames_since_write: 0,
            last_run_id: 0,
            cursor: 0,
        }
    }
}

impl Trace {
    pub fn state(&self) -> TraceState {
        self.state
    }

    pub fn len(&self) -> usize {
        self.len
    }

    pub fn watch_addr(&self) -> u32 {
        self.watch_addr
    }

    pub fn set_watch_addr(&mut self, addr: u32) {
        self.watch_addr = addr;
    }

    pub fn entry(&self, index: usize) -> Option<&TraceEntry> {
        self.entries.get(index).filter(|_| index < self.len)
    }

    pub fn write_frame(&self) -> Option<usize> {
        self.write_frame
    }

    pub fn start(&mut self, reader: &Gen2Reader) {
        self.len = 0;
        self.cursor = 0;
        self.write_frame = None;
        self.frames_since_write = 0;
        self.start_advance = rng_advance();
        self.start_state = reader.rng_state();
        self.watch_start = gb_mem::read_u16(self.watch_addr);
        self.state = TraceState::Recording;
    }

    pub fn stop(&mut self) {
        if self.state == TraceState::Recording {
            self.state = TraceState::Done;
        }
    }

    pub fn clear(&mut self) {
        self.len = 0;
        self.cursor = 0;
        self.write_frame = None;
        self.state = TraceState::Off;
    }

    pub fn start_advance(&self) -> u32 {
        self.start_advance
    }

    pub fn start_state(&self) -> u16 {
        self.start_state
    }

    /// Advances consumed between the trace start and the watched write.
    pub fn advances_to_write(&self) -> Option<u32> {
        let frame = self.write_frame?;
        let entry = self.entries.get(frame)?;
        Some(entry.advance.wrapping_sub(self.start_advance))
    }

    /// Called once per frame. Copies numbers only, no allocation or IO.
    pub fn record(&mut self, reader: &Gen2Reader) {
        // Arm off a Fixed A Frame run so the trace needs no hotkey of its own.
        let run_id = pnp::fixed_run_id();
        if run_id != self.last_run_id {
            self.last_run_id = run_id;
            self.start(reader);
        }

        if self.state != TraceState::Recording {
            return;
        }

        if self.len >= MAX_FRAMES {
            self.state = TraceState::Done;
            return;
        }

        let watch = gb_mem::read_u16(self.watch_addr);
        let changed = self.write_frame.is_none() && watch != self.watch_start;

        let mut flags = 0u8;
        if pnp::is_pressing(pnp::Button::A) {
            flags |= FLAG_A_PRESSED;
        }
        if changed {
            flags |= FLAG_WATCH_CHANGED;
        }

        self.entries[self.len] = TraceEntry {
            advance: rng_advance(),
            state: reader.rng_state(),
            div: measured_div(),
            watch,
            flags,
        };

        if changed {
            self.write_frame = Some(self.len);
        }

        self.len += 1;

        if self.write_frame.is_some() {
            self.frames_since_write += 1;
            if self.frames_since_write >= FRAMES_AFTER_WRITE {
                self.state = TraceState::Done;
            }
        }
    }

    pub fn draw(&mut self, reader: &Gen2Reader, is_locked: bool) {
        if is_locked {
            if pnp::is_just_pressed(pnp::Button::Ddown) {
                self.cursor = self.cursor.saturating_add(4).min(self.len.saturating_sub(1));
            } else if pnp::is_just_pressed(pnp::Button::Dup) {
                self.cursor = self.cursor.saturating_sub(4);
            } else if pnp::is_just_pressed(pnp::Button::A) {
                match self.state {
                    TraceState::Recording => self.stop(),
                    _ => self.start(reader),
                }
            } else if pnp::is_just_pressed(pnp::Button::B) {
                if let Some(frame) = self.write_frame {
                    self.cursor = frame.saturating_sub(2);
                }
            }
        }

        let status = match self.state {
            TraceState::Off => "OFF",
            TraceState::Recording => "REC",
            TraceState::Done => "DONE",
        };
        pnp::println!("Trace {} {}/{}", status, self.len, MAX_FRAMES);
        pnp::println!("watch {:04X}", self.watch_addr);
        pnp::println!("from adv {}", self.start_advance);
        pnp::println!("from st  {:04X}", self.start_state);

        match (self.write_frame, self.advances_to_write()) {
            (Some(frame), Some(delta)) => {
                pnp::println!("WRITE f{} +{}", frame, delta);
                if let Some(entry) = self.entries.get(frame) {
                    pnp::println!("st {:04X} dv {:04X}", entry.state, entry.watch);
                }
            }
            _ => pnp::println!("no write yet"),
        }

        pnp::println!("");
        pnp::println!("f    adv   st   dv");
        for row in 0..6usize {
            let index = self.cursor + row;
            match self.entry(index) {
                Some(entry) => pnp::println!(
                    "{:<4} {:<5} {:04X} {:04X}",
                    index,
                    entry.advance.wrapping_sub(self.start_advance),
                    entry.state,
                    entry.watch
                ),
                None => break,
            }
        }

        pnp::println!("");
        pnp::println!("A rec  B jump  ^v scr");
    }
}
