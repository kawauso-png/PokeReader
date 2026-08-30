#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v7.7.1 searches the CURRENT sampled state only. Recompute every frame and
# disable future propagation during live hunt; this avoids candidate explosion
# and is much cheaper than a full +16F envelope scan every frame.
sed -i 's/const HORIZON: u8 = 16;/const HORIZON: u8 = 0;/' "$FCMOD"
sed -i 's/const SCAN_EVERY: u8 = 8;/const SCAN_EVERY: u8 = 1;/' "$FCMOD"

sed -i 's/BLUE MEWTWO RNG v7.7.0 AUTO/BLUE MEWTWO RNG v7.7.1 NOW/' "$RUST"
sed -i 's/AUTOPAUSE CANDIDATE MODE/AUTOPAUSE NOW MODE/' "$RUST"
sed -i 's/"MEWTWO,20,/"MEWTWO,21,/' "$CTRACE"
