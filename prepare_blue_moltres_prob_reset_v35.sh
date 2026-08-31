#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.3.3.1: forecast scanning runs even while Auto Hunt is OFF. Reset the
# Moltres drought/quality age on the Auto Hunt OFF->ON edge so every hunt starts
# in the high-quality P5 / Q1/6 tier instead of inheriting menu/travel frames or
# a previous failed attempt.

if ! grep -q 'pub fn reset_moltres_search_age' "$FCMOD"; then
    sed -i '/pub fn moltres_search_age() -> u32/a\pub fn reset_moltres_search_age() { unsafe { MOLTRES_SEARCH_AGE = 0; } }' "$FCMOD"
fi

if ! grep -q 'v8.3.3.1 Auto Hunt rising edge' "$AUTOMOD"; then
    sed -i '/        LIVE.enabled = true;/i\        // v8.3.3.1 Auto Hunt rising edge: start each Moltres hunt at age zero.\
        if !LIVE.enabled {\
            unsafe { if LEGEND_TARGET_ID == 3 { super::shiny_forecast::reset_moltres_search_age(); } }\
        }' "$AUTOMOD"
fi

sed -i 's/BLUE LEGEND RNG v8.3.3 PROB/BLUE LEGEND RNG v8.3.3.1 PROB/' "$RUST"
sed -i 's/"LEGEND,34,/"LEGEND,35,/' "$CTRACE"

grep -q 'reset_moltres_search_age' "$FCMOD"
grep -q 'v8.3.3.1 Auto Hunt rising edge' "$AUTOMOD"
