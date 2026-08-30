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


# Store the endpoint-only prediction next to the captured state.  v4.3 does
# not use any Target->DV long-range model: it starts solely from DV-2.
replace_once(
    "    pub keys: u16,\n}",
    """    pub keys: u16,
    pub pred_route: u8,
    pub pred_raw: u16,
    pub pred_item1: u8,
    pub pred_item2: u8,
}""",
    "endpoint prediction fields",
)

# The divider phase representation is rDIV*64 + mcycle (mod 16384).
# Constants below are measured/derived in M-cycles after LIGHTTAIL removes the
# heavy Deep snapshot from the final burst:
#   final VBlank A->first Random A = 11752 (equiv. S->A = 11741)
#   each Random first->second rDIV read = 11
#   route3 item1 S->DV1 A = 369
#   consecutive DV call S->next A = 108
#   route4 item1 S->item2 A = 113
#   route4 item2 S->DV1 A = 371, or 374 when Item2 is selected (<0x14)
replace_once(
    "#[derive(Clone, Copy, PartialEq, Eq)]\npub enum TraceState {",
    """const EP43_FRAME_M: u16 = 1172;
const EP43_VBLANK_A_TO_RANDOM_A: u16 = 11752;
const EP43_RANDOM_PAIR_M: u16 = 11;
const EP43_ROUTE3_ITEM_TO_DV1_M: u16 = 369;
const EP43_DV_TO_DV_M: u16 = 108;
const EP43_ROUTE4_ITEM1_TO_ITEM2_M: u16 = 113;
const EP43_ROUTE4_ITEM2_TO_DV1_COMMON_M: u16 = 371;
const EP43_ROUTE4_ITEM2_EXTRA_M: u16 = 3;

fn ep43_phase_add(phase: u16, delta: u16) -> u16 {
    phase.wrapping_add(delta) & 0x3fff
}

fn ep43_div(phase: u16) -> u8 {
    (phase >> 6) as u8
}

fn ep43_update(state: u16, adiv: u8, sdiv: u8) -> u16 {
    let add = (state >> 8) as u8;
    let sub = state as u8;
    let (new_add, carry) = add.overflowing_add(adiv);
    let new_sub = sub.wrapping_sub(sdiv).wrapping_sub(carry as u8);
    ((new_add as u16) << 8) | new_sub as u16
}

fn ep43_random(state: u16, aphase: u16) -> (u16, u16) {
    let sphase = ep43_phase_add(aphase, EP43_RANDOM_PAIR_M);
    let next = ep43_update(state, ep43_div(aphase), ep43_div(sphase));
    (next, sphase)
}

fn ep43_predict(mut state: u16, mut ap4: u16, mut sp4: u16) -> (u8, u16, u8, u8) {
    // Endpoint is DV-2. Advance exactly two ordinary VBlank RNG updates.
    for _ in 0..2 {
        ap4 = ep43_phase_add(ap4, EP43_FRAME_M);
        sp4 = ep43_phase_add(sp4, EP43_FRAME_M);
        state = ep43_update(state, ep43_div(ap4), ep43_div(sp4));
    }

    // First held-item RNG call.  The A read is 11752 M-cycles after the final
    // VBlank A read; the paired S read follows 11 M-cycles later.
    let item1_a = ep43_phase_add(ap4, EP43_VBLANK_A_TO_RANDOM_A);
    let (after_item1, item1_s) = ep43_random(state, item1_a);
    let item1 = after_item1 as u8;

    if item1 < 0xc0 {
        // No held item: item1 + DV1 + DV2 = three calls total.
        let dv1_a = ep43_phase_add(item1_s, EP43_ROUTE3_ITEM_TO_DV1_M);
        let (after_dv1, dv1_s) = ep43_random(after_item1, dv1_a);
        let dv_hi = after_dv1 as u8;
        let dv2_a = ep43_phase_add(dv1_s, EP43_DV_TO_DV_M);
        let (after_dv2, _) = ep43_random(after_dv1, dv2_a);
        let raw = ((dv_hi as u16) << 8) | after_dv2 as u8 as u16;
        (3, raw, item1, 0)
    } else {
        // Held-item branch: a second item RNG precedes the two DV calls.
        let item2_a = ep43_phase_add(item1_s, EP43_ROUTE4_ITEM1_TO_ITEM2_M);
        let (after_item2, item2_s) = ep43_random(after_item1, item2_a);
        let item2 = after_item2 as u8;
        let extra = if item2 < 0x14 { EP43_ROUTE4_ITEM2_EXTRA_M } else { 0 };
        let dv1_a = ep43_phase_add(
            item2_s,
            EP43_ROUTE4_ITEM2_TO_DV1_COMMON_M + extra,
        );
        let (after_dv1, dv1_s) = ep43_random(after_item2, dv1_a);
        let dv_hi = after_dv1 as u8;
        let dv2_a = ep43_phase_add(dv1_s, EP43_DV_TO_DV_M);
        let (after_dv2, _) = ep43_random(after_dv1, dv2_a);
        let raw = ((dv_hi as u16) << 8) | after_dv2 as u8 as u16;
        (4, raw, item1, item2)
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TraceState {""",
    "endpoint prediction functions",
)

# Calculate immediately from the frozen DV-2 snapshot, before resume can
# change any game state.
replace_once(
    """            self.endpoint.keys = current.keys;

            // run_frame() is executing on the top-screen present hook.""",
    """            self.endpoint.keys = current.keys;
            let (pred_route, pred_raw, pred_item1, pred_item2) = ep43_predict(
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

# Append prediction fields to the endpoint CSV row. Existing frame/call
# sections are unchanged.
replace_once(
    "endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n",
    "endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys,pred_route,pred_raw,pred_item1,pred_item2\\n",
    "endpoint csv header",
)
replace_once(
    "ENDPOINT,OK,{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{:02X},{:02X},{},{},{:04X}\\n\\n",
    "ENDPOINT,OK,{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X},{:02X},{:02X},{},{},{:04X},{},{:04X},{:02X},{:02X}\\n\\n",
    "endpoint csv row",
)
replace_once(
    """                self.endpoint.stick,
                self.endpoint.keys
            );""",
    """                self.endpoint.stick,
                self.endpoint.keys,
                self.endpoint.pred_route,
                self.endpoint.pred_raw,
                self.endpoint.pred_item1,
                self.endpoint.pred_item2
            );""",
    "endpoint csv args",
)

# Distinguish predictor build and show the value while frozen at DV-2.
replace_once(
    '                "EP42 +{} S{:04X}",',
    '                "EP43 +{} S{:04X}",',
    "screen build marker",
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
                \"EP R{} DV{:04X}\",
                self.endpoint.pred_route,
                self.endpoint.pred_raw
            );""",
    "screen predicted raw",
)

path.write_text(s)
print("Applied Suicune Endpoint Predictor v4.3")
