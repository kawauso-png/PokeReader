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


# v4.6 is an input-sensitivity experiment, not a new predictor.  Pause at the
# first proven late stop (stop2), let the user resume with BASE/UP/A held, and
# automatically measure how the path from stop2 to the already-proven DV-2
# endpoint changes.  PURETAIL remains enabled only after Endpoint as in v4.4.

replace_once(
    """    endpoint: EndpointSnapshot,
    endpoint_pause_requested: bool,
    /// Row shown first in the on screen table.""",
    """    endpoint: EndpointSnapshot,
    endpoint_pause_requested: bool,
    // v4.6 stop2 input-sensitivity probe.  The stop2 pause happens on the
    // second row of the repeated-advance group, so every run resumes from the
    // same structural point.  Pause time itself does not advance emulation.
    input_stop2_pause_requested: bool,
    input_stop2_pause_len: usize,
    input_stop2_state: u16,
    input_stop2_div: u16,
    input_stop2_ap4: u16,
    input_stop2_sp4: u16,
    input_key_or: u16,
    input_key_frames: u32,
    input_total_frames: u32,
    input_stop2_resume_repeats: u32,
    /// Row shown first in the on screen table.""",
    "add v4.6 fields",
)

replace_once(
    """            endpoint: EndpointSnapshot::default(),
            endpoint_pause_requested: false,
            cursor: 0,""",
    """            endpoint: EndpointSnapshot::default(),
            endpoint_pause_requested: false,
            input_stop2_pause_requested: false,
            input_stop2_pause_len: 0,
            input_stop2_state: 0,
            input_stop2_div: 0,
            input_stop2_ap4: 0,
            input_stop2_sp4: 0,
            input_key_or: 0,
            input_key_frames: 0,
            input_total_frames: 0,
            input_stop2_resume_repeats: 0,
            cursor: 0,""",
    "init v4.6 fields",
)

replace_once(
    """        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;""",
    """        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;
        self.input_stop2_pause_requested = false;
        self.input_stop2_pause_len = 0;
        self.input_stop2_state = 0;
        self.input_stop2_div = 0;
        self.input_stop2_ap4 = 0;
        self.input_stop2_sp4 = 0;
        self.input_key_or = 0;
        self.input_key_frames = 0;
        self.input_total_frames = 0;
        self.input_stop2_resume_repeats = 0;""",
    "reset v4.6 fields",
)

# Capture the stop2 entry and pause immediately.  This is inserted directly
# after v4.1 sets the structural stop2 fields.
replace_once(
    """                self.endpoint.expected_dv_advance = current.advance.wrapping_add(13);
                self.endpoint.pause_advance = current.advance.wrapping_add(11);
            }
        }

        if self.endpoint.stop2_advance != 0""",
    """                self.endpoint.expected_dv_advance = current.advance.wrapping_add(13);
                self.endpoint.pause_advance = current.advance.wrapping_add(11);

                self.input_stop2_state = current.state;
                self.input_stop2_div = current.div;
                self.input_stop2_ap4 = direct_phase_m((current.div >> 8) as u8, current.asub);
                self.input_stop2_sp4 = direct_phase_m(current.div as u8, current.ssub);
                self.input_stop2_pause_len = self.len;
                if !self.input_stop2_pause_requested {
                    self.input_stop2_pause_requested = true;
                    pnp::request_pause();
                }
            }
        }

        // The next recorded row after request_pause() can only occur after the
        // user resumes.  From there until Endpoint, record the actual physical
        // stimulus.  R (0x0100) is stripped because it is the common resume key
        // in every test; BASE/UP/A are therefore directly comparable.
        if self.input_stop2_pause_requested
            && self.input_stop2_pause_len != 0
            && self.len > self.input_stop2_pause_len
            && self.endpoint.capture_advance == 0
        {
            let stimulus = current.keys & !0x0100u16;
            self.input_key_or |= stimulus;
            self.input_total_frames = self.input_total_frames.wrapping_add(1);
            if stimulus != 0 {
                self.input_key_frames = self.input_key_frames.wrapping_add(1);
            }
            if current.advance == self.endpoint.stop2_advance {
                self.input_stop2_resume_repeats =
                    self.input_stop2_resume_repeats.wrapping_add(1);
            }
        }

        if self.endpoint.stop2_advance != 0""",
    "pause and collect at stop2",
)

