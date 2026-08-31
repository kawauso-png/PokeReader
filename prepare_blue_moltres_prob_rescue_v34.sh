#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.3.3 Moltres probability-priority + drought rescue.
# Exhaustive analysis of the current five-correction Moltres event model over
# all 1,048,576 (ADD,DIV,4-phase-family) states shows shiny-containing NOW sets
# are only C5/S1, C6/S1, C10/S1, C12/S1. Therefore S/C >= 1/3 can never fire;
# the best possible ratio is 1/5. Realistic branch simulations also produce
# rare >10k-frame gaps with the five-correction model even when the scanner is
# healthy. This is a search-geometry issue, not a stale-scan bug.
#
# Strategy:
#   age < 1024 valid forecast frames : prefer >=1/6 (C5/C6) only
#   1024..4095                    : accept >=1/12 base-envelope candidates
#   age >= 4096                   : widen Moltres correction support -5..+3
#                                  and accept >=1/20 rescue candidates
# This keeps most stops in the high-quality 1/5..1/6 tier but prevents the
# observed long droughts from running indefinitely.

if ! grep -q 'MOLTRES_SEARCH_AGE' "$FCMOD"; then
    sed -i '/static mut LEGEND_TARGET_ID: u8 = 0;/a\static mut MOLTRES_SEARCH_AGE: u32 = 0;' "$FCMOD"

    # Reset drought age only when the selected legend actually changes.
    sed -i 's/pub fn set_legend_target(id: u32) { unsafe { LEGEND_TARGET_ID = id as u8; } }/pub fn set_legend_target(id: u32) { unsafe { let next = id as u8; if LEGEND_TARGET_ID != next { MOLTRES_SEARCH_AGE = 0; } LEGEND_TARGET_ID = next; } }/' "$FCMOD"

    awk '
    /fn legend_event_shift\(\) -> u16/ {
        print "pub fn moltres_search_age() -> u32 { unsafe { MOLTRES_SEARCH_AGE } }"
        print "pub fn moltres_rescue_mode() -> bool { unsafe { LEGEND_TARGET_ID == 3 && MOLTRES_SEARCH_AGE >= 4096 } }"
        print "pub fn moltres_corr_count() -> u8 { if moltres_rescue_mode() { 9 } else { 5 } }"
        print ""
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Base mode keeps the calibrated -3..+1 envelope. Rescue mode expands only
# after a long valid-search drought to -5..+3. The existing Moltres cap24 is
# enough: exhaustive candidate cardinality is at most C20 in rescue mode.
if ! grep -q 'v8.3.3 drought rescue corrections' "$FCMOD"; then
    awk '
    /    for corr in \[253u8, 254u8, 255u8, 0u8, 1u8\] \{/ {
        print "    // v8.3.3 drought rescue corrections: P5 normally, P9 after 4096 valid scans."
        print "    let rescue = unsafe { MOLTRES_SEARCH_AGE >= 4096 };"
        print "    let corrs = [251u8, 252u8, 253u8, 254u8, 255u8, 0u8, 1u8, 2u8, 3u8];"
        print "    let mut ci = if rescue { 0usize } else { 2usize };"
        print "    let end = if rescue { 9usize } else { 7usize };"
        print "    while ci < end {"
        print "        let corr = corrs[ci];"
        next
    }
    /        collect_battle_moltres\(pre_add, pre_div, p, count, shiny_count\);/ {
        print
        print "        ci += 1;"
        next
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# SCAN_EVERY is already 1 in v8.3.x. Count only valid Moltres forecast frames;
# NPC re-sync downtime does not falsely advance the quality tier.
if ! grep -q 'v8.3.3 valid-search age' "$FCMOD"; then
    sed -i '/LIVE = scan_full(seq, rng, div, frame, adp);/a\            // v8.3.3 valid-search age.\
            if LEGEND_TARGET_ID == 3 && LIVE.valid { MOLTRES_SEARCH_AGE = MOLTRES_SEARCH_AGE.saturating_add(1); }' "$FCMOD"
fi

# Probability-tier gate. Generic Mewtwo/Zapdos behavior remains unchanged.
if ! grep -q 'fn candidate_probability_ok' "$AUTOMOD"; then
    awk '
    /pub fn observe\(/ {
        print "fn moltres_prob_den() -> u16 {"
        print "    let age = super::shiny_forecast::moltres_search_age();"
        print "    if age < 1024 { 6 } else if age < 4096 { 12 } else { 20 }"
        print "}"
        print ""
        print "pub fn moltres_prob_den_overlay() -> u16 { moltres_prob_den() }"
        print ""
        print "fn candidate_probability_ok(fc: ForecastStats) -> bool {"
        print "    if fc.now_candidates == 0 || fc.now_shiny == 0 { return false; }"
        print "    unsafe {"
        print "        if LEGEND_TARGET_ID != 3 {"
        print "            return fc.now_candidates <= max_now_candidates();"
        print "        }"
        print "    }"
        print "    let den = moltres_prob_den();"
        print "    fc.now_candidates <= max_now_candidates()"
        print "        && (fc.now_shiny as u16).saturating_mul(den) >= fc.now_candidates"
        print "}"
        print ""
    }
    { print }
    ' "$AUTOMOD" > "$AUTOMOD.tmp"
    mv "$AUTOMOD.tmp" "$AUTOMOD"

    awk '
    BEGIN { skip = 0 }
    /^[[:space:]]*if fc\.now_candidates != 0$/ {
        print "        if candidate_probability_ok(fc)"
        skip = 1
        next
    }
    skip {
        if ($0 ~ /&& fc\.now_shiny != 0/) { skip = 0; next }
        next
    }
    { print }
    ' "$AUTOMOD" > "$AUTOMOD.tmp"
    mv "$AUTOMOD.tmp" "$AUTOMOD"
fi

# Overlay the live quality tier and rescue envelope so a long wait is directly
# diagnosable on hardware without another CSV.
if ! grep -q 'MOL Q1/{} A{} P{}' "$RUST"; then
    awk '
    /let npc = adaptive_model::npc_resync_stats\(\);/ {
        print
        print "        let mol_age = shiny_forecast::moltres_search_age();"
        print "        let mol_den = autopause::moltres_prob_den_overlay();"
        print "        let mol_corr = shiny_forecast::moltres_corr_count();"
        next
    }
    /NPC L\{\} R\{\} C\{\} \{\}/ {
        print
        print "        if legend_target == 3 { pnp::println!(color = YELLOW, \"MOL Q1/{} A{} P{}\", mol_den, mol_age, mol_corr); }"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.3.2 LOCALBASE/BLUE LEGEND RNG v8.3.3 PROB/' "$RUST"
sed -i 's/MOLTRES NPC LOCALBASE/MOLTRES PROB RESCUE/' "$RUST"
sed -i 's/"LEGEND,33,/"LEGEND,34,/' "$CTRACE"

# Build-time guards: fail early if an upstream prep changed one of the anchors.
grep -q 'MOLTRES_SEARCH_AGE' "$FCMOD"
grep -q 'v8.3.3 drought rescue corrections' "$FCMOD"
grep -q 'candidate_probability_ok' "$AUTOMOD"
grep -q 'MOL Q1/{} A{} P{}' "$RUST"
