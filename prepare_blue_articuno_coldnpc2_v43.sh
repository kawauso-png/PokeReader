#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.4.4 Articuno cold-start NPC tolerance, second hardware sample.
#
# Hardware after v42:
#   ADP -- B10 R07
#   H78/80 M4/4 S4 D16
#   NPC L0 R0 C80 COLD
#   BAD1 d9C s12 g1 r16
#   BAD2 d09 s13 g0 r06
#
# Each adaptive row is inferred independently from adjacent RNG samples, so two
# bad rows mean two distinct NPC-affected intervals in the 80-frame cold window.
# Do NOT promote d9C or d09 into ordinary transition classes.
#
# Cold lock is allowed at 78/80 only when every rejected row is clearly separated
# from the nearest legal transition for that exact (special, step, gap) class.
# This keeps near-model errors strict while admitting up to two genuine NPC jumps.

if ! grep -q 'ARTICUNO_COLDNPC2_V43' "$ADPMOD"; then
    awk '
    /fn cold_one_strong_npc_outlier\(base: u8, residue: u8\) -> bool \{/ {
        print "fn circular_delta_distance(a: u8, b: u8) -> u8 {"
        print "    let d = a.wrapping_sub(b);"
        print "    let n = 0u8.wrapping_sub(d);"
        print "    if d < n { d } else { n }"
        print "}"
        print ""
        print "fn model_delta_distance(delta: u8, special: bool, step: u8, gap: u8) -> u8 {"
        print "    let mut best = 0x80u8;"
        print "    let mut c = 0u16;"
        print "    while c <= 0xFF {"
        print "        let cand = c as u8;"
        print "        let legal = if special { allowed_special(cand, step, gap) } else { allowed_normal(cand, step, gap) };"
        print "        if legal {"
        print "            let dist = circular_delta_distance(delta, cand);"
        print "            if dist < best { best = dist; }"
        print "        }"
        print "        c += 1;"
        print "    }"
        print "    best"
        print "}"
        print ""
        print "fn cold_npc_outliers(base: u8, residue: u8, expected_bad: u8) -> bool {"
        print "    unsafe {"
        print "        if COUNT != WIN { return false; }"
        print "        let mut bad = 0u8;"
        print "        for i in 0..COUNT {"
        print "            let r = row_at_oldest(i);"
        print "            let d = r.k.wrapping_sub(base);"
        print "            let special = (r.seq % 20) as u8 == residue;"
        print "            let ok = if special { allowed_special(d, r.step, r.gap) } else { allowed_normal(d, r.step, r.gap) };"
        print "            if !ok {"
        print "                bad = bad.saturating_add(1);"
        print "                if bad > expected_bad { return false; }"
        print "                // ARTICUNO_COLDNPC2_V43: reject near-model misses."
        print "                if model_delta_distance(d, special, r.step, r.gap) < 4 { return false; }"
        print "            }"
        print "        }"
        print "        bad == expected_bad"
        print "    }"
        print "}"
        print ""
        skip=1
        next
    }
    skip {
        if ($0 ~ /^}/) { skip=0 }
        next
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"

    # v42 inserted the one-outlier ready clause. Replace it with strict 80/80,
    # validated 79/80, or validated 78/80.
    sed -i 's/(core_hits == WIN as u8 || (core_hits == (WIN as u8 - 1) && cold_one_strong_npc_outlier(base, residue)))/(core_hits == WIN as u8 || (core_hits == (WIN as u8 - 1) \&\& cold_npc_outliers(base, residue, 1)) || (core_hits == (WIN as u8 - 2) \&\& cold_npc_outliers(base, residue, 2)))/' "$ADPMOD"

    awk '
    /    fn normalized_support_contains_both_observed_modes\(\) \{/ {
        print "    #[test]"
        print "    fn articuno_cold_two_npc_rows_are_far_from_model() {"
        print "        assert!(model_delta_distance(0x9C, false, 0x12, 1) >= 4);"
        print "        assert!(model_delta_distance(0x09, false, 0x13, 0) >= 4);"
        print "        assert_eq!(model_delta_distance(0x00, false, 0x13, 0), 0);"
        print "        assert_eq!(model_delta_distance(0x03, true, 0x12, 1), 0);"
        print "    }"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.4.3 ART COLD1/BLUE LEGEND RNG v8.4.4 ART COLD2/' "$RUST"
sed -i 's/"LEGEND,42,/"LEGEND,43,/' "$CTRACE"

grep -q 'ARTICUNO_COLDNPC2_V43' "$ADPMOD"
grep -q 'cold_npc_outliers(base, residue, 2)' "$ADPMOD"
grep -q 'core_hits == (WIN as u8 - 2)' "$ADPMOD"
grep -q 'articuno_cold_two_npc_rows_are_far_from_model' "$ADPMOD"
grep -q 'BLUE LEGEND RNG v8.4.4 ART COLD2' "$RUST"
grep -q '"LEGEND,43,' "$CTRACE"
