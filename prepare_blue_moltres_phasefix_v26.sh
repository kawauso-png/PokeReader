#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.1 Moltres phase-liveness fix.
# On hardware, the host hook may sample the same GB seq more than once.
# v8.2 treated seq==prev_seq as a continuity failure and cleared PHASE_MASK,
# which can leave the overlay at FC NOW C0 S0 P0 and prevent AutoPause.
# A duplicate sample contains no new GB-frame transition, so preserve the
# already-learned phase family and wait for the next real seq increment.
if ! grep -q 'v8.2.1 duplicate-seq hold' "$FCMOD"; then
    awk '
    /pub fn observe_phase\(prev_seq:/ { in_observe = 1 }
    {
        print
        if (in_observe && $0 ~ /^[[:space:]]*unsafe \{/) {
            print "        // v8.2.1 duplicate-seq hold: host resampling the same GB frame"
            print "        // must not destroy a valid phase family."
            print "        if usable && prev_seq != 0 && seq == prev_seq {"
            print "            PHASE_LAST_SEQ = seq;"
            print "            return;"
            print "        }"
            in_observe = 0
        }
    }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Moltres' first calibrated profile produces a wider NOW envelope than Mewtwo.
# Do not silently discard shiny-containing Moltres states merely because C>12.
# Zapdos keeps its validated cap20; Mewtwo remains at the original cap12.
sed -i 's/if LEGEND_TARGET_ID == 1 { 20 } else { MAX_NOW_CANDIDATES }/if LEGEND_TARGET_ID == 1 { 20 } else if LEGEND_TARGET_ID == 3 { 24 } else { MAX_NOW_CANDIDATES }/' "$AUTOMOD"

if ! grep -q 'MOLTRES P-HOLD CAP24' "$RUST"; then
    sed -i '/MOLTRES AUTO EXP/a\        if legend_target == 3 { pnp::println!(color = YELLOW, "MOLTRES P-HOLD CAP24"); }' "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.2 MOL/BLUE LEGEND RNG v8.2.1 PFX/' "$RUST"
sed -i 's/ZAP+MOLTRES AUTO EXP/MOLTRES PHASEFIX AUTO/' "$RUST"
sed -i 's/"LEGEND,25,/"LEGEND,26,/' "$CTRACE"
