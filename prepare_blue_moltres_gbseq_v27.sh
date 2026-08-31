#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.2: give the predictor a real logical GB-frame sequence.
#
# host_blue_dvtrace_sample() increments trace_seq on every host sample.  On
# hardware the top-screen hook can sample the same emulated GB frame more than
# once, so trace_seq is not a GB-frame identity.  v8.2.1 tried to preserve model
# state when seq==prev_seq, but that condition can never be true for trace_seq.
#
# Keep trace_seq unchanged for CSV/Exact2F timing diagnostics.  Add a separate
# logical sequence that advances only when the sampled hRandomAdd/Sub +
# hFrameCounter tuple changes.  Feed that sequence (and the last accepted model
# RNG/DIV sample) to the adaptive/phase/forecast path.  Duplicate host samples
# then hit the existing v8.2.1 seq==prev_seq hold without corrupting the 80-frame
# adaptive window or the DIV phase family.

if ! grep -q 'gb_model_seq' "$CTRACE"; then
    sed -i '/static u32 trace_seq = 0;/a\
static u32 gb_model_seq = 0;\
static u32 gb_model_rng = 0;\
static bool gb_model_rng_valid = false;' "$CTRACE"

    sed -i '/live_rng = ((u32)add << 16) | ((u32)sub << 8) | frame;/a\
    if (!gb_model_rng_valid || live_rng != gb_model_rng)\
    {\
        gb_model_rng = live_rng;\
        gb_model_rng_valid = true;\
        gb_model_seq++;\
    }' "$CTRACE"

    sed -i '/u32 host_blue_dvtrace_seq(void) { return trace_seq; }/a\
u32 host_blue_dvtrace_gb_seq(void) { return gb_model_seq; }' "$CTRACE"
fi

if ! grep -q 'fn host_blue_dvtrace_gb_seq' "$RUST"; then
    sed -i '/fn host_blue_dvtrace_seq() -> u32;/a\    fn host_blue_dvtrace_gb_seq() -> u32;' "$RUST"
fi

if ! grep -q 'MODEL_LAST_SEQ' "$RUST"; then
    sed -i '/static mut HOST_FRAME: u32 = 0;/a\
static mut MODEL_LAST_SEQ: u32 = 0;\
static mut MODEL_LAST_RNG: u32 = 0;\
static mut MODEL_LAST_DIV: u8 = 0;' "$RUST"
fi

# Capture the model sequence and the last accepted model sample before the
# observer block injected by prepare_blue_divphase_v12.sh.
if ! grep -q 'let model_seq = host_blue_dvtrace_gb_seq' "$RUST"; then
    sed -i '/let phase_usable = current.all_ptrs_ok() && !current.in_mewtwo_battle();/a\
        let model_seq = host_blue_dvtrace_gb_seq();\
        let (model_prev_seq, model_prev_rng, model_prev_div) =\
            (MODEL_LAST_SEQ, MODEL_LAST_RNG, MODEL_LAST_DIV);' "$RUST"
fi

# Phase tracker: use logical GB seq + last accepted model RNG/DIV.
sed -i '/let _ = phase_tracker::observe(/,/^[[:space:]]*);/ {
    s/previous.seq, previous.rng, previous.div,/model_prev_seq, model_prev_rng, model_prev_div,/
    s/current.seq, current.rng, current.div, phase_usable,/model_seq, current.rng, current.div, phase_usable,/
}' "$RUST"

# Adaptive model: same logical stream.
sed -i '/let _ = adaptive_model::observe(/,/^[[:space:]]*);/ {
    s/previous.seq, previous.rng, previous.div,/model_prev_seq, model_prev_rng, model_prev_div,/
    s/current.seq, current.rng, current.div, phase_usable,/model_seq, current.rng, current.div, phase_usable,/
}' "$RUST"

# Forecast phase observer only needs seq + DIV, but must use the accepted DIV
# rather than an arbitrary duplicate-host-sample DIV.
sed -i '/shiny_forecast::observe_phase(/,/^[[:space:]]*);/ {
    s/previous.seq, previous.div, current.seq, current.div, phase_usable,/model_prev_seq, model_prev_div, model_seq, current.div, phase_usable,/
}' "$RUST"

# Commit the accepted model sample only after every observer has seen it.  On a
# duplicate logical frame model_seq==model_prev_seq, so the stored RNG/DIV stay
# anchored to the last real GB-frame transition.
if ! grep -q 'v8.2.2 accept logical GB sample' "$RUST"; then
    awk '
    /shiny_forecast::observe_phase\(/ { in_fc_phase = 1 }
    {
        print
        if (in_fc_phase && $0 ~ /^[[:space:]]*\);/) {
            print "        // v8.2.2 accept logical GB sample only on a real GB transition."
            print "        if phase_usable && model_seq != model_prev_seq {"
            print "            MODEL_LAST_SEQ = model_seq;"
            print "            MODEL_LAST_RNG = current.rng;"
            print "            MODEL_LAST_DIV = current.div;"
            print "        }"
            in_fc_phase = 0
        }
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

# Forecast/adaptive residue timing and AutoPause NOW decisions must use the same
# logical GB sequence.  Trace/event timing continues to use current.seq.
sed -i '/let fc = shiny_forecast::scan(/,/^[[:space:]]*);/ {
    s/current.seq, current.rng, current.div/model_seq, current.rng, current.div/
}' "$RUST"
sed -i 's/autopause::observe(current.seq, adp, fc, auto_enabled)/autopause::observe(model_seq, adp, fc, auto_enabled)/g' "$RUST"

# An Exact2F arm snapshot must use the logical sequence paired with its sampled
# RNG/DIV, not the host trace counter.
sed -i 's/shiny_forecast::mark_arm(s.seq, s.rng, s.div/shiny_forecast::mark_arm(MODEL_LAST_SEQ, s.rng, s.div/g' "$RUST"

# Make the two counters visible on hardware.  H may advance on a duplicate host
# sample while G intentionally holds; CSP should no longer be reset by that.
if ! grep -q 'SEQ H{} G{}' "$RUST"; then
    sed -i '/pnp::println!("FC NOW C{} S{} P{}", fc.now_candidates, fc.now_shiny, fc.phase_count);/a\        pnp::println!("SEQ H{} G{}", current.seq, model_seq);' "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.2.1 PFX/BLUE LEGEND RNG v8.2.2 GBSEQ/' "$RUST"
sed -i 's/MOLTRES PHASEFIX AUTO/MOLTRES GBSEQ AUTO/' "$RUST"
sed -i 's/"LEGEND,26,/"LEGEND,27,/' "$CTRACE"
