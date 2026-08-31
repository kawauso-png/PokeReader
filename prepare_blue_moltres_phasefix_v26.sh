#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
PHTMOD=reader_core/src/gen1/phase_tracker.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.1 Moltres phase-liveness fix.
# The host hook may sample the same GB seq more than once. A duplicate host
# sample is not a new GB frame and must not clear any learned phase/adaptive
# state. v8.2 cleared on seq==prev_seq, which can leave FC NOW C0 S0 P0 and
# prevent AutoPause even though the game is otherwise running normally.

# Forecast phase mask: keep an already-established family across duplicate seq.
if ! grep -q 'v8.2.1 duplicate-seq hold' "$FCMOD"; then
    awk '
    /pub fn observe_phase\(prev_seq:/ { in_observe = 1 }
    {
        print
        if (in_observe && $0 ~ /^[[:space:]]*unsafe \{/) {
            print "        // v8.2.1 duplicate-seq hold: host resampling the same GB frame"
            print "        // must not destroy an already-established phase family."
            print "        if usable && prev_seq != 0 && seq == prev_seq && PHASE_LAST_SEQ == seq {"
            print "            return;"
            print "        }"
            in_observe = 0
        }
    }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Adaptive model: preserve READY/window state on a duplicate sample.
if ! grep -q 'v8.2.1 duplicate-seq hold' "$ADPMOD"; then
    awk '
    /pub fn observe\(prev_seq:/ { in_observe = 1 }
    {
        print
        if (in_observe && $0 ~ /^[[:space:]]*unsafe \{/) {
            print "        // v8.2.1 duplicate-seq hold."
            print "        if usable && prev_seq != 0 && seq == prev_seq && LAST_SEQ == seq {"
            print "            return LIVE;"
            print "        }"
            in_observe = 0
        }
    }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

# Legacy phase tracker is diagnostic/CSV support, but keep it coherent too.
if ! grep -q 'v8.2.1 duplicate-seq hold' "$PHTMOD"; then
    awk '
    /fn observe\(&mut self, prev_seq:/ { in_observe = 1 }
    {
        print
        if (in_observe && $0 ~ /^[[:space:]]*if !usable \{/) {
            print "        // v8.2.1 duplicate-seq hold."
            print "        if usable && prev_seq != 0 && seq == prev_seq && self.last_seq == seq {"
            print "            return self.stats();"
            print "        }"
            in_observe = 0
        }
    }
    ' "$PHTMOD" > "$PHTMOD.tmp"
    mv "$PHTMOD.tmp" "$PHTMOD"
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
