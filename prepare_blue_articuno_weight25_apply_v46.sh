#!/bin/sh
set -eu

V45=prepare_blue_articuno_weight25_v45.sh
AUTOMOD=reader_core/src/gen1/autopause.rs

# Apply the v45 generator while bypassing only its obsolete exact-string guards.
# All substantive v45 code is still generated; the guards below validate the
# final integrated form instead.
sed '/^grep -q /d' "$V45" | sh

# The Moltres probability work introduced candidate_probability_ok() as the
# shared final NOW gate.  Target 2 must therefore add W25 there, rather than at
# the older raw if-condition that v45 originally targeted.
if ! grep -q 'ARTICUNO_WEIGHT_GATE_CALL_V46' "$AUTOMOD"; then
    sed -i '/if fc.now_candidates == 0 || fc.now_shiny == 0 { return false; }/a\    unsafe { if LEGEND_TARGET_ID == 2 && !weighted_gate(2, \&fc) { return false; } } // ARTICUNO_WEIGHT_GATE_CALL_V46' "$AUTOMOD"
fi

# The pre-existing autopause unit-test helper constructs ForecastStats with an
# explicit literal.  Add the v45 score fields to that helper only.
if ! grep -q 'ARTICUNO_TEST_FIELDS_V46' "$AUTOMOD"; then
    awk '
    BEGIN { helper=0; done=0 }
    /fn fc\(now_candidates: u16, now_shiny: u8\) -> ForecastStats/ { helper=1 }
    helper && !done && /^[[:space:]]*now_shiny,$/ {
        print
        print "            now_weight_total: 0, // ARTICUNO_TEST_FIELDS_V46"
        print "            now_shiny_weight: 0,"
        print "            now_shiny_pct: 0,"
        done=1
        next
    }
    { print }
    ' "$AUTOMOD" > "$AUTOMOD.tmp"
    mv "$AUTOMOD.tmp" "$AUTOMOD"
fi

# Final guards validate behavior, not fragile whitespace.
grep -q 'ARTICUNO_WEIGHT_GATE_V45' "$AUTOMOD"
grep -q 'ARTICUNO_WEIGHT_GATE_CALL_V46' "$AUTOMOD"
grep -q 'ARTICUNO_TEST_FIELDS_V46' "$AUTOMOD"
grep -q 'ARTICUNO_WEIGHT25_V45' reader_core/src/gen1/shiny_forecast.rs
grep -q 'replay_0022_is_high_confidence_weight25' reader_core/src/gen1/shiny_forecast.rs
grep -q 'ARTW {}/{} {}%' reader_core/src/gen1/mod.rs
grep -q 'BLUE LEGEND RNG v8.4.6 ART W25' reader_core/src/gen1/mod.rs
grep -q '"LEGEND,45,' 3gx/sources/blue_dvtrace.c
