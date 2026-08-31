#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.3.4 Moltres NOW-frame fix.
# Hardware showed FC NOW C0/S0/P4 with MOL age A frozen. The forecast phase mask
# was healthy (P4), but scan_full rejected the entire CURRENT evaluation whenever
# hFrameCounter was outside the legacy 1..=5 cycle. Moltres' dedicated 17F event
# path does not use hFrameCounter at all, so that guard must apply only to future
# +1/+2 propagation, not to the NOW candidate set.

if ! grep -q 'fn now_frame_usable_for' "$FCMOD"; then
    awk '
    /fn next_frame\(frame: u8\) -> u8 \{/ { in_nf = 1 }
    {
        print
        if (in_nf && $0 ~ /^}/) {
            print ""
            print "fn now_frame_usable_for(target: u8, frame: u8) -> bool {"
            print "    target == 3 || next_frame(frame) != 0"
            print "}"
            print "fn now_frame_usable(frame: u8) -> bool {"
            print "    unsafe { now_frame_usable_for(LEGEND_TARGET_ID, frame) }"
            print "}"
            in_nf = 0
        }
    }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Do not reject Moltres NOW merely because hFrameCounter is outside 1..=5.
sed -i 's/if !adp.ready || phase_count == 0 || next_frame(frame) == 0 { return out; }/if !adp.ready || phase_count == 0 || !now_frame_usable(frame) { return out; }/' "$FCMOD"

# NOW has been fully evaluated at this point. Mark it valid immediately. If the
# legacy frame counter cannot be propagated, simply omit NEXT +1/+2; AutoPause
# intentionally uses NOW only.
if ! grep -q 'v8.3.4 NOW is valid before future propagation' "$FCMOD"; then
    sed -i '/    out.now_shiny = now.1;/a\    // v8.3.4 NOW is valid before future propagation.\
    out.valid = true;\
    if next_frame(frame) == 0 { return out; }' "$FCMOD"
fi

# Defensive fix for the cheap-NOW fallback path (normally unreachable with
# SCAN_EVERY=1 in v8.3.x): Moltres current evaluation has the same rule there.
sed -i 's/LIVE.valid = now_n != 0 && next_frame(frame) != 0;/LIVE.valid = now_n != 0 \&\& now_frame_usable(frame);/' "$FCMOD"

# Pure regression test without mutating global target state.
if ! grep -q 'moltres_now_accepts_extended_frame_counter' "$FCMOD"; then
    awk '
    /    \#\[test\]/ && !done {
        print "    #[test]"
        print "    fn moltres_now_accepts_extended_frame_counter() {"
        print "        assert!(now_frame_usable_for(3, 0x0F));"
        print "        assert!(now_frame_usable_for(3, 0x00));"
        print "        assert!(!now_frame_usable_for(0, 0x0F));"
        print "        assert!(now_frame_usable_for(0, 5));"
        print "    }"
        print ""
        done = 1
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.3.3.1 PROB/BLUE LEGEND RNG v8.3.4 NOWFIX/' "$RUST"
sed -i 's/MOLTRES PROB RESCUE/MOLTRES NOW FRAME FIX/' "$RUST"
sed -i 's/"LEGEND,35,/"LEGEND,36,/' "$CTRACE"

grep -q 'fn now_frame_usable_for' "$FCMOD"
grep -q 'v8.3.4 NOW is valid before future propagation' "$FCMOD"
grep -q 'moltres_now_accepts_extended_frame_counter' "$FCMOD"
