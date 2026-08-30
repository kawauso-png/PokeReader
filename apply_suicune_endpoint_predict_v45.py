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


# Store prediction beside the DV-2 endpoint snapshot.  The prediction is
# computed while the game is frozen, before PURETAIL resumes; no extra work is
# added to the final Random burst itself.
replace_once(
    """    pub stick: u64,
    pub keys: u16,
}""",
    """    pub stick: u64,
    pub keys: u16,
    pub pred_route: u8,
    pub pred_raw: u16,
    pub pred_item1: u8,
    pub pred_item2: u8,
}""",
    "extend endpoint snapshot",
)

replace_once(
    "#[derive(Clone, Copy, PartialEq, Eq)]\npub enum TraceState {",
    """const EP45_FRAME_M: u16 = 1172;
const EP45_VBLANK_A_TO_RANDOM_A: u16 = 11752;
const EP45_RANDOM_PAIR_M: u16 = 11;
const EP45_ROUTE3_ITEM_TO_DV1_M: u16 = 369;
const EP45_DV_TO_DV_M: u16 = 108;
const EP45_ROUTE4_ITEM1_TO_ITEM2_M: u16 = 113;
const EP45_ROUTE4_ITEM2_TO_DV1_COMMON_M: u16 = 371;
const EP45_ROUTE4_ITEM2_EXTRA_M: u16 = 3;

fn ep45_phase_add(phase: u16, delta: u16) -> u16 {
    phase.wrapping_add(delta) & 0x3fff
}

fn ep45_div(phase: u16) -> u8 {
    (phase >> 6) as u8
}

fn ep45_update(state: u16, adiv: u8, sdiv: u8) -> u16 {
    let add = (state >> 8) as u8;
    let sub = state as u8;
    let (new_add, carry) = add.overflowing_add(adiv);
    let new_sub = sub.wrapping_sub(sdiv).wrapping_sub(carry as u8);
    ((new_add as u16) << 8) | new_sub as u16
}

fn ep45_random(state: u16, aphase: u16) -> (u16, u16) {
    let sphase = ep45_phase_add(aphase, EP45_RANDOM_PAIR_M);
    (ep45_update(state, ep45_div(aphase), ep45_div(sphase)), sphase)
}

fn ep45_predict(mut state: u16, mut ap4: u16, mut sp4: u16) -> (u8, u16, u8, u8) {
    // Endpoint is DV-2.  Only the DIV byte matters for these two ordinary
    // VBlank updates; the nominal 1172-M-cycle projection has matched every
    // tested endpoint even when the exact AP4 jitter is a few M-cycles.
    for _ in 0..2 {
        ap4 = ep45_phase_add(ap4, EP45_FRAME_M);
        sp4 = ep45_phase_add(sp4, EP45_FRAME_M);
        state = ep45_update(state, ep45_div(ap4), ep45_div(sp4));
    }

    let item1_a = ep45_phase_add(ap4, EP45_VBLANK_A_TO_RANDOM_A);
    let (after_item1, item1_s) = ep45_random(state, item1_a);
    let item1 = after_item1 as u8;

    if item1 < 0xc0 {
        let dv1_a = ep45_phase_add(item1_s, EP45_ROUTE3_ITEM_TO_DV1_M);
        let (after_dv1, dv1_s) = ep45_random(after_item1, dv1_a);
        let dv_hi = after_dv1 as u8;
        let dv2_a = ep45_phase_add(dv1_s, EP45_DV_TO_DV_M);
        let (after_dv2, _) = ep45_random(after_dv1, dv2_a);
        (3, ((dv_hi as u16) << 8) | after_dv2 as u8 as u16, item1, 0)
    } else {
        let item2_a = ep45_phase_add(item1_s, EP45_ROUTE4_ITEM1_TO_ITEM2_M);
        let (after_item2, item2_s) = ep45_random(after_item1, item2_a);
        let item2 = after_item2 as u8;
        let extra = if item2 < 0x14 { EP45_ROUTE4_ITEM2_EXTRA_M } else { 0 };
        let dv1_a = ep45_phase_add(
            item2_s,
            EP45_ROUTE4_ITEM2_TO_DV1_COMMON_M + extra,
        );
        let (after_dv1, dv1_s) = ep45_random(after_item2, dv1_a);
        let dv_hi = after_dv1 as u8;
        let dv2_a = ep45_phase_add(dv1_s, EP45_DV_TO_DV_M);
        let (after_dv2, _) = ep45_random(after_dv1, dv2_a);
        (4, ((dv_hi as u16) << 8) | after_dv2 as u8 as u16, item1, item2)
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TraceState {""",
    "insert v4.5 predictor",
)

replace_once(
    """            self.endpoint.atick = current.atick;
            self.endpoint.stick = current.stick;
            self.endpoint.keys = current.keys;

            // run_frame() is executing on the top-screen present hook.""",
    """            self.endpoint.atick = current.atick;
            self.endpoint.stick = current.stick;
            self.endpoint.keys = current.keys;
            let (pred_route, pred_raw, pred_item1, pred_item2) = ep45_predict(
                self.endpoint.state,
                self.endpoint.ap4,
                self.endpoint.sp4,
            );
            self.endpoint.pred_route = pred_route;
            self.endpoint.pred_raw = pred_raw;
            self.endpoint.pred_item1 = pred_item1;
            self.endpoint.pred_item2 = pred_item2;

            // run_frame() is executing on the top-screen present hook.""",
    "compute prediction at frozen endpoint",
)

replace_once(
    "endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n",
    "endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys,pred_route,pred_raw,pred_item1,pred_item2\\n",
    "extend endpoint csv header",
)
replace_once(
    "ENDPOINT,OK,{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{:02X},{:02X},{},{},{:04X}\\n\\n",
    "ENDPOINT,OK,{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{:02X},{:02X},{},{},{:04X},{},{:04X},{:02X},{:02X}\\n\\n",
    "extend endpoint csv row",
)
replace_once(
    """                self.endpoint.atick,
                self.endpoint.stick,
                self.endpoint.keys
            );""",
    """                self.endpoint.atick,
                self.endpoint.stick,
                self.endpoint.keys,
                self.endpoint.pred_route,
                self.endpoint.pred_raw,
                self.endpoint.pred_item1,
                self.endpoint.pred_item2
            );""",
    "extend endpoint csv args",
)

replace_once(
    '                "EP44 +{} S{:04X}",',
    '                "EP45 +{} S{:04X}",',
    "screen v4.5 marker",
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
            pnp::println!(
                \"EP P R{} DV{:04X}\",
                self.endpoint.pred_route,
                self.endpoint.pred_raw
            );""",
    "show endpoint prediction",
)

path.write_text(s)
print("Applied Suicune Endpoint Predictor v4.5 PURETAIL")
