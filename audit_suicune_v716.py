#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

required = [
    'fn reset_scan_epoch_v716(&mut self)',
    'self.practical_live_checked = 0;',
    'self.practical_live_lane_frames = 0;',
    'self.practical_empirical_cell_frames = 0;',
    'self.practical_live_exact_eval = 0;',
    'self.practical_empirical_eval = 0;',
    'self.practical_live_index_wait = 0;',
    'self.practical_empirical_skip_exception = 0;',
    'S716 SCAN',
    'S716 READY UP+B',
    'FASTTAIL715,V715',
    'fn practical_wait_monitor',
    'fn rebind_known_post_v713',
    'fn enter_stage3_learn',
    'practical_expected716_state',
    'practical_expected717_state',
]
for x in required:
    if x not in t:
        raise SystemExit('v716 audit missing: ' + x)

# Helper must be called both by fresh Y+DOWN search and stale reset cleanup.
if t.count('self.reset_scan_epoch_v716();') != 2:
    raise SystemExit(f'v716 expected two reset epoch calls, got {t.count("self.reset_scan_epoch_v716();")}')

if 'S715 SCAN' in t:
    raise SystemExit('v716 stale S715 SCAN remains')

# Search architecture must still be current-root and no future horizon should
# have been reintroduced by this UI/reset-only patch.
start = t.find('fn practical_wait_monitor')
if start < 0:
    raise SystemExit('v716 wait monitor missing')
window = t[start:start+12000]
for forbidden in ['normal_step(', 'SEARCH_HORIZON', 'target == current']:
    if forbidden in window:
        raise SystemExit('v716 future-search regression: ' + forbidden)

print('AUDIT PASS: v7.1.6 zeros FR/ADV/P/X/EV/SK on fresh scan and stale VC-reset cleanup; search/model/guards retained')
