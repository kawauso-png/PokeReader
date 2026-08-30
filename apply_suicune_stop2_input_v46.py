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


# v4.6 is an input-sensitivity experiment.  Pause at the first proven late
# stop (stop2), let the user resume with BASE/UP/A held, and measure how the
# path to the already-proven DV-2 endpoint changes.  At Endpoint we also run
# the late predictor while frozen, then resume with a completely uninstrumented
# PURETAIL (no Deep, no call log, no route counter).

# Extend EndpointSnapshot with the frozen prediction.  Use the full struct tail
# to avoid colliding with other structs that also contain stick/keys fields.
replace_once(
    """pub struct EndpointSnapshot {
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
}""",
    """pub struct EndpointSnapshot {
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
    pub pred_route: u8,
    pub pred_raw: u16,
    pub pred_item1: u8,
    pub pred_item2: u8,
}""",
    "extend EndpointSnapshot",
)

# Exact late timing model.  0032/0034 validated route3.  The route4 constants
# are not donor fits: 108M between DV calls implies a 101M BattleRandom
# turnaround (108 - ld b,a 1M - call 6M).  Therefore item1->item2 is
# 101+(cp2+ld2+jr-not2+call6)=113M; item2->DV1 is 101+261 common path +
# (cp2+ld abs4+jr-taken3)=371M, or +3M when Item2 is selected.
replace_once(
    "#[derive(Clone, Copy, PartialEq, Eq)]\npub enum TraceState {",
    """const EP46_FRAME_M: u16 = 1172;
const EP46_VBLANK_A_TO_RANDOM_A: u16 = 11752;
const EP46_RANDOM_PAIR_M: u16 = 11;
const EP46_ROUTE3_ITEM_TO_DV1_M: u16 = 369;
const EP46_DV_TO_DV_M: u16 = 108;
const EP46_ROUTE4_ITEM1_TO_ITEM2_M: u16 = 113;
const EP46_ROUTE4_ITEM2_TO_DV1_COMMON_M: u16 = 371;
const EP46_ROUTE4_ITEM2_EXTRA_M: u16 = 3;

fn ep46_phase_add(phase: u16, delta: u16) -> u16 {
    phase.wrapping_add(delta) & 0x3fff
}

fn ep46_div(phase: u16) -> u8 {
    (phase >> 6) as u8
}

fn ep46_update(state: u16, adiv: u8, sdiv: u8) -> u16 {
    let add = (state >> 8) as u8;
    let sub = state as u8;
    let (new_add, carry) = add.overflowing_add(adiv);
    let new_sub = sub.wrapping_sub(sdiv).wrapping_sub(carry as u8);
    ((new_add as u16) << 8) | new_sub as u16
}

fn ep46_random(state: u16, aphase: u16) -> (u16, u16) {
    let sphase = ep46_phase_add(aphase, EP46_RANDOM_PAIR_M);
    (ep46_update(state, ep46_div(aphase), ep46_div(sphase)), sphase)
}

fn ep46_predict(mut state: u16, mut ap4: u16, mut sp4: u16) -> (u8, u16, u8, u8) {
    for _ in 0..2 {
        ap4 = ep46_phase_add(ap4, EP46_FRAME_M);
        sp4 = ep46_phase_add(sp4, EP46_FRAME_M);
        state = ep46_update(state, ep46_div(ap4), ep46_div(sp4));
    }

    let item1_a = ep46_phase_add(ap4, EP46_VBLANK_A_TO_RANDOM_A);
    let (after_item1, item1_s) = ep46_random(state, item1_a);
    let item1 = after_item1 as u8;

    if item1 < 0xc0 {
        let dv1_a = ep46_phase_add(item1_s, EP46_ROUTE3_ITEM_TO_DV1_M);
        let (after_dv1, dv1_s) = ep46_random(after_item1, dv1_a);
        let dv_hi = after_dv1 as u8;
        let dv2_a = ep46_phase_add(dv1_s, EP46_DV_TO_DV_M);
        let (after_dv2, _) = ep46_random(after_dv1, dv2_a);
        (3, ((dv_hi as u16) << 8) | after_dv2 as u8 as u16, item1, 0)
    } else {
        let item2_a = ep46_phase_add(item1_s, EP46_ROUTE4_ITEM1_TO_ITEM2_M);
        let (after_item2, item2_s) = ep46_random(after_item1, item2_a);
        let item2 = after_item2 as u8;
        let extra = if item2 < 0x14 { EP46_ROUTE4_ITEM2_EXTRA_M } else { 0 };
        let dv1_a = ep46_phase_add(
            item2_s,
            EP46_ROUTE4_ITEM2_TO_DV1_COMMON_M + extra,
        );
        let (after_dv1, dv1_s) = ep46_random(after_item2, dv1_a);
        let dv_hi = after_dv1 as u8;
        let dv2_a = ep46_phase_add(dv1_s, EP46_DV_TO_DV_M);
        let (after_dv2, _) = ep46_random(after_dv1, dv2_a);
        (4, ((dv_hi as u16) << 8) | after_dv2 as u8 as u16, item1, item2)
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TraceState {""",
    "insert v4.6 predictor",
)

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

