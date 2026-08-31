#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
MAIN=3gx/sources/main.c
CTRACE=3gx/sources/blue_dvtrace.c

# v8.4.1 Articuno Auto Hunt.
# Hardware calibration: legend_trace_0016, Exact2F arm_source=2.
#
# Measured anchors:
#   trigger 1109 -> PRE 1120 = 11F
#   trigger 1109 -> DV  1121 = 12F
#   GB release 1112 -> DV 1121 = 9F
#   trigger ADD/DIV 51/DD -> PRE 95/A7 -> DV ADD/DIV 63/B9
#   raw DV 6360, microphase=91, add2_match=1
#
# The 11 trigger->PRE transitions reconstruct the event K sequence exactly:
#   1A 1A 1D 19 1A 16 1B 15 1A 16 0F
# With the trace DIV phase family (p0=49), that sequence is reproduced by the
# existing Mewtwo primary offsets plus these Articuno-specific M-cycle deltas:
#   rel 1,2,5..11: +0x80; rel3: +0x140; rel4: +0x40.
# This is therefore a distinct 11F Articuno event path, not a blind Zapdos or
# Moltres timing reuse.
#
# On the final BattleRandom frame, raw 6360 is covered by the ordinary Mewtwo
# timing formula with a +90..+94 M-cycle common envelope. This also matches the
# already-observed hardware microphase classes 90/91/94.

# v8.4 calibration build deliberately suppressed target-2 forecasts. Remove
# only those two injected guard blocks; Exact2F/trace plumbing stays unchanged.
if grep -q 'ARTICUNO_CAL_FORECAST_LOCK' "$FCMOD"; then
    sed -i '/ARTICUNO_CAL_FORECAST_LOCK: no prediction before hardware calibration\./,/^[[:space:]]*}/d' "$FCMOD"
    sed -i '/ARTICUNO_CAL_FORECAST_LOCK: keep Exact2F trace, discard false arm forecast\./,/^[[:space:]]*}/d' "$FCMOD"
fi

