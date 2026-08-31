#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.4.2 Articuno adaptive-model hardware fix.
#
# Live Articuno screen after a full 80-row cold window showed:
#   ADP -- B10 R00
#   H70/80 M4/4 S4 D16
#   NPC L0 R0 C80 COLD
#   BAD1 dFF s13 g0 r05
#   BAD2 dFF s13 g0 r08
#
# All non-core readiness gates are already locked. The repeated hardware class
# dFF/s13/g0 is therefore a missing ordinary transition, not an NPC reset or
# insufficient wait. Promote only this exact observed class while keeping the
# strict 80/80 cold-lock requirement unchanged.

if ! grep -q 'ARTICUNO_ADPFIX_V41' "$ADPMOD"; then
    awk '
    /\(0xFF, 0x13, 1\) \|/ {
        print
        print "        (0xFF, 0x13, 0) | // ARTICUNO_ADPFIX_V41 hardware dFF/s13/g0"
        next
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"

    awk '
    /    fn normalized_support_contains_both_observed_modes\(\) \{/ {
        print "    #[test]"
        print "    fn articuno_hardware_normal_ff_13_0_is_accepted() {"
        print "        assert!(allowed_normal(0xFF, 0x13, 0));"
        print "    }"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.4.1 ART AUTO/BLUE LEGEND RNG v8.4.2 ART ADP/' "$RUST"
sed -i 's/"LEGEND,40,/"LEGEND,41,/' "$CTRACE"

grep -q 'ARTICUNO_ADPFIX_V41' "$ADPMOD"
grep -q 'articuno_hardware_normal_ff_13_0_is_accepted' "$ADPMOD"
grep -q 'BLUE LEGEND RNG v8.4.2 ART ADP' "$RUST"
grep -q '"LEGEND,41,' "$CTRACE"
