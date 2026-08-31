#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"marker not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


BREEDING_RS = r'''use core::fmt::Write;

use super::hook::{
    adiv_subtick, call_log_count, call_log_entry, call_log_start, call_log_stop, measured_div,
    rng_advance, sdiv_subtick,
};
use super::reader::Gen2Reader;
use crate::pnp;

const MAX_BREED_FRAMES: usize = 4096;
const EGG_FILE_BASE: u32 = 9000;

#[derive(Clone, Copy)]
struct BreedFrame {
    advance: u32,
    state: u16,
    div: u16,
    keys: u16,
    species: u8,
    dv1: u8,
    dv2: u8,
    asub: u8,
    ssub: u8,
}

impl BreedFrame {
    const EMPTY: Self = Self {
        advance: 0,
        state: 0,
        div: 0,
        keys: 0,
        species: 0,
        dv1: 0,
        dv2: 0,
        asub: 0,
        ssub: 0,
    };
}

static mut BREED_FRAMES: [BreedFrame; MAX_BREED_FRAMES] = [BreedFrame::EMPTY; MAX_BREED_FRAMES];

#[derive(Clone, Copy, Default)]
struct BreedTarget {
    advance: u32,
    state: u16,
    div: u16,
    asub: u8,
    ssub: u8,
    species: u8,
    dvs: u16,
}

#[derive(Clone, Copy, Default)]
struct BreedResult {
    advance: u32,
    species: u8,
    dvs: u16,
    shiny: bool,
    random_calls: u32,
    total_calls: u32,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum BreedState {
    Off,
    Armed,
    Done,
    Timeout,
    Cancelled,
}

impl BreedState {
    fn text(self) -> &'static str {
        match self {
            Self::Off => "OFF",
            Self::Armed => "ARMED",
            Self::Done => "DONE",
            Self::Timeout => "TIMEOUT",
            Self::Cancelled => "CANCEL",
        }
    }
}

struct LineBuf {
    buf: [u8; 512],
    len: usize,
}

impl LineBuf {
    fn new() -> Self {
        Self { buf: [0; 512], len: 0 }
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

pub struct BreedingProbe {
    frames: &'static mut [BreedFrame],
    len: usize,
    state: BreedState,
    target: BreedTarget,
    result: Option<BreedResult>,
    scanned_calls: u32,
    random_calls: u32,
    random_tail: [u32; 3],
    save_index: u32,
    save_result: Option<bool>,
    saved_slot: u32,
}

impl Default for BreedingProbe {
    fn default() -> Self {
        Self {
            frames: unsafe { &mut *core::ptr::addr_of_mut!(BREED_FRAMES) },
            len: 0,
            state: BreedState::Off,
            target: BreedTarget::default(),
            result: None,
            scanned_calls: 0,
            random_calls: 0,
            random_tail: [0; 3],
            save_index: 1,
            save_result: None,
            saved_slot: 0,
        }
    }
}

impl BreedingProbe {
    pub fn toggle(&mut self, reader: &Gen2Reader) {
        if self.state == BreedState::Armed {
            call_log_stop();
            self.state = BreedState::Cancelled;
            return;
        }

        self.len = 0;
        self.result = None;
        self.scanned_calls = 0;
        self.random_calls = 0;
        self.random_tail = [0; 3];
        self.save_result = None;
        self.target = BreedTarget {
            advance: rng_advance(),
            state: reader.rng_state(),
            div: measured_div(),
            asub: adiv_subtick(),
            ssub: sdiv_subtick(),
            species: reader.egg_species_raw(),
            dvs: reader.egg_raw_dvs(),
        };
        call_log_start();
        self.state = BreedState::Armed;
    }

    fn scan_new_calls(&mut self) {
        let total = call_log_count();
        while self.scanned_calls < total {
            let entry = call_log_entry(self.scanned_calls as usize);
            if entry.pc == 0x2f60 {
                self.random_calls = self.random_calls.wrapping_add(1);
                self.random_tail[0] = self.random_tail[1];
                self.random_tail[1] = self.random_tail[2];
                self.random_tail[2] = entry.advance;
            }
            self.scanned_calls += 1;
        }
    }

    fn breeding_random_burst_seen(&self) -> bool {
        self.random_calls >= 3
            && self.random_tail[2].wrapping_sub(self.random_tail[0]) <= 2
    }

    pub fn record(&mut self, reader: &Gen2Reader) {
        if self.state != BreedState::Armed {
            return;
        }

        self.scan_new_calls();

        if self.len >= MAX_BREED_FRAMES {
            call_log_stop();
            self.state = BreedState::Timeout;
            self.save();
            pnp::request_pause();
            return;
        }

        let species = reader.egg_species_raw();
        let dvs = reader.egg_raw_dvs();
        let dv1 = (dvs >> 8) as u8;
        let dv2 = dvs as u8;

        self.frames[self.len] = BreedFrame {
            advance: rng_advance(),
            state: reader.rng_state(),
            div: measured_div(),
            keys: pnp::current_keys() as u16,
            species,
            dv1,
            dv2,
            asub: adiv_subtick(),
            ssub: sdiv_subtick(),
        };
        self.len += 1;

        let changed = species != self.target.species || dvs != self.target.dvs;
        if species != 0 && (changed || self.breeding_random_burst_seen()) {
            call_log_stop();
            self.result = Some(BreedResult {
                advance: rng_advance(),
                species,
                dvs,
                shiny: reader.egg().shiny,
                random_calls: self.random_calls,
                total_calls: call_log_count(),
            });
            self.state = BreedState::Done;
            self.save();
            pnp::request_pause();
        }
    }

    fn save(&mut self) {
        if self.len == 0 {
            self.save_result = Some(false);
            return;
        }

        if !pnp::trace_file_open(EGG_FILE_BASE + self.save_index) {
            self.save_result = Some(false);
            return;
        }

        let mut line = LineBuf::new();
        let _ = write!(
            line,
            "probe,target_advance,target_state,target_div,target_asub,target_ssub,initial_species,initial_dvs,result,result_advance,result_species,result_dvs,shiny,frames,random_calls,total_calls\n"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();

        if let Some(result) = self.result {
            let _ = write!(
                line,
                "BREEDING,{},{:04X},{:04X},{:02X},{:02X},{:02X},{:04X},OK,{},{:02X},{:04X},{},{},{},{}\n\n",
                self.target.advance,
                self.target.state,
                self.target.div,
                self.target.asub,
                self.target.ssub,
                self.target.species,
                self.target.dvs,
                result.advance,
                result.species,
                result.dvs,
                result.shiny as u8,
                self.len,
                result.random_calls,
                result.total_calls
            );
        } else {
            let _ = write!(
                line,
                "BREEDING,{},{:04X},{:04X},{:02X},{:02X},{:02X},{:04X},{},,,,,{},{},{}\n\n",
                self.target.advance,
                self.target.state,
                self.target.div,
                self.target.asub,
                self.target.ssub,
                self.target.species,
                self.target.dvs,
                self.state.text(),
                self.len,
                self.random_calls,
                call_log_count()
            );
        }
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,asub,ssub,keys,egg_species,egg_dv1,egg_dv2,changed\n"
        );
        pnp::trace_file_write(line.as_bytes());

        for index in 0..self.len {
            let e = self.frames[index];
            line.clear();
            let dvs = ((e.dv1 as u16) << 8) | e.dv2 as u16;
            let changed = e.species != self.target.species || dvs != self.target.dvs;
            let _ = write!(
                line,
                "{},{},{},{:04X},{:04X},{:02X},{:02X},{:04X},{:02X},{:02X},{:02X},{}\n",
                index,
                e.advance.wrapping_sub(self.target.advance),
                e.advance,
                e.state,
                e.div,
                e.asub,
                e.ssub,
                e.keys,
                e.species,
                e.dv1,
                e.dv2,
                changed as u8
            );
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _ = write!(
            line,
            "\ncall_index,pc,advance,add,sub,div,cycles,host_tick,mcycle,is_random\n"
        );
        pnp::trace_file_write(line.as_bytes());

        let total = call_log_count() as usize;
        let shown = total.min(super::hook::CALL_LOG_LEN);
        for i in 0..shown {
            let e = call_log_entry(i);
            line.clear();
            let _ = write!(
                line,
                "{},{:04X},{},{:02X},{:02X},{:04X},{},{},{:02X},{}\n",
                total - shown + i,
                e.pc,
                e.advance,
                e.add,
                e.sub,
                e.div,
                e.cycles,
                e.host_tick,
                e.mcycle,
                (e.pc == 0x2f60) as u8
            );
            pnp::trace_file_write(line.as_bytes());
        }

        pnp::trace_file_close();
        self.saved_slot = pnp::trace_written_slot();
        self.save_index = self.saved_slot.saturating_add(1);
        self.save_result = Some(true);
    }

    pub fn draw_status(&self) {
        pnp::println!("");
        pnp::println!("BreedProbe {}", self.state.text());
        match self.result {
            Some(result) => {
                pnp::println!("Raw DV {:04X}", result.dvs);
                pnp::println!("Shiny {} R{}", result.shiny as u8, result.random_calls);
            }
            None if self.state == BreedState::Armed => {
                pnp::println!("Target {}", self.target.advance);
                pnp::println!("Rand {} F{}", self.random_calls, self.len);
            }
            _ => {}
        }
        match self.save_result {
            Some(true) => pnp::println!("EggCSV {:04}", self.saved_slot),
            Some(false) => pnp::println!("EggCSV ERR"),
            None => pnp::println!("Y+Down arm/cancel"),
        }
    }
}
'''

