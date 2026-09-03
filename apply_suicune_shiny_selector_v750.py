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
# B40/B716/B717 revalidation. v7.5.0 keeps that conservative evaluator for the
# first real shiny attempts, but makes every inherited host-phase control
# telemetry-only. Every successful encounter therefore comes from ordinary
# game progress rather than waiting inside Pause for a chosen system-tick phase.
# -------------------------------------------------------------------------

# The generated v7.3.8 source contains three tight host-tick waits inherited
# from the START/Resume/cadence causal experiments. Remove all three while
# retaining target/actual tick capture for diagnostics. Failing closed here is
# intentional: if the generator later adds/removes one, the production build
# must be reviewed instead of silently changing timing policy.
wait_pat = re.compile(r'\s*while\s*\(\s*svcGetSystemTick\(\)\s*<\s*target\s*\)\s*\{\s*\}')
waits = list(wait_pat.finditer(m))
if len(waits) != 3:
    raise SystemExit(f'v750 expected exactly 3 inherited host-phase waits, found {len(waits)}')
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

# Later v7.x diagnostics inherited the reset wording from v7.1.7. Keep result
# checkpoint failures paused, so no unwanted game frame is released before the
# user chooses VC Reset. Search errors E2/E3 already use the v6.5.7
# host_request_resume() path and are immediately reset-friendly.
t = t.replace('S717 RESET RECOMMENDED', 'S750 VC RESET')

# Replace stale causal-control labels if present. Selector/timing fields remain
# in telemetry, but no longer influence START/Resume because the host waits are
# gone.
for old in (
    'ABS SLOT{} FIXED',
    'ABS SLOT{} X=TOGGLE',
    'SLOT0 BASE  X=+1',
):
    t = t.replace(old, 'NATURAL RESUME')

marker = 'BUCKET750,V750,'
if marker not in t:
    raise SystemExit('v750 bucket CSV version marker missing')

# Keep the confidence evaluator and all three live verification checkpoints.
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

# Narrow policy guard: this selector build must not contain a direct write to
# the Japanese Suicune/Celebi DV watch bytes. The normal reader remains
# read-only at those locations.
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
print('Applied Suicune v7.5.0 Shiny Selector: v738 confidence gates + natural phase + VC-reset retry')
