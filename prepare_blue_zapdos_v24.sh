#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
MAIN=3gx/sources/main.c
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.1 Zapdos experimental Auto Hunt.
# legend_trace_0001 established:
# - Exact2F GB release -> DV remains 9F.
# - rel1..11 event K sequence is reproduced by the Mewtwo offsets +0x300 M-cycles.
# - PRE is 6F/51 and actual raw DV 5AA2 is covered when the final DV-frame
#   timing is widened by the common-shift interval inferred from d2: 694..751 M.

if ! grep -q 'LEGEND_TARGET_ID' "$FCMOD"; then
    awk '
    { print }
    /static mut ARM_BITS:/ {
        print "static mut LEGEND_TARGET_ID: u8 = 0;"
        print "pub fn set_legend_target(id: u32) { unsafe { LEGEND_TARGET_ID = id as u8; } }"
        print "fn legend_event_shift() -> u16 { unsafe { if LEGEND_TARGET_ID == 1 { 0x300 } else { 0 } } }"
    }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

sed -i 's/let off = if rel == anomaly { anomaly_offset(rel) } else { primary_offset(rel) };/let off = (if rel == anomaly { anomaly_offset(rel) } else { primary_offset(rel) }).wrapping_add(legend_event_shift());/' "$FCMOD"

if ! grep -q 'ZAPDOS DV timing envelope' "$FCMOD"; then
    sed -i '/unsafe fn collect_battle(add: u8, div: u8, p: u8, count: &mut u16, shiny_count: &mut u8) {/a\    // ZAPDOS DV timing envelope: trace 0001 common-shift support 694..751 M.\
    let target = unsafe { LEGEND_TARGET_ID };\
    let (tv_lo, tv_hi, tb_lo, tb_hi) = if target == 1 {\
        (2747u16, 2822u16, 6355u16, 6418u16)\
    } else {\
        (2053u16, 2071u16, 5661u16, 5667u16)\
    };' "$FCMOD"
    sed -i 's/let qv_lo = ((p as u16 + 2053) \/ 64) as u8;/let qv_lo = ((p as u16 + tv_lo) \/ 64) as u8;/' "$FCMOD"
    sed -i 's/let qv_hi = ((p as u16 + 2071) \/ 64) as u8;/let qv_hi = ((p as u16 + tv_hi) \/ 64) as u8;/' "$FCMOD"
    sed -i 's/let mut tb = 5661u16;/let mut tb = tb_lo;/' "$FCMOD"
    sed -i 's/while tb <= 5667 {/while tb <= tb_hi {/' "$FCMOD"
fi

if ! grep -q 'shiny_forecast::set_legend_target(legend_target)' "$RUST"; then
    sed -i '/let legend_target = unsafe { host_blue_legend_target_id() };/a\    shiny_forecast::set_legend_target(legend_target);\
    autopause::set_legend_target(legend_target);' "$RUST"
fi

if ! grep -q 'pub fn set_legend_target' "$AUTOMOD"; then
    sed -i '/const MAX_NOW_CANDIDATES: u16 = 12;/a\static mut LEGEND_TARGET_ID: u8 = 0;\
pub fn set_legend_target(id: u32) { unsafe { LEGEND_TARGET_ID = id as u8; } }\
fn max_now_candidates() -> u16 { unsafe { if LEGEND_TARGET_ID == 1 { 20 } else { MAX_NOW_CANDIDATES } } }' "$AUTOMOD"
fi
sed -i 's/fc.now_candidates <= MAX_NOW_CANDIDATES/fc.now_candidates <= max_now_candidates()/' "$AUTOMOD"

sed -i 's/host_blue_legend_target_id() == 0u/host_blue_legend_target_id() <= 1u/g' "$MAIN"
sed -i 's/if legend_target != 0 {/if legend_target >= 2 {/' "$RUST"
if ! grep -q 'ZAPDOS AUTO EXP' "$RUST"; then
    sed -i '/pnp::println!(color = BLUE, "TARGET {}  <\/>@PAUSE", legend_name);/a\        if legend_target == 1 { pnp::println!(color = YELLOW, "ZAPDOS AUTO EXP"); }' "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.0 CAL/BLUE LEGEND RNG v8.1 ZAP/' "$RUST"
sed -i 's/4-LEGEND CALIBRATION/ZAPDOS AUTO EXPERIMENT/' "$RUST"
sed -i 's/"LEGEND,23,/"LEGEND,24,/' "$CTRACE"
