#!/usr/bin/env python3
from pathlib import Path
import re

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# v7.1.2 deliberately changes only the on-screen interpretation of scan counters.
# RNG_ADVANCE can move several times during one actionable VC frame.  The old
# A/C labels made an ADV delta look like the number of roots that the user could
# actually start Exact2F from.  Keep all v7.1 search/evaluator/guard logic intact.
if 'S711 SCAN' not in t:
    raise SystemExit('v712: S711 SCAN anchor missing')
if 'STAGE3,V710' not in t or 'BRANCH710,V710' not in t:
    raise SystemExit('v712: v7.1 telemetry missing')
if 'practical_empirical_cell_frames' not in t:
    raise SystemExit('v712: empirical cell counter missing')
if 'practical_empirical_skip_exception' not in t:
    raise SystemExit('v712: empirical skip counter missing')

# UI epoch only; CSV formats stay V710 so all existing parsers remain compatible.
t = t.replace('"S711 ', '"S712 ')

scan_re = re.compile(
    r'pnp::println!\("S712 SCAN"\);\s*'
    r'pnp::println!\(\s*"A\{\} C\{\} P\{\}",\s*'
    r'rng_advance\(\)\.wrapping_sub\(self\.practical_live_start_advance\),\s*'
    r'self\.practical_live_checked,\s*'
    r'self\.practical_live_lane_frames\s*\);\s*'
    r'pnp::println!\(\s*"X\{\} I\{\} E\{\}",\s*'
    r'self\.practical_empirical_eval,\s*'
    r'self\.practical_live_index_wait,\s*'
    r'self\.practical_live_exact_eval\s*\);',
    re.S,
)
new_scan = '''pnp::println!("S712 SCAN");
                // FR = actionable VC-frame roots actually inspected.
                // ADV = logical RNG advances elapsed since SCAN start.
                pnp::println!(
                    "FR{} ADV{}",
                    self.practical_live_checked,
                    rng_advance().wrapping_sub(self.practical_live_start_advance)
                );
                // P/X are PRE-cell hits: proven / recent empirical.
                pnp::println!(
                    "P{} X{}",
                    self.practical_live_lane_frames,
                    self.practical_empirical_cell_frames
                );
                // EV = exact+empirical evaluations, SK = index/exception skips.
                pnp::println!(
                    "EV{} SK{}",
                    self.practical_live_exact_eval.saturating_add(self.practical_empirical_eval),
                    self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception)
                );'''
t, n = scan_re.subn(new_scan, t, count=1)
if n != 1:
    raise SystemExit(f'v712: SCAN block count {n}')

# Safety: this patch must not alter the search monitor or hard-guard functions.
for marker in [
    'fn practical_wait_monitor',
    'evaluate_exact',
    'evaluate_empirical',
    'practical_expected40_state',
    'practical_expected716_state',
    'practical_expected717_state',
    'S658 TEST',
]:
    if marker not in t:
        raise SystemExit('v712: safety marker missing: ' + marker)

T.write_text(t)
print('Applied Suicune v7.1.2 Actionable Counter UI: FR vs ADV made explicit; search logic unchanged')
