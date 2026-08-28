use core::fmt::Write;

use super::game_lib::gb_mem;
use super::hook::{
    add_div_tracker, adiv_cycles, call_log_count, call_log_entry, call_log_start, call_log_stop,
    cycle_counter, deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, measured_div,
    rng_advance, sdiv_cycles, sub_div_tracker,
};
use super::reader::Gen2Reader;
use crate::pnp;

/// Frames kept in RAM. At 36 bytes an entry this is about 288 KB. The buffer
/// lives in .bss (see TRACE_ENTRIES) rather than inside the Trace struct, so
/// growing it does not put a quarter of a megabyte on the stack when the
/// persisted state is first built.
const MAX_FRAMES: usize = 8192;

/// First byte of the window copied every frame. The Japanese enemy Pokémon
/// struct starts at D237 (species), so this also captures the two bytes in
/// front of it that hold the species copy.
const WINDOW_START: u32 = 0xd235;
const WINDOW_LEN: usize = 10;

/// Default watch pair: the enemy DVs on the Japanese release, D237 + 6.
const DEFAULT_WATCH: u32 = 0xd23d;

/// Species numbers that mark the frames where the enemy struct is populated,
/// so they can be picked out of the CSV afterwards. Celebi is FB, Suicune F5.
const CELEBI_SPECIES: u8 = 0xfb;
const SUICUNE_SPECIES: u8 = 0xf5;

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
    /// Cycle counter at the two VBlank rDIV reads of this frame. The DIV byte
    /// only resolves 256 cycles; these resolve the position inside that step,
    /// which is what the +/-1 phase slips turn on.
    pub acyc: u32,
    pub scyc: u32,
}

impl TraceEntry {
    const EMPTY: Self = Self {
        advance: 0,
        state: 0,
        div: 0,
        adiv: 0,
        sdiv: 0,
        keys: 0,
        flags: 0,
        window: [0; WINDOW_LEN],
        acyc: 0,
        scyc: 0,
    };
}

/// The frame buffer itself. Kept as a static so it is zero initialised in .bss
/// and never copied through the stack.
static mut TRACE_ENTRIES: [TraceEntry; MAX_FRAMES] = [TraceEntry::EMPTY; MAX_FRAMES];

pub const FLAG_A_PRESSED: u8 = 1;
pub const FLAG_WATCH_CHANGED: u8 = 2;
pub const FLAG_CELEBI_SPECIES: u8 = 4;

#[derive(Clone, Copy, Default)]
pub struct ProbeTarget {
    pub advance: u32,
    pub state: u16,
    pub div: u16,
    pub adiv: u16,
    pub sdiv: u16,
    pub acyc: u32,
    pub scyc: u32,
    pub keys: u16,
}

#[derive(Clone, Copy, Default)]
pub struct ProbeResult {
    pub dv_advance: u32,
    pub offset: u32,
    pub route: u8,
    pub raw_dv: u16,
    pub first_call_index: u32,
    pub final_call_index: u32,
    pub clean_tail: bool,
}

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
    // Deep-probe rows contain register snapshots plus three raw memory blobs.
    // Saving only happens after the result is locked, so a 1 KiB stack buffer
    // is preferable to allocations in the timing-sensitive hook.
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
    entries: &'static mut [TraceEntry],
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
    probe_active: bool,
    probe_target: ProbeTarget,
    probe_result: Option<ProbeResult>,
    /// Row shown first in the on screen table.
    pub cursor: usize,
}

