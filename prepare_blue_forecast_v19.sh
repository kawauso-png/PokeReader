#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
CTRACE=3gx/sources/blue_dvtrace.c
FCMOD=reader_core/src/gen1/shiny_forecast.rs

if ! grep -q '^mod shiny_forecast;$' "$RUST"; then
    sed -i '1imod shiny_forecast;' "$RUST"
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

# scan_full leaves RAW_BITS at its final +16F evaluation. Re-evaluate the
# current trigger state before snapshotting ARM_BITS so the arm snapshot is NOW.
if ! grep -q 'let arm_n = seed_current' "$FCMOD"; then
    awk '
    /for i in 0\.\.RAW_WORDS \{ ARM_BITS\[i\] = RAW_BITS\[i\]; \}/ {
        print "        let arm_n = seed_current(rng, div, frame);"
        print "        let _ = evaluate_states(arm_n);"
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# AutoPause candidate mode only wants compact sets. The scanner therefore
# skips shiny-containing horizons wider than 8 raw-DV candidates and keeps
# searching farther ahead within the 16F horizon.
sed -i 's/out.next_horizon == 0 && e.1 != 0 {/out.next_horizon == 0 \&\& e.1 != 0 \&\& e.0 <= 8 {/' "$FCMOD"

sed -i 's/BLUE MEWTWO RNG v7.5.1 ADAPT/BLUE MEWTWO RNG v7.6.0 FCST/' "$RUST"
sed -i 's/ADAPTIVE ENVELOPE READ-ONLY/SHINY FORECAST READ-ONLY/' "$RUST"

# v7.5.1 build preparation already upgraded meta 9 -> 18.
sed -i 's/"MEWTWO,18,/"MEWTWO,19,/' "$CTRACE"
