#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c
MAIN=3gx/sources/main.c

# v8.4 Articuno calibration-first build.
#
# Base: the hardware-successful v8.3.5 Moltres branch, including NPC resync,
# local-base reacquire, NOW-frame repair, probability rescue, Exact2F and VC
# reset/session clearing.
#
# Articuno is already present in the shared fixed-legend table as internal
# species 0x4A / Lv50, but it has no hardware event-path calibration yet.
# Zapdos and Moltres proved that bird timing is not interchangeable (their
# measured release->DV paths differ), so target id 2 deliberately remains
# Auto-Hunt locked until one Articuno Exact2F trace establishes its path.

# Dedicated build: boot directly on ARTICUNO (target id 2). Paused D-pad target
# switching remains available for diagnostics, but the intended test target is 2.
sed -i 's/static u32 blue_legend_target = 3u;/static u32 blue_legend_target = 2u;/' "$CTRACE"

# Do not expose Mewtwo-derived forecast candidates for the uncalibrated Articuno
# target. Exact2F/DV/call tracing remains fully active; only forecast/arm sets are
# suppressed so the overlay cannot suggest a false shiny timing.
if ! grep -q 'ARTICUNO_CAL_FORECAST_LOCK' "$FCMOD"; then
    awk '
    /pub fn scan\(seq:/ { in_scan = 1 }
    /pub fn mark_arm\(seq:/ { in_arm = 1 }
    {
        print
        if (in_scan && $0 ~ /^[[:space:]]*unsafe \{$/) {
            print "        // ARTICUNO_CAL_FORECAST_LOCK: no prediction before hardware calibration."
            print "        if LEGEND_TARGET_ID == 2 {"
            print "            LIVE = ForecastStats::default();"
            print "            LIVE.scan_age = 0;"
            print "            return LIVE;"
            print "        }"
            in_scan = 0
        } else if (in_arm && $0 ~ /^[[:space:]]*unsafe \{$/) {
            print "        // ARTICUNO_CAL_FORECAST_LOCK: keep Exact2F trace, discard false arm forecast."
            print "        if LEGEND_TARGET_ID == 2 {"
            print "            ARM = ArmForecast::default();"
            print "            for i in 0..RAW_WORDS { ARM_BITS[i] = 0; }"
            print "            return;"
            print "        }"
            in_arm = 0
        }
    }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# Make the dedicated mode unmistakable on hardware. The existing bird guard
# already leaves Auto Hunt disabled for target id 2.
sed -i 's/BLUE LEGEND RNG v8.3.5 VCRST/BLUE LEGEND RNG v8.4 ART CAL/' "$RUST"
sed -i 's/MOLTRES VC RESET SAFE/ARTICUNO CAL + VCRST/' "$RUST"
sed -i 's/CALIBRATE: EXACT2F ONLY/ARTICUNO: EXACT2F TRACE/' "$RUST"
sed -i 's/CAL AUTO LOCKED/AUTO LOCKED - NEED 1 TRACE/' "$RUST"

# New trace schema/build id; all existing legend_trace sections are preserved.
sed -i 's/"LEGEND,37,/"LEGEND,39,/' "$CTRACE"

# Guards: fail build preparation if an upstream patch changed a critical anchor.
# Downstream v40/v41 Articuno builds intentionally change the title and Auto-Hunt
# gate. Accept those final forms so repeated make lint/test/build prepare passes
# remain idempotent in the same Actions workspace.
grep -q 'static u32 blue_legend_target = 2u;' "$CTRACE"
grep -q 'ARTICUNO_CAL_FORECAST_LOCK' "$FCMOD"
grep -Eq 'BLUE LEGEND RNG v8\.4 ART CAL|BLUE LEGEND RNG v8\.4\.1 ART AUTO|BLUE LEGEND RNG v8\.4\.2 ART ADP' "$RUST"
grep -q 'ARTICUNO: EXACT2F TRACE' "$RUST"
grep -Eq 'host_blue_legend_target_id\(\) <= 1u \|\| host_blue_legend_target_id\(\) == 3u|host_blue_legend_target_id\(\) <= 3u' "$MAIN"
