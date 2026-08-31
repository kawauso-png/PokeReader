#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.4: promote the two reproducible r00* bad rows seen on hardware into the
# special-20F transition model. Two independent live captures both showed:
#   d03 s12 g1 r00*
#   d04 s12 g0 r00*
# while all other readiness gates were locked (S4 D16, marker hits complete).
# Keep READY at 80/80; only add these exact observed transition classes.

if ! grep -q '(0x04, 0x12, 0)' "$ADPMOD"; then
    awk '
    /\(0x03, 0x12, 0\) \|/ {
        print
        print "        (0x03, 0x12, 1) |"
        next
    }
    /\(0x03, 0x13, 0\)\)/ {
        print "        (0x03, 0x13, 0) |"
        print "        (0x04, 0x12, 0))"
        next
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

# Add regression assertions so later model edits cannot silently drop either
# hardware-observed special transition.
if ! grep -q 'hardware_special_rows_r00' "$ADPMOD"; then
    awk '
    /    fn ready_threshold_requires_full_clean_window\(\) \{/ {
        print "    #[test]"
        print "    fn hardware_special_rows_r00_are_accepted() {"
        print "        assert!(allowed_special(0x03, 0x12, 1));"
        print "        assert!(allowed_special(0x04, 0x12, 0));"
        print "    }"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.2.3 BADROW/BLUE LEGEND RNG v8.2.4 SPFIX/' "$RUST"
sed -i 's/ADAPT BADROW DIAG/ADAPT SPECIAL FIX/' "$RUST"
sed -i 's/"LEGEND,28,/"LEGEND,29,/' "$CTRACE"