# Add a compact self-contained sensitivity section before the Endpoint section.
# The normalized residual removes 1172 M-cycles for every remaining repeated
# stop2 frame.  Existing no-input traces 0031-0035 collapse to roughly
# A=0x36e8..0x36f8 and S=0x36f0..0x36f3, so runs with different Targets and
# 122/123-frame stop2 lengths can be compared directly.
replace_once(
    """        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );""",
    """        let _ = write!(
            line,
            \"input_probe,status,stop2_state,stop2_div,stop2_ap4,stop2_sp4,key_or,key_frames,total_frames,stop2_resume_repeats,endpoint_state,endpoint_ap4,endpoint_sp4,delta_ap4,delta_sp4,norm_ap4,norm_sp4\\n\"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        if self.input_stop2_state != 0 && self.endpoint.capture_advance != 0 {
            let delta_ap4 = self.endpoint.ap4.wrapping_sub(self.input_stop2_ap4) & 0x3fff;
            let delta_sp4 = self.endpoint.sp4.wrapping_sub(self.input_stop2_sp4) & 0x3fff;
            let repeat_m = ((self.input_stop2_resume_repeats as u32 * 1172u32) & 0x3fff) as u16;
            let norm_ap4 = delta_ap4.wrapping_sub(repeat_m) & 0x3fff;
            let norm_sp4 = delta_sp4.wrapping_sub(repeat_m) & 0x3fff;
            let _ = write!(
                line,
                \"INPUT,OK,{:04X},{:04X},{:04X},{:04X},{:04X},{},{},{},{:04X},{:04X},{:04X},{:04X},{:04X},{:04X},{:04X}\\n\\n\",
                self.input_stop2_state,
                self.input_stop2_div,
                self.input_stop2_ap4,
                self.input_stop2_sp4,
                self.input_key_or,
                self.input_key_frames,
                self.input_total_frames,
                self.input_stop2_resume_repeats,
                self.endpoint.state,
                self.endpoint.ap4,
                self.endpoint.sp4,
                delta_ap4,
                delta_sp4,
                norm_ap4,
                norm_sp4
            );
        } else {
            let _ = write!(line, \"INPUT,INCOMPLETE,,,,,,,,,,,,,,,,\\n\\n\");
        }
        pnp::trace_file_write(line.as_bytes());
        line.clear();

        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );""",
    "insert v4.6 csv section",
)

# Identify the build and make the two pause stages unambiguous on-screen.
replace_once(
    '                "EP44 +{} S{:04X}",',
    '                "EP46 +{} S{:04X}",',
    "screen v4.6 endpoint marker",
)

replace_once(
    """        if self.endpoint.capture_advance != 0 {
            pnp::println!(
                \"EP46 +{} S{:04X}\",""",
    """        if self.input_stop2_pause_requested
            && self.endpoint.capture_advance == 0
            && self.endpoint.stop2_advance != 0
        {
            pnp::println!(
                \"S46 +{} S{:04X}\",
                self.endpoint.stop2_offset,
                self.input_stop2_state
            );
            pnp::println!(\"HOLD BASE/UP/A + R\");
        }

        if self.endpoint.capture_advance != 0 {
            pnp::println!(
                \"EP46 +{} S{:04X}\",""",
    "show stop2 instruction",
)

replace_once(
    """            pnp::println!(
                \"EP D{:04X} {:02X}/{:02X}\",
                self.endpoint.div,
                self.endpoint.asub,
                self.endpoint.ssub
            );""",
    """            pnp::println!(
                \"EP D{:04X} {:02X}/{:02X}\",
                self.endpoint.div,
                self.endpoint.asub,
                self.endpoint.ssub
            );
            let delta_ap4 = self.endpoint.ap4.wrapping_sub(self.input_stop2_ap4) & 0x3fff;
            let delta_sp4 = self.endpoint.sp4.wrapping_sub(self.input_stop2_sp4) & 0x3fff;
            let repeat_m = ((self.input_stop2_resume_repeats as u32 * 1172u32) & 0x3fff) as u16;
            let norm_ap4 = delta_ap4.wrapping_sub(repeat_m) & 0x3fff;
            let norm_sp4 = delta_sp4.wrapping_sub(repeat_m) & 0x3fff;
            pnp::println!(
                \"IN K{:04X} F{} R{}\",
                self.input_key_or,
                self.input_key_frames,
                self.input_stop2_resume_repeats
            );
            pnp::println!(\"NR {:04X}/{:04X}\", norm_ap4, norm_sp4);""",
    "show input stats at endpoint",
)

path.write_text(s)
print("Applied Suicune stop2 Input Sensitivity Probe v4.6")
