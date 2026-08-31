#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
PHTMOD=reader_core/src/gen1/phase_tracker.rs
KMOD=reader_core/src/gen1/k_observer.rs
BOOTMOD=reader_core/src/gen1/boot_capture.rs
CTRACE=3gx/sources/blue_dvtrace.c
MAIN=3gx/sources/main.c
HDR=3gx/includes/pokereader.h

# v8.3.5 VC-reset/session reset support.
# A VC Reset restarts the emulated GB software without reloading the 3GX process,
# so Rust/C prediction statics can otherwise survive into the next attempt.
# Reset every predictor/observer state on:
#   1) selected-legend battle entry (the attempt is over),
#   2) pointer invalid -> valid recovery (best-effort VC reset detection),
#   3) Auto Hunt OFF -> ON (guaranteed fresh session after a VC Reset),
#   4) paused Y+B manual reset fallback.

# C logical GB model clock. Keep host trace_seq monotonic for CSV timing; only
# the prediction clock is restarted.
if ! grep -q '^void host_blue_dvtrace_reset_model_clock' "$CTRACE"; then
    sed -i '/u32 host_blue_dvtrace_gb_seq(void) { return gb_model_seq; }/a\
void host_blue_dvtrace_reset_model_clock(void)\
{\
    gb_model_seq = 0;\
    gb_model_rng = 0;\
    gb_model_rng_valid = false;\
}' "$CTRACE"
fi