Path("reader_core/src/crystal/breeding.rs").write_text(BREEDING_RS)

replace_once(
    "reader_core/src/crystal/mod.rs",
    "mod draw;\n",
    "mod breeding;\nmod draw;\n",
)
replace_once(
    "reader_core/src/crystal/mod.rs",
    "pub use frame::{arm_suicune_probe, run_frame};",
    "pub use frame::{arm_breeding_probe, arm_suicune_probe, run_frame};",
)

replace_once(
    "reader_core/src/lib.rs",
    '''#[no_mangle]\npub extern "C" fn arm_suicune_probe() {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        crystal::arm_suicune_probe();\n    }\n}\n''',
    '''#[no_mangle]\npub extern "C" fn arm_suicune_probe() {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        crystal::arm_suicune_probe();\n    }\n}\n\n#[no_mangle]\npub extern "C" fn arm_breeding_probe() {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        crystal::arm_breeding_probe();\n    }\n}\n''',
)

replace_once(
    "3gx/includes/pokereader.h",
    "void arm_suicune_probe();",
    "void arm_suicune_probe();\nvoid arm_breeding_probe();",
)

replace_once(
    "3gx/sources/main.c",
    '''            if (just_pressed & KEY_X)\n            {\n                arm_suicune_probe();\n            }\n            // Y + START arms the legacy full trace without advancing a frame.\n''',
    '''            if (just_pressed & KEY_X)\n            {\n                arm_suicune_probe();\n            }\n            // Y + DOWN arms/cancels the Crystal breeding probe at the exact\n            // frozen state. No game frame is allowed through here.\n            if (just_pressed & KEY_DDOWN)\n            {\n                arm_breeding_probe();\n            }\n            // Y + START arms the legacy full trace without advancing a frame.\n''',
)

