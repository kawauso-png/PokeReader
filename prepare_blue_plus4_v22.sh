#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# Traces 0048/0049 proved that the Exact2F event-side sample can also land
# +4 M-cycles from the normal-frame phase family.  v7.7.1 covered only
# 0/-4/-8, which made those actual DVs fall outside the forecast envelope.
# Keep the existing branches and add +4 conservatively.
sed -i 's/for jump in \[0u8, 60u8, 56u8\] { \/\/ 0, -4, -8 mod 64/for jump in [0u8, 60u8, 56u8, 4u8] { \/\/ 0, -4, -8, +4 mod 64/' "$FCMOD"

# After DVs exist, show whether the Exact2F arm snapshot actually contained the
# generated raw DV. This is post-generation diagnostics only and never affects
# pause/input behavior.
if ! grep -q 'FC ARM C{} S{} {}' "$RUST"; then
    awk '
    /let shiny = shiny_from_raw\(result\.battle\.raw_dv\);/ {
        print
        print "            let arm_fc = shiny_forecast::arm_stats();"
        print "            let arm_hit = shiny_forecast::arm_contains(result.battle.raw_dv);"
        print "            if arm_fc.valid {"
        print "                pnp::println!(color = if arm_hit { GREEN } else { RED }, \"FC ARM C{} S{} {}\", arm_fc.candidates, arm_fc.shiny, if arm_hit { \"HIT\" } else { \"MISS\" });"
        print "            }"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE MEWTWO RNG v7.7.1 NOW/BLUE MEWTWO RNG v7.7.2 +4/' "$RUST"
sed -i 's/AUTOPAUSE NOW MODE/AUTOPAUSE +4 ENVELOPE/' "$RUST"
sed -i 's/"MEWTWO,21,/"MEWTWO,22,/' "$CTRACE"