if ! grep -q 'ARTICUNO_AUTO_MODEL_V40' "$FCMOD"; then
    # Target-2 BattleRandom timing envelope. v24 already made target 1 select
    # Zapdos-specific constants; insert Articuno as the next branch.
    sed -i '/(2747u16, 2822u16, 6355u16, 6418u16)/a\    } else if target == 2 {\
        // ARTICUNO_AUTO_MODEL_V40: trace 0016 common timing +90..+94 M.\
        (2143u16, 2165u16, 5751u16, 5761u16)' "$FCMOD"

    # Insert the calibrated Articuno event path immediately before collect_event.
    awk '
    /unsafe fn collect_event\(add: u8, div: u8, phase: u8, frame: u8,/ {
        print "fn articuno_event_offset(rel: u8) -> u16 {"
        print "    let extra = match rel {"
        print "        3 => 0x140u16,"
        print "        4 => 0x040u16,"
        print "        _ => 0x080u16,"
        print "    };"
        print "    primary_offset(rel).wrapping_add(extra)"
        print "}"
        print ""
        print "fn run_articuno_event_path(mut add: u8, mut div: u8, p0: u8) -> (u8, u8, u8) {"
        print "    let mut p = p0;"
        print "    for rel in 1u8..=11u8 {"
        print "        let step = phase_step(p);"
        print "        let pc = phase_next(p);"
        print "        let k = (((pc as u16) + articuno_event_offset(rel)) / 64) as u8;"
        print "        let v = step_add(add, div, k, step);"
        print "        add = v.0;"
        print "        div = v.1;"
        print "        p = pc;"
        print "    }"
        print "    (add, div, p)"
        print "}"
        print ""
        print "unsafe fn collect_articuno_event(add: u8, div: u8, phase: u8,"
        print "                                 count: &mut u16, shiny_count: &mut u8) {"
        print "    // Keep the same measured host-sampling phase support used by the"
        print "    // validated 11F event family: aligned, -4 M, and -8 M."
        print "    for jump in [0u8, 60u8, 56u8] {"
        print "        let p0 = phase.wrapping_add(jump) & 0x3F;"
        print "        let pre = run_articuno_event_path(add, div, p0);"
        print "        collect_battle(pre.0, pre.1, pre.2, count, shiny_count);"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"

    # Divert target 2 to the new 11F path before the Moltres target-3 branch.
    awk '
    /unsafe fn collect_event\(add: u8, div: u8, phase: u8, frame: u8,/ {
        print
        in_event_sig = 1
        next
    }
    in_event_sig {
        print
        print "    if LEGEND_TARGET_ID == 2 {"
        print "        collect_articuno_event(add, div, phase, count, shiny_count);"
        print "        return;"
        print "    }"
        in_event_sig = 0
        next
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"

    # Regression test from the actual hardware trace. Validate both the exact
    # reconstructed K sequence/PRE state and that the timing envelope contains
    # raw DV 6360.
    cat >> "$FCMOD" <<'EOF'

#[cfg(test)]
mod articuno_trace0016_tests {
    use super::*;

    #[test]
    fn articuno_trace0016_path_and_raw_are_covered() {
        let mut p = 49u8;
        let mut got = [0u8; 11];
        for rel in 1u8..=11u8 {
            let pc = phase_next(p);
            got[(rel - 1) as usize] =
                (((pc as u16) + articuno_event_offset(rel)) / 64) as u8;
            p = pc;
        }
        assert_eq!(got, [0x1A, 0x1A, 0x1D, 0x19, 0x1A, 0x16, 0x1B, 0x15, 0x1A, 0x16, 0x0F]);

        let pre = run_articuno_event_path(0x51, 0xDD, 49);
        assert_eq!(pre, (0x95, 0xA7, 13));

        // One endpoint pair inside the +90..+94 envelope yields the observed
        // raw 6360; collect_battle enumerates this qv/tb combination.
        let qv = ((pre.2 as u16 + 2165) / 64) as u8;
        let qb1 = ((pre.2 as u16 + 5751) / 64) as u8;
        let qb2 = ((pre.2 as u16 + 5751 + 120) / 64) as u8;
        let low = pre.0
            .wrapping_add(pre.1.wrapping_add(qv))
            .wrapping_add(pre.1.wrapping_add(qb1))
            .wrapping_add(1);
        let high = low.wrapping_add(pre.1.wrapping_add(qb2)).wrapping_add(1);
        assert_eq!(((high as u16) << 8) | low as u16, 0x6360);
    }
}
EOF
fi

# Enable target 2 in the paused Y+X Auto Hunt gate. All four table entries are
# now backed by a hardware-calibrated event model.
sed -i 's/(host_blue_legend_target_id() <= 1u || host_blue_legend_target_id() == 3u)/host_blue_legend_target_id() <= 3u/g' "$MAIN"

# Disable the two old target-2 calibration-only UI guards once, then add an
# explicit Articuno Auto status line. The marker prevents a second prepare pass
# from rewriting the newly inserted target-2 line.
if ! grep -q 'ARTICUNO_AUTO_UI_V40' "$RUST"; then
    sed -i 's/if legend_target == 2 {/if legend_target == 255 {/g' "$RUST"
    sed -i '/MOLTRES AUTO EXP/a\        if legend_target == 2 { pnp::println!(color = YELLOW, "ARTICUNO AUTO 11F/9F"); } // ARTICUNO_AUTO_UI_V40' "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.4 ART CAL/BLUE LEGEND RNG v8.4.1 ART AUTO/' "$RUST"
sed -i 's/ARTICUNO CAL + VCRST/ARTICUNO AUTO + VCRST/' "$RUST"
sed -i 's/"LEGEND,39,/"LEGEND,40,/' "$CTRACE"

# Build-time guards.
grep -q 'ARTICUNO_AUTO_MODEL_V40' "$FCMOD"
grep -q 'collect_articuno_event' "$FCMOD"
grep -q 'articuno_trace0016_path_and_raw_are_covered' "$FCMOD"
! grep -q 'ARTICUNO_CAL_FORECAST_LOCK' "$FCMOD"
grep -q 'host_blue_legend_target_id() <= 3u' "$MAIN"
grep -q 'ARTICUNO_AUTO_UI_V40' "$RUST"
grep -q 'BLUE LEGEND RNG v8.4.1 ART AUTO' "$RUST"
grep -q '"LEGEND,40,' "$CTRACE"
