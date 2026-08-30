#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
s = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    s = s.replace(old, new, 1)


# Endpoint state is intentionally tiny.  v4.1 is a measurement build: it does
# not guess the shiny result yet.  It only detects the proven late stop,
# snapshots DV-2, pauses, and preserves the snapshot next to the actual result.
replace_once(
    "#[derive(Clone, Copy, PartialEq, Eq)]\npub enum TraceState {",
    """#[derive(Clone, Copy, Default)]
pub struct EndpointSnapshot {
    pub stop2_advance: u32,
    pub stop2_offset: u32,
    pub expected_dv_advance: u32,
    pub pause_advance: u32,
    pub capture_advance: u32,
    pub capture_offset: u32,
    pub state: u16,
    pub div: u16,
    pub ap4: u16,
    pub sp4: u16,
    pub asub: u8,
    pub ssub: u8,
    pub atick: u64,
    pub stick: u64,
    pub keys: u16,
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TraceState {""",
    "insert EndpointSnapshot",
)

replace_once(
    "    probe_result: Option<ProbeResult>,\n    /// Row shown first in the on screen table.",
    """    probe_result: Option<ProbeResult>,
    // Endpoint Probe v4.1.  Offline v4.0 found the late repeated-advance
    // boundary (stop2) at +717..+719 and the DV burst exactly 13 advances
    // later.  We therefore capture stop2+11 = DV-2 and pause there.
    endpoint: EndpointSnapshot,
    endpoint_pause_requested: bool,
    /// Row shown first in the on screen table.""",
    "add endpoint fields",
)

replace_once(
    "            probe_result: None,\n            cursor: 0,",
    """            probe_result: None,
            endpoint: EndpointSnapshot::default(),
            endpoint_pause_requested: false,
            cursor: 0,""",
    "init endpoint fields",
)

replace_once(
    "        self.first_change = None;\n        self.save_result = None;",
    """        self.first_change = None;
        self.save_result = None;
        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;""",
    "reset endpoint fields",
)

replace_once(
    "    fn entry(&self, index: usize) -> Option<&TraceEntry> {",
    """    fn update_suicune_endpoint(&mut self) {
        if !self.probe_active || self.len == 0 {
            return;
        }

        let current = self.entries[self.len - 1];
        let rel = current.advance.wrapping_sub(self.probe_target.advance);

        // Mirror analyze_suicune_factor_v40.py exactly: collapse equal
        // advances, then stop2 is the first repeated group whose offset is
        // greater than 600.  The 760 guard only prevents a failed/mis-armed
        // run from mistaking the final encounter frame for stop2.
        if self.endpoint.stop2_advance == 0 && self.len >= 2 {
            let previous = self.entries[self.len - 2];
            if current.advance == previous.advance && rel > 600 && rel <= 760 {
                self.endpoint.stop2_advance = current.advance;
                self.endpoint.stop2_offset = rel;
                self.endpoint.expected_dv_advance = current.advance.wrapping_add(13);
                self.endpoint.pause_advance = current.advance.wrapping_add(11);
            }
        }

        if self.endpoint.stop2_advance != 0
            && self.endpoint.capture_advance == 0
            && current.advance >= self.endpoint.pause_advance
        {
            self.endpoint.capture_advance = current.advance;
            self.endpoint.capture_offset = rel;
            self.endpoint.state = current.state;
            self.endpoint.div = current.div;
            self.endpoint.ap4 = direct_phase_m((current.div >> 8) as u8, current.asub);
            self.endpoint.sp4 = direct_phase_m(current.div as u8, current.ssub);
            self.endpoint.asub = current.asub;
            self.endpoint.ssub = current.ssub;
            self.endpoint.atick = current.atick;
            self.endpoint.stick = current.stick;
            self.endpoint.keys = current.keys;

            // run_frame() is executing on the top-screen present hook.  The
            // existing host pause flag makes the following bottom-screen hook
            // enter the freeze loop, so no extra game frame is released.
            if !self.endpoint_pause_requested {
                self.endpoint_pause_requested = true;
                pnp::request_pause();
            }
        }
    }

    fn entry(&self, index: usize) -> Option<&TraceEntry> {""",
    "insert endpoint detector",
)

