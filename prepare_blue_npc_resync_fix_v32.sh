#!/bin/sh
set -eu

FCMOD=reader_core/src/gen1/shiny_forecast.rs
RUST=reader_core/src/gen1/mod.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.3.1: SCAN_EVERY=1 makes modulo scheduling unnecessary and Clippy rejects
# `% 1`. Keep full scan every GB frame without modulo.
sed -i 's/if SCAN_TICK % SCAN_EVERY == 0 || target_near || !LIVE.valid {/if SCAN_EVERY == 1 || target_near || !LIVE.valid {/' "$FCMOD"
sed -i 's/BLUE LEGEND RNG v8.3 NPCSYNC/BLUE LEGEND RNG v8.3.1 NPCSYNC/' "$RUST"
sed -i 's/"LEGEND,31,/"LEGEND,32,/' "$CTRACE"