replace_once(
    "3gx/sources/main.c",
    '''        sprintf(path, "/luma/plugins/pokereader/traces/celebi_trace_%04lu.csv", (unsigned long)slot);''',
    '''        if (index >= 9000)\n        {\n            sprintf(path, "/luma/plugins/pokereader/traces/egg_trace_%04lu.csv", (unsigned long)(slot - 9000));\n        }\n        else\n        {\n            sprintf(path, "/luma/plugins/pokereader/traces/celebi_trace_%04lu.csv", (unsigned long)slot);\n        }''',
)
replace_once(
    "3gx/sources/main.c",
    "    trace_written_slot = slot;",
    "    trace_written_slot = index >= 9000 ? slot - 9000 : slot;",
)

replace_once(
    "reader_core/src/crystal/reader.rs",
    '''    pub fn rng_state(&self) -> u16 {\n        gb_mem::read_u16(self.addrs.gb_rng_ptr)\n    }\n''',
    '''    pub fn egg_species_raw(&self) -> u8 {\n        gb_mem::read_u8(self.addrs.egg_ptr)\n    }\n\n    pub fn egg_raw_dvs(&self) -> u16 {\n        let atkdef = gb_mem::read_u8(self.addrs.egg_ptr + 0x15);\n        let spespc = gb_mem::read_u8(self.addrs.egg_ptr + 0x16);\n        ((atkdef as u16) << 8) | spespc as u16\n    }\n\n    pub fn rng_state(&self) -> u16 {\n        gb_mem::read_u16(self.addrs.gb_rng_ptr)\n    }\n''',
)

replace_once(
    "reader_core/src/crystal/frame.rs",
    '''    trace: super::trace::Trace,\n}\n''',
    '''    trace: super::trace::Trace,\n    breeding: super::breeding::BreedingProbe,\n}\n''',
)
replace_once(
    "reader_core/src/crystal/frame.rs",
    '''        trace: super::trace::Trace::default(),\n        main_menu: Menu::new(MENU),\n''',
    '''        trace: super::trace::Trace::default(),\n        breeding: super::breeding::BreedingProbe::default(),\n        main_menu: Menu::new(MENU),\n''',
)
replace_once(
    "reader_core/src/crystal/frame.rs",
    '''pub fn arm_suicune_probe() {\n    let reader = Gen2Reader::crystal();\n    let state = unsafe { get_state() };\n    state.trace.arm_suicune_probe(&reader);\n}\n\npub fn run_frame() {\n''',
    '''pub fn arm_suicune_probe() {\n    let reader = Gen2Reader::crystal();\n    let state = unsafe { get_state() };\n    state.trace.arm_suicune_probe(&reader);\n}\n\n/// Invoked from the C pause loop by Y+DOWN. This captures the exact frozen\n/// state before the daycare script is allowed to run.\npub fn arm_breeding_probe() {\n    let reader = Gen2Reader::crystal();\n    let state = unsafe { get_state() };\n    state.trace.stop();\n    state.breeding.toggle(&reader);\n}\n\npub fn run_frame() {\n''',
)
replace_once(
    "reader_core/src/crystal/frame.rs",
    '''    state.trace.record(&reader);\n\n    if !state.show_view.check() {\n''',
    '''    state.trace.record(&reader);\n    state.breeding.record(&reader);\n\n    if !state.show_view.check() {\n''',
)
replace_once(
    "reader_core/src/crystal/frame.rs",
    '''        CrystalView::Egg => draw_pkx(&reader.egg()),\n''',
    '''        CrystalView::Egg => {\n            draw_pkx(&reader.egg());\n            state.breeding.draw_status();\n        }\n''',
)

print("Crystal breeding RNG v1 patch applied")
