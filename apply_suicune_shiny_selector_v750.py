#!/usr/bin/env python3
from pathlib import Path
import re

M = Path('3gx/sources/main.c')
T = Path('reader_core/src/crystal/trace.rs')
P = Path('reader_core/src/crystal/practical.rs')

m = M.read_text()
t = T.read_text()
p = P.read_text()

# -------------------------------------------------------------------------
# Suicune v7.5.0 Shiny Selector / VC Reset Retry
#
# Production boundary:
#   * read-only RNG / DIV / phase observation
#   * current-root / future-candidate search is allowed
#   * Exact-2F and PokeReader Pause are allowed as input-timing assistance
#   * NO RNG/DIV/DV writes
#   * NO host-tick waiting to choose START/Resume phase
#   * a failed gate returns to the normal VC-reset retry workflow
#
# v7.3.8 already supplies the confidence-gated adaptive shiny evaluator and
# B40/B716/B717 revalidation.  v7.5.0 deliberately keeps that conservative
# evaluator for the first real shiny attempts, but removes the later causal
# experiment's host-phase waits.  The START/Resume metrics remain telemetry
# only, so every successful encounter still comes from ordinary game progress.
# -------------------------------------------------------------------------

# v5.0 installs one START host-phase wait and v7.3.0 replaces the old Resume
# wait with another.  Remove ONLY the tight system-tick waits; keep target and
# actual tick capture for diagnostics.  After v7.3.8 exactly two such waits
# must exist.  Failing closed here is intentional so a future generator change
# cannot silently re-enable phase manipulation in a v7.5 production build.
wait_pat = re.compile(r'\s*while\s*\(\s*svcGetSystemTick\(\)\s*<\s*target\s*\)\s*\{\s*\}')
waits = list(wait_pat.finditer(m))
if len(waits) != 2:
    raise SystemExit(f'v750 expected exactly 2 host-phase waits, found {len(waits)}')
m = wait_pat.sub('\n                    /* v7.5 natural phase: telemetry target only; do not wait */', m)
if re.search(r'while\s*\(\s*svcGetSystemTick\(\)\s*<', m):
    raise SystemExit('v750 found an unexpected remaining host-tick wait')

# Make the build identity unmistakable on the live selector screens while
# preserving the existing field layout and hot-path logic.
t = t.replace('S738 A-EPOCH SCAN', 'S750 SHINY SCAN')
t = t.replace('S738 CONF SHINY SCAN', 'S750 SHINY SCAN')
t = t.replace('S738 SHINY LOCK', 'S750 SHINY READY')
t = t.replace('BUCKET738,V738,', 'BUCKET750,V750,')
m = m.replace('S738', 'S750')

# Later v7.x diagnostics inherited the old reset wording from v7.1.7.  Keep
# failures paused when a result-path checkpoint fails (so no unwanted game
# frame is released), but make the intended retry action explicit.  Search
# errors E2/E3 already use v6.5.7 host_request_resume(), which lets the user
# invoke the VC software reset immediately.
t = t.replace('S717 RESET RECOMMENDED', 'S750 VC RESET')
t = t.replace('R > VC RESET', 'R > VC RESET')

# Replace stale causal-control labels if present.  Selectors/timing fields are
# still logged, but have no causal effect because both host waits above are
# disabled.
for old in (
    'ABS SLOT{} FIXED',
    'ABS SLOT{} X=TOGGLE',
    'SLOT0 BASE  X=+1',
):
    t = t.replace(old, 'NATURAL RESUME')

# Add a small non-timing-sensitive policy marker to the saved selector CSV.
# The bucket row exists in the v7.3.8 generated source and is written only
# after the encounter result is locked.
marker = 'BUCKET750,V750,'
if marker not in t:
    raise SystemExit('v750 bucket CSV version marker missing')

# Sanity: keep the proven confidence evaluator and all three verification
# checkpoints.  These are the hybrid Y+X safety net: press selection happens
# before the encounter, then the actual path is checked as it unfolds.
required = [
    'pub fn evaluate_adaptive_bucket(',
    'primary_shiny',
    'deep_support',
    'practical_expected40_state',
    'practical_expected716_state',
    'practical_expected717_state',
    'fn practical_fail',
    'reset_scan_epoch_v716',
    'host_request_resume',
]
blob = p + '\n' + t + '\n' + m
missing = [x for x in required if x not in blob]
if missing:
    raise SystemExit(f'v750 required production markers missing: {missing}')

# Assert the build does not contain any direct writes to the observed RNG/DIV
# or enemy DV addresses introduced by this patch.  This is a narrow guard on
# the generated selector sources, not a general static analysis of PokeReader.
for forbidden in (
    'write_u16(0xd23d',
    'write_u8(0xd23d',
    'write_u16(0xd23e',
    'write_u8(0xd23e',
):
    if forbidden in blob.lower():
        raise SystemExit(f'v750 forbidden DV write marker present: {forbidden}')

M.write_text(m)
T.write_text(t)
P.write_text(p)
print('Applied Suicune v7.5.0 Shiny Selector: v738 confidence gates + natural START/Resume + VC-reset retry')
