#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# Traces 0048/0049 proved that the Exact2F event-side sample can also land
# +4 M-cycles from the normal-frame phase family.  v7.7.1 covered only
# 0/-4/-8, which made those actual DVs fall outside the forecast envelope.
# Keep the existing branches and add +4 conservatively.
sed -i 's/for jump in \[0u8, 60u8, 56u8\] { \/\/ 0, -4, -8 mod 64/for jump in [0u8, 60u8, 56u8, 4u8] { \/\/ 0, -4, -8, +4 mod 64/' "$FCMOD"

sed -i 's/BLUE MEWTWO RNG v7.7.1 NOW/BLUE MEWTWO RNG v7.7.2 +4/' "$RUST"
sed -i 's/AUTOPAUSE NOW MODE/AUTOPAUSE +4 ENVELOPE/' "$RUST"
sed -i 's/"MEWTWO,21,/"MEWTWO,22,/' "$CTRACE"