# Adaptive model: cold-start again, including NPC persisted lock/base/residue.
if ! grep -q '^pub fn reset_session()' "$ADPMOD"; then
    awk '
    /pub fn stats\(\) -> AdaptiveStats/ {
        print "pub fn reset_session() {"
        print "    unsafe {"
        print "        HEAD = 0; COUNT = 0; CLEAN_TAIL = 0; LAST_SEQ = 0;"
        print "        LIVE = AdaptiveStats::default(); LIVE.last_gap = 0xFF;"
        print "        ARM = AdaptiveStats::default(); ARM.last_gap = 0xFF;"
        print "        NPC_LOCK_VALID = false;"
        print "        NPC_LOCK_BASE = 0;"
        print "        NPC_LOCK_RESIDUE20 = 0;"
        print "        NPC_RESETS = 0;"
        print "        NPC_LAST_RESET_SEQ = 0;"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

# Forecast: phase family, NOW/future cache, arm snapshot and Moltres drought age.
if ! grep -q '^pub fn reset_session()' "$FCMOD"; then
    awk '
    /pub fn scan\(seq:/ {
        print "pub fn reset_session() {"
        print "    unsafe {"
        print "        PHASE_MASK = 0; PHASE_LAST_SEQ = 0; SCAN_TICK = 0;"
        print "        LIVE = ForecastStats::default();"
        print "        ARM = ArmForecast::default();"
        print "        MOLTRES_SEARCH_AGE = 0;"
        print "        for i in 0..RAW_WORDS { RAW_BITS[i] = 0; ARM_BITS[i] = 0; }"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"
fi

# AutoPause latch/fire state.
if ! grep -q '^pub fn reset_session()' "$AUTOMOD"; then
    awk '
    /pub fn observe\(/ {
        print "pub fn reset_session() { reset_all(false); }"
        print ""
    }
    { print }
    ' "$AUTOMOD" > "$AUTOMOD.tmp"
    mv "$AUTOMOD.tmp" "$AUTOMOD"
fi

# Legacy phase tracker is diagnostic, but stale state after reset is misleading.
if ! grep -q '^pub fn reset_session()' "$PHTMOD"; then
    awk '
    /^pub fn observe\(/ {
        print "pub fn reset_session() {"
        print "    unsafe {"
        print "        TRACKER.clear(0, false, 10, false);"
        print "        TRACKER.forecast_checks = 0; TRACKER.forecast_hits = 0;"
        print "        TRACKER.resets = 0; TRACKER.rng_skips = 0;"
        print "        TRACKER.last_k = 0; TRACKER.last_div_step = 0; TRACKER.last_gap = 0xFF;"
        print "        TRACKER.arm_stats = TrackerStats::default();"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$PHTMOD" > "$PHTMOD.tmp"
    mv "$PHTMOD.tmp" "$PHTMOD"
fi

# K observer diagnostic counters/histograms.
if ! grep -q '^pub fn reset_session()' "$KMOD"; then
    awk '
    /pub fn stats\(\) -> KObsStats/ {
        print "pub fn reset_session() {"
        print "    unsafe {"
        print "        RING_HEAD = 0; RING_COUNT = 0;"
        print "        HIST = [0; 256]; PHASE_HIST = [[0; 256]; 4];"
        print "        VALID_TOTAL = 0; INVALID_TOTAL = 0;"
        print "        ARM_COUNT = 0; ARM_VALID_TOTAL = 0; ARM_INVALID_TOTAL = 0;"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$KMOD" > "$KMOD.tmp"
    mv "$KMOD.tmp" "$KMOD"
fi

# Boot/omni diagnostic capture counters.
if ! grep -q '^pub fn reset_session()' "$BOOTMOD"; then
    awk '
    /pub fn stats\(\) -> BootStats/ {
        print "pub fn reset_session() {"
        print "    unsafe {"
        print "        HEAD = 0; COUNT = 0; LIVE_VALID = 0; LIVE_INVALID = 0;"
        print "        ARM_COUNT = 0; ARM_VALID = 0; ARM_INVALID = 0;"
        print "        LAST_K = 0; LAST_STEP = 0; LAST_GAP = 0xFF;"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$BOOTMOD" > "$BOOTMOD.tmp"
    mv "$BOOTMOD.tmp" "$BOOTMOD"
fi

# Rust needs access to the C model-clock reset.
if ! grep -q 'fn host_blue_dvtrace_reset_model_clock' "$RUST"; then
    sed -i '/fn host_blue_dvtrace_gb_seq() -> u32;/a\    fn host_blue_dvtrace_reset_model_clock();' "$RUST"
fi

# Central full reset + diagnostic reason/count.
# reason 1=battle entry, 2=pointer recovery, 3=host/manual/Auto-Hunt rising edge.
if ! grep -q 'fn blue_reset_predictor_session' "$RUST"; then
    awk '
    /pub fn run_frame\(\) \{/ {
        print "static mut VC_RESET_COUNT: u32 = 0;"
        print "static mut VC_RESET_REASON: u32 = 0;"
        print ""
        print "fn blue_reset_predictor_session(reason: u32) {"
        print "    unsafe {"
        print "        host_blue_dvtrace_reset_model_clock();"
        print "        MODEL_LAST_SEQ = 0; MODEL_LAST_RNG = 0; MODEL_LAST_DIV = 0;"
        print "        VC_RESET_COUNT = VC_RESET_COUNT.wrapping_add(1);"
        print "        VC_RESET_REASON = reason;"
        print "    }"
        print "    adaptive_model::reset_session();"
        print "    shiny_forecast::reset_session();"
        print "    autopause::reset_session();"
        print "    phase_tracker::reset_session();"
        print "    k_observer::reset_session();"
        print "    boot_capture::reset_session();"
        print "}"
        print ""
        print "#[no_mangle]"
        print "pub extern \"C\" fn blue_vc_reset_model() { blue_reset_predictor_session(3); }"
        print ""
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

# Best-effort automatic VC reset detection: if emulator pointer sampling drops
# out then returns, discard all pre-reset state before observers use the sample.
if ! grep -q 'v8.3.5 pointer recovery reset' "$RUST"; then
    sed -i '/        state.last_snapshot = current;/a\        // v8.3.5 pointer recovery reset.\
        if previous.seq != 0 && current.all_ptrs_ok() && !previous.all_ptrs_ok() {\
            blue_reset_predictor_session(2);\
        }' "$RUST"
fi

# A fixed-legend encounter consumes the old hunt session. Clear prediction state
# after trace finalization so a later VC Reset cannot inherit it.
if ! grep -q 'v8.3.5 battle-entry session end' "$RUST"; then
    sed -i '/            state.fixed_target = None;/i\            // v8.3.5 battle-entry session end.\
            blue_reset_predictor_session(1);' "$RUST"
fi

# Export manual/session reset to C freeze-loop logic.
if ! grep -q 'blue_vc_reset_model' "$HDR"; then
    sed -i '/u32 blue_capture_target(u32 run_id);/a\void blue_vc_reset_model(void);' "$HDR"
fi

# Guaranteed reset on every Auto Hunt OFF->ON. This is the key VC-reset safety
# property: after the user VC-resets a failed encounter and returns to Moltres,
# enabling Auto Hunt always starts from a fresh 80F cold learn.
if ! grep -q 'v8.3.5 fresh session on Auto Hunt enable' "$MAIN"; then
    sed -i 's/blue_autosearch_enabled = !blue_autosearch_enabled;/\/\* v8.3.5 fresh session on Auto Hunt enable. \*\/\n                    if (!blue_autosearch_enabled) blue_vc_reset_model();\n                    blue_autosearch_enabled = !blue_autosearch_enabled;/' "$MAIN"
fi

# Manual fallback while paused: Y+B clears all predictor state without allowing
# a GB frame through. Keep plain B behavior unchanged.
if ! grep -q 'VC predictor manual reset' "$MAIN"; then
    awk '
    /            \/\/ B cancels a pending\/error state without resuming the game\./ {
        print "            // VC predictor manual reset: paused-only Y+B."
        print "            if ((just_pressed & KEY_B) && (held & KEY_Y))"
        print "            {"
        print "                blue_vc_reset_model();"
        print "                reset_blue_fixed_transient();"
        print "                blue_fixed_error = 0;"
        print "                continue;"
        print "            }"
        print ""
    }
    { print }
    ' "$MAIN" > "$MAIN.tmp"
    mv "$MAIN.tmp" "$MAIN"
fi

# Make reset activity visible. R: 1=battle, 2=ptr recovery, 3=Auto/manual host reset.
if ! grep -q 'RST N{} R{}' "$RUST"; then
    sed -i '/pnp::println!("SEQ H{} G{}", current.seq, model_seq);/a\        pnp::println!("RST N{} R{}", VC_RESET_COUNT, VC_RESET_REASON);' "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.3.4 NOWFIX/BLUE LEGEND RNG v8.3.5 VCRST/' "$RUST"
sed -i 's/MOLTRES NOW FRAME FIX/MOLTRES VC RESET SAFE/' "$RUST"
sed -i 's/"LEGEND,36,/"LEGEND,37,/' "$CTRACE"

# Build-time guards.
grep -q '^void host_blue_dvtrace_reset_model_clock' "$CTRACE"
grep -q '^pub fn reset_session()' "$ADPMOD"
grep -q '^pub fn reset_session()' "$FCMOD"
grep -q 'fn blue_reset_predictor_session' "$RUST"
grep -q 'v8.3.5 fresh session on Auto Hunt enable' "$MAIN"
grep -q 'RST N{} R{}' "$RUST"
