use core::fmt::Write;

use super::game_lib::gb_mem;
use super::hook::{
    add_div_tracker, adiv_cycles, adiv_tick, call_log_count, call_log_entry, call_log_start,
    call_log_stop, cyc_hook_ret, cyc_hook_word, cycle_counter, deep_log_clear, deep_log_count,
    deep_log_entry, deep_log_start, deep_log_stop, measured_div, rng_advance, sdiv_cycles,
    sdiv_tick, sub_div_tracker, wide_ctx_byte, wide_log_count, wide_log_meta, wide_near_byte,
    CTX_WIDE_LEN, DIV_NEAR_LEN, WIDE_LOG_LEN,
};
use super::reader::Gen2Reader;
use crate::pnp;

/// Frames kept in RAM. Entries also include two 64-bit host ticks for timing. The buffer
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
    pub atick: u64,
    pub stick: u64,
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
        atick: 0,
        stick: 0,
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
    pub atick: u64,
    pub stick: u64,
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
    /// True from Y+X until a non-probe Trace explicitly replaces this session.
    /// Kept after stop/result so manual saves can still report which Target was armed.
    probe_session: bool,
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
            probe_session: false,
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
        // Y+X is handled directly by the C pause loop, so synchronize all
        // queued host counters here.  Otherwise an old Y+START/Y+SELECT/Y+A
        // request can be observed on the first resumed frame and silently
        // cancel a freshly armed probe.
        let (arm_id, _) = pnp::trace_request();
        let (stop_req, save_req) = pnp::trace_cmds();
        self.last_arm_id = arm_id;
        self.last_stop_req = stop_req;
        self.last_save_req = save_req;
        self.last_run_id = pnp::fixed_run_id();
        deep_log_clear();
        self.probe_target = ProbeTarget {
            advance: rng_advance(),
            state: reader.rng_state(),
            div: measured_div(),
            adiv: add_div_tracker().index().unwrap_or(0) as u16,
            sdiv: sub_div_tracker().index().unwrap_or(0) as u16,
            acyc: adiv_cycles(),
            scyc: sdiv_cycles(),
            atick: adiv_tick(),
            stick: sdiv_tick(),
            keys: pnp::current_keys() as u16,
        };
        self.probe_result = None;
        self.probe_active = true;
        self.probe_session = true;
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
        self.probe_session = false;
        self.probe_result = None;
        deep_log_clear();
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
            // A legacy Trace must start with an empty Deep section; otherwise
            // it can accidentally save samples from the previous probe.
            deep_log_clear();
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

    fn detect_suicune_result(
        &self,
        observed_advance: u32,
        dv1: u8,
        dv2: u8,
    ) -> Option<ProbeResult> {
        // The frame sampler and the rDIV hook do not necessarily run in the
        // same order within a presented VC frame.  A DV can therefore already
        // be visible in D23D/E while the final 2F60/02B6 entries for that same
        // advance are not yet in CALL_LOG.  Retry the visible DV against the
        // current and two immediately preceding advances.  This fixes the
        // live-probe failure seen in 0054, where the full Random burst exists
        // in the saved call section but was not available at the first frame
        // on which the DV bytes became visible.
        let total = call_log_count() as usize;
        let shown = total.min(super::hook::CALL_LOG_LEN);
        if shown < 4 {
            return None;
        }

        let is_vblank_a = |pc: u16| pc == 0x02b5 || pc == 0x02b6;
        let is_random_a = |pc: u16| pc == 0x2f60;

        for lag in 0..=2u32 {
            let advance = observed_advance.wrapping_sub(lag);
            let offset = advance.wrapping_sub(self.probe_target.advance);
            if !(680..=780).contains(&offset) {
                continue;
            }

            // Find the VBlank-A read on this candidate advance whose resulting
            // Sub byte is the DV2 byte now visible in wEnemyMon.
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
            let Some(end) = end else { continue };

            // The immediately preceding VBlank-A delimits the stationary
            // encounter generation burst. Count first-rDIV Random reads.
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
                continue;
            }
            let Some((last_random_index, last_random_entry)) = last_random else {
                continue;
            };
            if last_random_entry.sub != dv1 {
                continue;
            }

            // Startup control keys are normally released within the first ~20
            // frames. Treat everything from rel 32 onward as the clean tail.
            let clean_tail = self
                .entries
                .iter()
                .take(self.len)
                .enumerate()
                .filter(|(i, _)| *i >= 32)
                .all(|(_, e)| e.keys == 0);

            return Some(ProbeResult {
                dv_advance: advance,
                offset,
                route,
                raw_dv: ((dv1 as u16) << 8) | dv2 as u16,
                first_call_index: (total - shown + start) as u32,
                final_call_index: (total - shown + end.max(last_random_index)) as u32,
                clean_tail,
            });
        }

        None
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
                // A new Fixed run without a fresh Y+X is a legacy trace, not a
                // continuation of the previous probe result.
                self.probe_session = false;
                self.probe_result = None;
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
            atick: adiv_tick(),
            stick: sdiv_tick(),
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

        // Probe metadata comes first.  Even when result auto-detection did not
        // complete, preserve the exact Y+X Target so a failed/mis-armed trial
        // can be diagnosed instead of looking like an ordinary legacy Trace.
        if self.probe_session {
            let phase_a = self.probe_target.adiv & 15;
            let phase_s = self.probe_target.sdiv & 15;
            let _ = write!(
                line,
                "probe,target,target_state,target_div,target_adiv,target_sdiv,target_acyc,target_scyc,target_atick,target_stick,target_keys,phase_a,phase_s,result,dv_advance,offset,route,raw_dv,clean_tail,call_first,call_final,deep_samples\n"
            );
            pnp::trace_file_write(line.as_bytes());
            line.clear();
            if let Some(result) = self.probe_result {
                let _ = write!(
                    line,
                    "SUICUNE,{},{:04X},{:04X},{},{},{},{},{},{},{:04X},{},{},OK,{},{},{},{:04X},{},{},{},{}\n\n",
                    self.probe_target.advance,
                    self.probe_target.state,
                    self.probe_target.div,
                    self.probe_target.adiv,
                    self.probe_target.sdiv,
                    self.probe_target.acyc,
                    self.probe_target.scyc,
                    self.probe_target.atick,
                    self.probe_target.stick,
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
            } else {
                let _ = write!(
                    line,
                    "SUICUNE,{},{:04X},{:04X},{},{},{},{},{},{},{:04X},{},{},NO_RESULT,,,,,,,,{}\n\n",
                    self.probe_target.advance,
                    self.probe_target.state,
                    self.probe_target.div,
                    self.probe_target.adiv,
                    self.probe_target.sdiv,
                    self.probe_target.acyc,
                    self.probe_target.scyc,
                    self.probe_target.atick,
                    self.probe_target.stick,
                    self.probe_target.keys,
                    phase_a,
                    phase_s,
                    deep_log_count()
                );
            }
            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\n"
        );
        pnp::trace_file_write(line.as_bytes());

        for index in 0..self.len {
            let entry = self.entries[index];
            line.clear();
            let _ = write!(
                line,
                "{},{},{},{:04X},{:04X},{},{},{},{},{},{},{:04X},{},",
                index,
                entry.advance.wrapping_sub(self.start_advance),
                entry.advance,
                entry.state,
                entry.div,
                entry.adiv,
                entry.sdiv,
                entry.acyc,
                entry.scyc,
                entry.atick,
                entry.stick,
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
        let _ = write!(line, "\ncall_index,pc,advance,add,sub,div,cycles,host_tick\n");
        pnp::trace_file_write(line.as_bytes());

        let total = call_log_count() as usize;
        let shown = total.min(super::hook::CALL_LOG_LEN);
        for i in 0..shown {
            let e = call_log_entry(i);
            line.clear();
            let _ = write!(
                line,
                "{},{:04X},{},{:02X},{:02X},{:04X},{},{}\n",
                total - shown + i,
                e.pc,
                e.advance,
                e.add,
                e.sub,
                e.div,
                e.cycles,
                e.host_tick
            );
            pnp::trace_file_write(line.as_bytes());
        }

        // Third section: high-information samples from the first rDIV read
        // of each Random call.  Memory blobs are hex strings so they remain a
        // valid single CSV field without quoting.
        line.clear();
        let _ = write!(
            line,
            "\ndeep_index,pc,advance,add,sub,div,cycles,host_tick,r0,r1,r2,r3,r4,r5,r6,r7,r8,r9,r10,r11,r12,lr,host_pc,stk0,stk1,stk2,stk3,stk4,stk5,stk6,stk7,cpu_ctx_22f5e0_64,wram_d200_d27f,hram_ff80_ffff\n"
        );
        pnp::trace_file_write(line.as_bytes());

        let deep_total = deep_log_count() as usize;
        let deep_shown = deep_total.min(super::hook::DEEP_LOG_LEN);
        for i in 0..deep_shown {
            let e = deep_log_entry(i);
            line.clear();
            let _ = write!(
                line,
                "{},{:04X},{},{:02X},{:02X},{:04X},{},{}",
                deep_total - deep_shown + i,
                e.pc,
                e.advance,
                e.add,
                e.sub,
                e.div,
                e.cycles,
                e.host_tick
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

        // Fourth section: exactly eight first-VBlank rDIV snapshots for
        // locating the emulator's internal 16-bit divider.  The blobs are
        // streamed in small chunks because a 1 KiB snapshot expands to 2048
        // hex characters, larger than LineBuf by design.
        line.clear();
        let _ = write!(
            line,
            "\nwide_index,pc,advance,div,host_tick,div_ptr,ctx_base,ctx_valid,ctx_bytes,near_base,near_valid,near_bytes,cyc_hook_word,cyc_hook_ret\n"
        );
        pnp::trace_file_write(line.as_bytes());

        let wide_shown = (wide_log_count() as usize).min(WIDE_LOG_LEN);
        for i in 0..wide_shown {
            let e = wide_log_meta(i);

            line.clear();
            let _ = write!(
                line,
                "{},{:04X},{},{:02X},{},{:08X},{:08X},{},",
                i,
                e.pc,
                e.advance,
                e.div,
                e.host_tick,
                e.div_ptr,
                e.ctx_base,
                e.ctx_valid
            );
            pnp::trace_file_write(line.as_bytes());

            for start in (0..CTX_WIDE_LEN).step_by(256) {
                line.clear();
                let end = core::cmp::min(start + 256, CTX_WIDE_LEN);
                for offset in start..end {
                    let _ = write!(line, "{:02X}", wide_ctx_byte(i, offset));
                }
                pnp::trace_file_write(line.as_bytes());
            }

            line.clear();
            let _ = write!(line, ",{:08X},{},", e.near_base, e.near_valid);
            pnp::trace_file_write(line.as_bytes());

            for start in (0..DIV_NEAR_LEN).step_by(256) {
                line.clear();
                let end = core::cmp::min(start + 256, DIV_NEAR_LEN);
                for offset in start..end {
                    let _ = write!(line, "{:02X}", wide_near_byte(i, offset));
                }
                pnp::trace_file_write(line.as_bytes());
            }

            line.clear();
            let _ = write!(line, ",{:08X},{:08X}\n", cyc_hook_word(), cyc_hook_ret());
            pnp::trace_file_write(line.as_bytes());
        }

        pnp::trace_file_close();
        self.save_index += 1;
        self.save_result = Some(true);
    }

    /// Compact status block for the RNG page.  This is deliberately visible
    /// outside the Trace tab because most Suicune work is done while watching
    /// State/DIV/Advance.  While paused, the display refreshes on the next
    /// allowed Fixed frame, so after Y+L returns to pause the user can verify
    /// Probe REC before pressing R.
    pub fn draw_rng_status(&self) {
        let fixed = pnp::fixed_a_frame();
        let run = if fixed.pending {
            "WAIT"
        } else if fixed.running {
            "RUN"
        } else {
            "-"
        };
        pnp::println!(
            "Fix {} A{} {} U{}",
            fixed.frames,
            fixed.armed as u8,
            run,
            fixed.physical_up as u8
        );

        if self.probe_active {
            let mode = if self.state == TraceState::Armed { "ARM" } else { "REC" };
            pnp::println!("Probe {} T{}", mode, self.probe_target.advance);
            pnp::println!(
                "Ph {}/{} D{} W{}",
                self.probe_target.adiv & 15,
                self.probe_target.sdiv & 15,
                deep_log_count(),
                wide_log_count()
            );
        } else if let Some(result) = self.probe_result {
            pnp::println!("Probe OK +{} {}c", result.offset, result.route);
            pnp::println!(
                "DV {:04X} D{} W{}",
                result.raw_dv,
                deep_log_count(),
                wide_log_count()
            );
        } else if self.probe_session {
            pnp::println!("Probe STOP T{}", self.probe_target.advance);
            pnp::println!("NO RESULT D{} W{}", deep_log_count(), wide_log_count());
        } else {
            pnp::println!("Probe OFF");
            pnp::println!("Deep 0");
        }
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
                    _ => {
                        self.probe_session = false;
                        self.probe_result = None;
                        self.start(reader);
                    }
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
        pnp::println!("watch {:04X} chg {}", self.watch_addr, self.watch_changes);
        pnp::println!(
            "calls {} d{} w{}",
            call_log_count(),
            deep_log_count(),
            wide_log_count()
        );
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
        pnp::println!("CH {:08X} R{:08X}", cyc_hook_word(), cyc_hook_ret());
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
