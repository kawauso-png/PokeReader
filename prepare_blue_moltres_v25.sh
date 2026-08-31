#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
MAIN=3gx/sources/main.c
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2 Moltres experimental Auto Hunt.
# legend_trace_0008 (Exact2F arm_source=2) established:
# - trigger 1263, GB release 1266, PRE 1280, DV write 1281
# - release -> DV = 15F, trigger -> PRE = 17F
# - trigger ADD/DIV BE/CF -> PRE ADD/DIV 00/06
# - actual raw DV 19A7, BattleRandom consistency add2_match=1
#
# Unlike Mewtwo/Zapdos, Moltres is not represented as an 11F shifted event.
# Model the calibrated 17F event as an affine PRE transform. The normal 17F
# DIV phase progression supplies the cumulative DIV contribution; the measured
# event Random-call K sum is 658. A small -3..+1 correction envelope covers the
# one-frame sampling displacement seen in the calibration while keeping the
# NOW candidate set <=12 in the calibrated state family.

if ! grep -q 'collect_battle_moltres' "$FCMOD"; then
    awk '
    /unsafe fn collect_event\(add: u8, div: u8, phase: u8, frame: u8,/ {
        print "unsafe fn collect_battle_moltres(add: u8, div: u8, p: u8, count: &mut u16, shiny_count: &mut u8) {"
        print "    // Trace 0008 is consistent with the common DV-frame routine at"
        print "    // approximately the Mewtwo timing +0x400 M-cycles. Keep the"
        print "    // narrow calibrated envelope for the first hardware validation."
        print "    let qv_lo = ((p as u16 + 3077) / 64) as u8;"
        print "    let qv_hi = ((p as u16 + 3095) / 64) as u8;"
        print "    let mut qv = qv_lo;"
        print "    loop {"
        print "        let mut tb = 6685u16;"
        print "        while tb <= 6691 {"
        print "            let qb1 = ((p as u16 + tb) / 64) as u8;"
        print "            let qb2 = ((p as u16 + tb + 120) / 64) as u8;"
        print "            let rv = div.wrapping_add(qv);"
        print "            let rb1 = div.wrapping_add(qb1);"
        print "            let rb2 = div.wrapping_add(qb2);"
        print "            let low = add.wrapping_add(rv).wrapping_add(rb1).wrapping_add(1);"
        print "            let high = low.wrapping_add(rb2).wrapping_add(1);"
        print "            raw_insert(((high as u16) << 8) | low as u16, count, shiny_count);"
        print "            tb += 1;"
        print "        }"
        print "        if qv == qv_hi { break; }"
        print "        qv = qv.wrapping_add(1);"
        print "    }"
        print "}"
        print ""
        print "unsafe fn collect_moltres_event(add: u8, div: u8, phase: u8, count: &mut u16, shiny_count: &mut u8) {"
        print "    let mut p = phase;"
        print "    let mut cumulative_ticks = 0u16;"
        print "    let mut cumulative_sum = 0u16;"
        print "    for _ in 0..17 {"
        print "        let step = phase_step(p) as u16;"
        print "        cumulative_ticks = cumulative_ticks.wrapping_add(step);"
        print "        cumulative_sum = cumulative_sum.wrapping_add(cumulative_ticks);"
        print "        p = phase_next(p);"
        print "    }"
        print "    let pre_div = div.wrapping_add(cumulative_ticks as u8);"
        print "    let base_c = cumulative_sum.wrapping_add(658) as u8;"
        print "    for corr in [253u8, 254u8, 255u8, 0u8, 1u8] { // -3,-2,-1,0,+1"
        print "        let pre_add = add"
        print "            .wrapping_add(div.wrapping_mul(17))"
        print "            .wrapping_add(base_c)"
        print "            .wrapping_add(corr);"
        print "        collect_battle_moltres(pre_add, pre_div, p, count, shiny_count);"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Divert only Moltres to its 17F profile; Mewtwo and the validated Zapdos path
# remain byte-for-byte on their existing forecast paths. collect_event has a
# two-line signature, so insert after the second signature line.
if ! grep -q 'LEGEND_TARGET_ID == 3' "$FCMOD"; then
    awk '
    /unsafe fn collect_event\(add: u8, div: u8, phase: u8, frame: u8,/ {
        print
        in_event_sig = 1
        next
    }
    in_event_sig {
        print
        print "    if LEGEND_TARGET_ID == 3 {"
        print "        collect_moltres_event(add, div, phase, count, shiny_count);"
        print "        return;"
        print "    }"
        in_event_sig = 0
        next
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Enable Y+X Auto Hunt for Mewtwo, Zapdos and Moltres. Articuno remains locked
# until its own calibration arrives.
sed -i 's/host_blue_legend_target_id() <= 1u/(host_blue_legend_target_id() <= 1u || host_blue_legend_target_id() == 3u)/g' "$MAIN"
sed -i 's/if legend_target >= 2 {/if legend_target == 2 {/' "$RUST"

if ! grep -q 'MOLTRES AUTO EXP' "$RUST"; then
    sed -i '/ZAPDOS AUTO EXP/a\        if legend_target == 3 { pnp::println!(color = YELLOW, "MOLTRES AUTO EXP"); }' "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.1 ZAP/BLUE LEGEND RNG v8.2 MOL/' "$RUST"
sed -i 's/ZAPDOS AUTO EXPERIMENT/ZAP+MOLTRES AUTO EXP/' "$RUST"
sed -i 's/"LEGEND,24,/"LEGEND,25,/' "$CTRACE"
