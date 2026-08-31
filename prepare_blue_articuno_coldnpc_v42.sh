#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.4.3 Articuno cold-start NPC tolerance.
#
# Hardware after v41:
#   ADP -- B10 R04
#   H79/80 M4/4 S4 D16
#   NPC L0 R0 C80 COLD
#   BAD1 d20 s12 g1 r13
#
# v41 fixed the repeated dFF/s13/g0 class. The sole remaining d20 row is a
# large K jump, consistent with an NPC Random() consumption during the initial
# 80-frame cold window. Do NOT promote d20 to a normal transition.
#
# Allow cold lock only when:
#   - the window is otherwise fully locked,
#   - exactly 79/80 rows match the learned model,
#   - the one bad row is a strong circular K outlier (distance >= 0x10).
# Small/near-model mismatches remain rejected. After cold lock, the existing
# NPC resync/local-base machinery handles subsequent jumps.

if ! grep -q 'ARTICUNO_COLDNPC_V42' "$ADPMOD"; then
    awk '
    /fn calculate\(\) -> AdaptiveStats \{/ {
        print "fn cold_one_strong_npc_outlier(base: u8, residue: u8) -> bool {"
        print "    unsafe {"
        print "        if COUNT != WIN { return false; }"
        print "        let mut bad = 0u8;"
        print "        let mut strong = false;"
        print "        for i in 0..COUNT {"
        print "            let r = row_at_oldest(i);"
        print "            let d = r.k.wrapping_sub(base);"
        print "            let special = (r.seq % 20) as u8 == residue;"
        print "            let ok = if special { allowed_special(d, r.step, r.gap) } else { allowed_normal(d, r.step, r.gap) };"
        print "            if !ok {"
        print "                bad = bad.saturating_add(1);"
        print "                let neg = 0u8.wrapping_sub(d);"
        print "                let circ = if d < neg { d } else { neg };"
        print "                strong = circ >= 0x10; // ARTICUNO_COLDNPC_V42"
        print "            }"
        print "        }"
        print "        bad == 1 && strong"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"

    # v31 rewrites the original ready predicate into `let cold_ready = ...`.
    # Replace only its strict core-hit clause; every other readiness gate stays.
    sed -i 's/&& core_hits == WIN as u8/\&\& (core_hits == WIN as u8 || (core_hits == (WIN as u8 - 1) \&\& cold_one_strong_npc_outlier(base, residue)))/' "$ADPMOD"

    awk '
    /    fn normalized_support_contains_both_observed_modes\(\) \{/ {
        print "    #[test]"
        print "    fn articuno_cold_npc_rule_keeps_normal_classes_strict() {"
        print "        assert!(!allowed_normal(0x20, 0x12, 1));"
        print "        assert!(!allowed_special(0x20, 0x12, 1));"
        print "    }"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.4.2 ART ADP/BLUE LEGEND RNG v8.4.3 ART COLD1/' "$RUST"
sed -i 's/"LEGEND,41,/"LEGEND,42,/' "$CTRACE"

grep -q 'ARTICUNO_COLDNPC_V42' "$ADPMOD"
grep -q 'cold_one_strong_npc_outlier' "$ADPMOD"
grep -q 'core_hits == (WIN as u8 - 1)' "$ADPMOD"
grep -q 'BLUE LEGEND RNG v8.4.3 ART COLD1' "$RUST"
grep -q '"LEGEND,42,' "$CTRACE"
