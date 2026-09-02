#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs').read_text()

required = [
    'S723 INDEXLESS',
    'S723 PROBE',
    'self.practical_live_found_lane=253',
    'PHASESCAN,V723',
    'PRECOUNT,V723',
    'self.practical_live_checked>=3000',
    'pnp::request_pause()',
]
for marker in required:
    if marker not in T:
        raise SystemExit('v723 audit missing: ' + marker)

start = T.find('    fn live_root_monitor')
end = T.find('    fn practical_fail', start)
if start < 0 or end < 0:
    raise SystemExit('v723 audit live_root_monitor span missing')
mon = T[start:end]

# The entire point of v7.2.3 is that diagnostic stopping is independent of the
# Add/Sub index trackers.  These calls may still exist elsewhere for production
# shiny logic and arm-time telemetry, but never inside the diagnostic scanner.
for bad in [
    'add_div_tracker().index()',
    'sub_div_tracker().index()',
    'practical_live_index_wait=self.practical_live_index_wait.saturating_add(1)',
]:
    if bad in mon:
        raise SystemExit('v723 audit index gate leaked into phase scanner: ' + bad)

# Diagnostic path must remain prediction-free.
for bad in ['evaluate_empirical(', 'evaluate_exact(', 'bind_practical_prediction(']:
    if bad in mon:
        raise SystemExit('v723 audit production evaluator leaked into probe: ' + bad)

# Exact-current-root requirement and timing capture must remain intact.
for marker in ['if lag!=0 || best!=0', 'pre_vblank_timing_capture_stop();']:
    if marker not in mon:
        raise SystemExit('v723 audit lost exact/timing invariant: ' + marker)

print('v7.2.3 indexless phase probe audit PASS')
