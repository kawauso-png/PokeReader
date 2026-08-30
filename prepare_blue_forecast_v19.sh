#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
CTRACE=3gx/sources/blue_dvtrace.c

if ! grep -q '^mod shiny_forecast;$' "$RUST"; then
    sed -i '1imod shiny_forecast;' "$RUST"
fi

if ! grep -q 'host_blue_forecast_append_csv' "$RUST"; then
    awk '
    { print }
    /fn host_blue_gbrelease_valid\(\) -> u32;/ {
        print "    fn host_blue_forecast_append_csv(slot: u32, valid: u32, candidates: u32, shiny: u32, phase_count: u32, next_horizon: u32, next_candidates: u32, next_shiny: u32, target_seq: u32, actual_raw: u32, actual_hit: u32) -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'shiny_forecast::observe_phase' "$RUST"; then
    awk '
    BEGIN { in_adp = 0 }
    /let _ = adaptive_model::observe\(/ { in_adp = 1 }
    { print }
    in_adp && /^[[:space:]]*\);/ {
        print "        shiny_forecast::observe_phase("
        print "            previous.seq, previous.div, current.seq, current.div, phase_usable,"
        print "        );"
        in_adp = 0
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'shiny_forecast::mark_arm' "$RUST"; then
    awk '
    /adaptive_model::mark_arm\(\);/ {
        print
        print "            shiny_forecast::mark_arm("
        print "                s.seq, s.rng, s.div, (s.rng & 0xFF) as u8, adaptive_model::stats(),"
        print "            );"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'let fc = shiny_forecast::scan' "$RUST"; then
    awk '
    /let adp = adaptive_model::stats\(\);/ {
        print
        print "        let fc = shiny_forecast::scan("
        print "            current.seq, current.rng, current.div, (current.rng & 0xFF) as u8, adp,"
        print "        );"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'FC NOW C{} S{} P{}' "$RUST"; then
    awk '
    /pnp::println!\(\"H\{\}\/\{\} M\{\}\/\{\} S\{\} D\{\}\"/ {
        print
        print "        pnp::println!(\"FC NOW C{} S{} P{}\", fc.now_candidates, fc.now_shiny, fc.phase_count);"
        print "        if fc.valid && fc.next_horizon != 0 {"
        print "            let remain = if fc.target_seq >= current.seq { fc.target_seq - current.seq } else { 0 };"
        print "            pnp::println!(color = if fc.next_shiny != 0 { YELLOW } else { WHITE }, \"NEXT +{} C{} S{}\", remain, fc.next_candidates, fc.next_shiny);"
        print "        } else {"
        print "            pnp::println!(\"NEXT --\");"
        print "        }"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'let arm_fc = shiny_forecast::arm_stats' "$RUST"; then
    awk '
    /let fixed_run_id = if state.fixed_target.is_some\(\)/ {
        print "                let arm_fc = shiny_forecast::arm_stats();"
        print "                if slot != 0 && arm_fc.valid {"
        print "                    let actual_hit = shiny_forecast::arm_contains(current.raw_dv);"
        print "                    let _ = host_blue_forecast_append_csv("
        print "                        slot, 1, arm_fc.candidates as u32, arm_fc.shiny as u32,"
        print "                        arm_fc.phase_count as u32, arm_fc.next_horizon as u32,"
        print "                        arm_fc.next_candidates as u32, arm_fc.next_shiny as u32,"
        print "                        arm_fc.target_seq, current.raw_dv as u32, u32::from(actual_hit),"
        print "                    );"
        print "                }"
        print
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE MEWTWO RNG v7.5.1 ADAPT/BLUE MEWTWO RNG v7.6.0 FCST/' "$RUST"
sed -i 's/ADAPTIVE ENVELOPE READ-ONLY/SHINY FORECAST READ-ONLY/' "$RUST"

# v7.5.1 build preparation already upgraded meta 9 -> 18.
sed -i 's/"MEWTWO,18,/"MEWTWO,19,/' "$CTRACE"
