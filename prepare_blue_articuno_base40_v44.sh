#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.4.5 Articuno cold base-dominance fix.
#
# Hardware v43 reached:
#   ADP -- B10 R02
#   H80/80 M4/4 S4 D16
#   KOBS ... M10 45%
# with no BAD rows. The selected adaptive base (B10) agrees with the global
# K-observer mode (M10), all 80 rows classify, all 20F markers agree, and DIV
# phase is fully locked. The remaining old Moltres cold gate was base_hits>=56
# (70%), which is too strict for Articuno's legitimate B-1/B/B+1 distribution.
#
# Keep every structural gate intact and lower only Articuno cold base dominance
# to 32/80 (40%). Also expose BH on screen so this hidden gate is observable.

if ! grep -q 'ARTICUNO_COLD_BASE_MIN' "$ADPMOD"; then
    sed -i '/const DIV_WIN: usize = 16;/a\const ARTICUNO_COLD_BASE_MIN: u8 = 32; // ARTICUNO_BASE40_V44' "$ADPMOD"
    sed -i 's/base_hits >= 56/base_hits >= ARTICUNO_COLD_BASE_MIN/' "$ADPMOD"
fi

# Expose the previously hidden base-hit gate in the live overlay.
if ! grep -q 'BH{}' "$RUST"; then
    sed -i 's/"ADP {} B{:02X} R{:02}"/"ADP {} B{:02X} BH{} R{:02}"/' "$RUST"
    sed -i 's/adp.base, adp.residue20);/adp.base, adp.base_hits, adp.residue20);/' "$RUST"
fi

# Regression checks: do not weaken the actual transition, marker, or DIV gates.
if ! grep -q 'articuno_cold_base_threshold_is_40_percent' "$ADPMOD"; then
    awk '
    /    fn normalized_support_contains_both_observed_modes\(\) \{/ {
        print "    #[test]"
        print "    fn articuno_cold_base_threshold_is_40_percent() {"
        print "        assert_eq!(ARTICUNO_COLD_BASE_MIN, 32);"
        print "        assert_eq!(WIN, 80);"
        print "    }"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.4.4 ART COLD2/BLUE LEGEND RNG v8.4.5 ART BASE40/' "$RUST"
sed -i 's/"LEGEND,43,/"LEGEND,44,/' "$CTRACE"

grep -q 'ARTICUNO_COLD_BASE_MIN: u8 = 32' "$ADPMOD"
grep -q 'base_hits >= ARTICUNO_COLD_BASE_MIN' "$ADPMOD"
grep -q 'articuno_cold_base_threshold_is_40_percent' "$ADPMOD"
grep -q 'ADP {} B{:02X} BH{} R{:02}' "$RUST"
grep -q 'BLUE LEGEND RNG v8.4.5 ART BASE40' "$RUST"
grep -q '"LEGEND,44,' "$CTRACE"
