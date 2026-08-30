#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v7.7.1 AutoPause decisions use the CURRENT sampled state, not a propagated
# future state. Keep the +16F scan at its old 8F diagnostic cadence, but refresh
# NOW candidates on every intervening frame with only the cheap current-state
# evaluation (normally four hidden-phase seeds once ADP is READY).
if ! grep -q 'v7.7.1 fresh NOW' "$FCMOD"; then
    python3 - "$FCMOD" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = '''        if SCAN_TICK % SCAN_EVERY == 0 || target_near || !LIVE.valid {
            LIVE = scan_full(seq, rng, div, frame, adp);
        } else {
            LIVE.scan_age = LIVE.scan_age.saturating_add(1);
        }
'''
new = '''        if SCAN_TICK % SCAN_EVERY == 0 || target_near || !LIVE.valid {
            LIVE = scan_full(seq, rng, div, frame, adp);
        } else {
            // v7.7.1 fresh NOW: AutoPause needs this exact sampled frame. Do
            // not propagate normal RNG branches just to make a pause decision.
            let now_n = seed_current(rng, div, frame);
            let now = evaluate_states(now_n);
            LIVE.phase_count = PHASE_MASK.count_ones() as u8;
            LIVE.now_candidates = now.0;
            LIVE.now_shiny = now.1;
            LIVE.valid = now_n != 0 && next_frame(frame) != 0;
            LIVE.scan_age = LIVE.scan_age.saturating_add(1);
        }
'''
if old not in s:
    raise SystemExit('scan block not found')
p.write_text(s.replace(old, new, 1))
PY
fi

sed -i 's/BLUE MEWTWO RNG v7.7.0 AUTO/BLUE MEWTWO RNG v7.7.1 NOW/' "$RUST"
sed -i 's/AUTOPAUSE CANDIDATE MODE/AUTOPAUSE NOW MODE/' "$RUST"
sed -i 's/"MEWTWO,20,/"MEWTWO,21,/' "$CTRACE"