# Capture the stop2 entry and pause immediately.
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
        // user resumes. R (0x0100) is stripped because every test uses it.
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

# Compute prediction at the frozen Endpoint before PURETAIL resumes.
replace_once(
    """            self.endpoint.atick = current.atick;
            self.endpoint.stick = current.stick;
            self.endpoint.keys = current.keys;

            // run_frame() is executing on the top-screen present hook.""",
    """            self.endpoint.atick = current.atick;
            self.endpoint.stick = current.stick;
            self.endpoint.keys = current.keys;
            let (pred_route, pred_raw, pred_item1, pred_item2) = ep46_predict(
                self.endpoint.state,
                self.endpoint.ap4,
                self.endpoint.sp4,
            );
            self.endpoint.pred_route = pred_route;
            self.endpoint.pred_raw = pred_raw;
            self.endpoint.pred_item1 = pred_item1;
            self.endpoint.pred_item2 = pred_item2;

            // run_frame() is executing on the top-screen present hook.""",
    "compute endpoint prediction",
)

# Compact sensitivity section.  The normalized residual removes 1172M for
# every remaining repeated stop2 frame. Existing no-input traces 0031-0035
# collapse to roughly A=0x36e8..0x36f8 and S=0x36f0..0x36f3.
replace_once(
    """        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );""",
    """        let _ = write!(
            line,
            \"input_probe,status,stop2_state,stop2_div,stop2_ap4,stop2_sp4,key_or,key_frames,total_frames,stop2_resume_repeats,endpoint_state,endpoint_ap4,endpoint_sp4,delta_ap4,delta_sp4,norm_ap4,norm_sp4,pred_route,pred_raw,pred_item1,pred_item2\\n\"
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
                \"INPUT,OK,{:04X},{:04X},{:04X},{:04X},{:04X},{},{},{},{:04X},{:04X},{:04X},{:04X},{:04X},{:04X},{:04X},{},{:04X},{:02X},{:02X}\\n\\n\",
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
                norm_sp4,
                self.endpoint.pred_route,
                self.endpoint.pred_raw,
                self.endpoint.pred_item1,
                self.endpoint.pred_item2
            );
        } else {
            let _ = write!(line, \"INPUT,INCOMPLETE,,,,,,,,,,,,,,,,,,,,\\n\\n\");
        }
        pnp::trace_file_write(line.as_bytes());
        line.clear();

        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );""",
    "insert v4.6 csv section",
)

# Identify both pause stages on screen.
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
            pnp::println!(\"NR {:04X}/{:04X}\", norm_ap4, norm_sp4);
            pnp::println!(
                \"P R{} DV{:04X}\",
                self.endpoint.pred_route,
                self.endpoint.pred_raw
            );""",
    "show input stats and prediction at endpoint",
)

path.write_text(s)
print("Applied Suicune stop2 Input Sensitivity Probe v4.6")