impl Default for Trace {
    fn default() -> Self {
        Self {
            // Safe for the same reason the persisted state is: the reader runs
            // single threaded, and only one Trace is ever built.
            entries: unsafe { &mut *core::ptr::addr_of_mut!(TRACE_ENTRIES) },
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
            probe_active: false,
            probe_target: ProbeTarget::default(),
            probe_result: None,
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

    /// Called directly from the C pause loop by Y+X.  Because this runs while
    /// the game is frozen, it captures the exact Target state instead of
    /// reconstructing it from trace frame 0 (= Target+1).
    pub fn arm_suicune_probe(&mut self, reader: &Gen2Reader) {
        self.stop();
        self.reset();
        self.probe_target = ProbeTarget {
            advance: rng_advance(),
            state: reader.rng_state(),
            div: measured_div(),
            adiv: add_div_tracker().index().unwrap_or(0) as u16,
            sdiv: sub_div_tracker().index().unwrap_or(0) as u16,
            acyc: adiv_cycles(),
            scyc: sdiv_cycles(),
            keys: pnp::current_keys() as u16,
        };
        self.probe_result = None;
        self.probe_active = true;
        self.state = TraceState::Armed;
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
        self.probe_active = false;
        deep_log_stop();
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
        call_log_start();
        if self.probe_active {
            deep_log_start();
        } else {
            deep_log_stop();
        }
        self.state = TraceState::Recording;
    }

    pub fn stop(&mut self) {
        if self.state == TraceState::Recording || self.state == TraceState::Armed {
            call_log_stop();
            deep_log_stop();
            self.probe_active = false;
            self.state = TraceState::Done;
        }
    }

    fn detect_suicune_result(&self, advance: u32, dv1: u8, dv2: u8) -> Option<ProbeResult> {
        // The current Japanese-VC observations all lock the Suicune DV about
        // 730 frames after Target.  The wider guard prevents an unrelated F5
        // struct from accidentally terminating a probe while keeping the
        // detector future-proof for small timing slips.
        let offset = advance.wrapping_sub(self.probe_target.advance);
        if !(680..=780).contains(&offset) {
            return None;
        }

        let total = call_log_count() as usize;
        let shown = total.min(super::hook::CALL_LOG_LEN);
        if shown < 4 {
            return None;
        }

        let is_vblank_a = |pc: u16| pc == 0x02b5 || pc == 0x02b6;
        let is_random_a = |pc: u16| pc == 0x2f60;

        // Find the VBlank-A read on this advance whose resulting Sub byte is
        // the DV2 byte now visible in wEnemyMon.
        let mut end = None;
        for i in (0..shown).rev() {
            let e = call_log_entry(i);
            if e.advance < advance {
                break;
            }
            if e.advance == advance && is_vblank_a(e.pc) && e.sub == dv2 {
                end = Some(i);
                break;
            }
        }
        let end = end?;

        // The immediately preceding VBlank-A delimits the stationary encounter
        // generation burst.  Count first-rDIV Random reads between the two.
        let mut start = 0usize;
        for i in (0..end).rev() {
            if is_vblank_a(call_log_entry(i).pc) {
                start = i + 1;
                break;
            }
        }

        let mut route = 0u8;
        let mut last_random = None;
        for i in start..end {
            let e = call_log_entry(i);
            if is_random_a(e.pc) {
                route = route.saturating_add(1);
                last_random = Some((i, e));
            }
        }
        if route != 3 && route != 4 {
            return None;
        }
        let (last_random_index, last_random_entry) = last_random?;
        if last_random_entry.sub != dv1 {
            return None;
        }

        // Startup control keys are normally released within the first ~20
        // frames.  Treat everything from rel 32 onward as the clean tail.
        let clean_tail = self
            .entries
            .iter()
            .take(self.len)
            .enumerate()
            .filter(|(i, _)| *i >= 32)
            .all(|(_, e)| e.keys == 0);

        Some(ProbeResult {
            dv_advance: advance,
            offset,
            route,
            raw_dv: ((dv1 as u16) << 8) | dv2 as u16,
            first_call_index: (total - shown + start) as u32,
            final_call_index: (total - shown + end.max(last_random_index)) as u32,
            clean_tail,
        })
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
            call_log_stop();
            deep_log_stop();
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
        if window[2] == CELEBI_SPECIES || window[2] == SUICUNE_SPECIES {
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
            acyc: adiv_cycles(),
            scyc: sdiv_cycles(),
        };

        self.len += 1;

        if self.probe_active && window[2] == SUICUNE_SPECIES {
            if let Some(result) = self.detect_suicune_result(
                self.entries[self.len - 1].advance,
                window[8],
                window[9],
            ) {
                self.probe_result = Some(result);
                self.probe_active = false;
                call_log_stop();
                deep_log_stop();
                self.state = TraceState::Done;

                // DV and route are already locked.  From this point filesystem
                // work cannot change the result, so save automatically and ask
                // the C host to pause before the user can inject another key.
                self.save();
                pnp::request_pause();
            }
        }
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

        // Probe summary comes first so a parser can classify a trial without
        // reading thousands of frame/call rows.
        if let Some(result) = self.probe_result {
            let phase_a = self.probe_target.adiv & 15;
            let phase_s = self.probe_target.sdiv & 15;
            let _ = write!(
                line,
                "probe,target,target_state,target_div,target_adiv,target_sdiv,target_acyc,target_scyc,target_keys,phase_a,phase_s,dv_advance,offset,route,raw_dv,clean_tail,call_first,call_final,deep_samples\n"
            );
            pnp::trace_file_write(line.as_bytes());
            line.clear();
            let _ = write!(
                line,
                "SUICUNE,{},{:04X},{:04X},{},{},{},{},{:04X},{},{},{},{},{},{:04X},{},{},{},{}\n\n",
                self.probe_target.advance,
                self.probe_target.state,
                self.probe_target.div,
                self.probe_target.adiv,
                self.probe_target.sdiv,
                self.probe_target.acyc,
                self.probe_target.scyc,
                self.probe_target.keys,
                phase_a,
                phase_s,
                result.dv_advance,
                result.offset,
                result.route,
                result.raw_dv,
                result.clean_tail as u8,
                result.first_call_index,
                result.final_call_index,
                deep_log_count()
            );
            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\n"
        );
        pnp::trace_file_write(line.as_bytes());

        for index in 0..self.len {
            let entry = self.entries[index];
            line.clear();
            let _ = write!(
                line,
                "{},{},{},{:04X},{:04X},{},{},{},{},{:04X},{},",
                index,
                entry.advance.wrapping_sub(self.start_advance),
                entry.advance,
                entry.state,
                entry.div,
                entry.adiv,
                entry.sdiv,
                entry.acyc,
                entry.scyc,
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

        // Second section: every Random call, which is what shows how the DVs
        // are actually produced inside a single frame.
        line.clear();
        let _ = write!(line, "\ncall_index,pc,advance,add,sub,div,cycles\n");
        pnp::trace_file_write(line.as_bytes());

        let total = call_log_count() as usize;
        let shown = total.min(super::hook::CALL_LOG_LEN);
        for i in 0..shown {
            let e = call_log_entry(i);
            line.clear();
            let _ = write!(
                line,
                "{},{:04X},{},{:02X},{:02X},{:04X},{}\n",
                total - shown + i,
                e.pc,
                e.advance,
                e.add,
                e.sub,
                e.div,
                e.cycles
            );
            pnp::trace_file_write(line.as_bytes());
        }

        // Third section: high-information samples from the first rDIV read
        // of each Random call.  Memory blobs are hex strings so they remain a
        // valid single CSV field without quoting.
        line.clear();
        let _ = write!(
            line,
            "\ndeep_index,pc,advance,add,sub,div,cycles,r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12,lr,host_pc,stk0,stk1,stk2,stk3,stk4,stk5,stk6,stk7,cpu_ctx_22f5e0_64,wram_d200_d27f,hram_ff80_ffff\n"
        );
        pnp::trace_file_write(line.as_bytes());

        let deep_total = deep_log_count() as usize;
        let deep_shown = deep_total.min(super::hook::DEEP_LOG_LEN);
        for i in 0..deep_shown {
            let e = deep_log_entry(i);
            line.clear();
            let _ = write!(
                line,
                "{},{:04X},{},{:02X},{:02X},{:04X},{}",
                deep_total - deep_shown + i,
                e.pc,
                e.advance,
                e.add,
                e.sub,
                e.div,
                e.cycles
            );
            for reg in e.regs.iter() {
                let _ = write!(line, ",{:08X}", reg);
            }
            for word in e.host_stack.iter() {
                let _ = write!(line, ",{:08X}", word);
            }
            let _ = write!(line, ",");
            for byte in e.cpu_ctx.iter() {
                let _ = write!(line, "{:02X}", byte);
            }
            let _ = write!(line, ",");
            for byte in e.wram_d200.iter() {
                let _ = write!(line, "{:02X}", byte);
            }
            let _ = write!(line, ",");
            for byte in e.hram.iter() {
                let _ = write!(line, "{:02X}", byte);
            }
            let _ = write!(line, "\n");
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
        pnp::println!("calls {} deep {}", call_log_count(), deep_log_count());
        if self.probe_active {
            pnp::println!("Probe ARMED T{}", self.probe_target.advance);
        } else if let Some(result) = self.probe_result {
            pnp::println!(
                "Probe +{} {}c {:04X}",
                result.offset,
                result.route,
                result.raw_dv
            );
        }
        // If this stays at 0 the cycle-counter hook address is wrong for this
        // release and the acyc/scyc columns will be useless.
        pnp::println!("cyc {:08X}", cycle_counter());
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