replace_once(
    "        self.len += 1;\n\n        if self.probe_active && window[2] == SUICUNE_SPECIES {",
    """        self.len += 1;

        // Detect/capture the late endpoint before the encounter result exists.
        // Recording remains active across the pause; after resume the normal
        // Suicune result detector still locks the real DV and auto-saves it.
        self.update_suicune_endpoint();

        if self.probe_active && window[2] == SUICUNE_SPECIES {""",
    "call endpoint detector",
)

# Add a self-contained endpoint section without changing the existing probe
# header.  Existing v3/v4 CSV parsers that read only the first two probe lines
# therefore continue to work unchanged.
replace_once(
    """            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

        let _ = write!(
            line,
            \"frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n\"
        );""",
    """            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        if self.endpoint.capture_advance != 0 {
            let _ = write!(
                line,
                \"ENDPOINT,OK,{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{:02X},{:02X},{},{},{:04X}\\n\\n\",
                self.endpoint.stop2_advance,
                self.endpoint.stop2_offset,
                self.endpoint.expected_dv_advance,
                self.endpoint.pause_advance,
                self.endpoint.capture_advance,
                self.endpoint.capture_offset,
                self.endpoint.state,
                self.endpoint.div,
                self.endpoint.ap4,
                self.endpoint.sp4,
                self.endpoint.asub,
                self.endpoint.ssub,
                self.endpoint.atick,
                self.endpoint.stick,
                self.endpoint.keys
            );
        } else if self.endpoint.stop2_advance != 0 {
            let _ = write!(
                line,
                \"ENDPOINT,STOP2_ONLY,{},{},{},{},,,,,,,,,,,\\n\\n\",
                self.endpoint.stop2_advance,
                self.endpoint.stop2_offset,
                self.endpoint.expected_dv_advance,
                self.endpoint.pause_advance
            );
        } else {
            let _ = write!(line, \"ENDPOINT,NO_STOP2,,,,,,,,,,,,,,,\\n\\n\");
        }
        pnp::trace_file_write(line.as_bytes());
        line.clear();

        let _ = write!(
            line,
            \"frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n\"
        );""",
    "insert endpoint CSV section",
)

replace_once(
    """        } else {
            pnp::println!(\"Probe OFF\");
            pnp::println!(
                \"LiveSub {:02X}/{:02X} B{}\",
                adiv_subtick(),
                sdiv_subtick(),
                adiv_subtick() >> 3
            );
        }
    }

    pub fn draw(&mut self, reader: &Gen2Reader, is_locked: bool) {""",
    """        } else {
            pnp::println!(\"Probe OFF\");
            pnp::println!(
                \"LiveSub {:02X}/{:02X} B{}\",
                adiv_subtick(),
                sdiv_subtick(),
                adiv_subtick() >> 3
            );
        }

        if self.endpoint.capture_advance != 0 {
            pnp::println!(
                \"EP +{} S{:04X}\",
                self.endpoint.capture_offset,
                self.endpoint.state
            );
            pnp::println!(
                \"EP D{:04X} {:02X}/{:02X}\",
                self.endpoint.div,
                self.endpoint.asub,
                self.endpoint.ssub
            );
        } else if self.endpoint.stop2_advance != 0 {
            pnp::println!(
                \"EP S+{} P+{}\",
                self.endpoint.stop2_offset,
                self.endpoint.pause_advance.wrapping_sub(self.probe_target.advance)
            );
        }
    }

    pub fn draw(&mut self, reader: &Gen2Reader, is_locked: bool) {""",
    "add endpoint RNG status",
)

path.write_text(s)
print("Applied Suicune Endpoint Probe v4.1 (stop2 -> DV-2 auto-pause)")
