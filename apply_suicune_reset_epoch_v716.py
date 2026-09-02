#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')


def need(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f'v716 missing {label}: {marker}')


def function_span(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'v716 function not found: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'v716 function brace not found: {signature}')
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit(f'v716 unclosed function: {signature}')


t = T.read_text()
for marker, label in [
    ('S715 SCAN', 'v715 scan UI'),
    ('S715 READY UP+B', 'v715 ready UI'),
    ('FASTTAIL715,V715', 'v715 fingerprint telemetry'),
    ('fn clear_stale_practical_status(&mut self)', 'stale status cleanup'),
    ('pub fn search_practical_targets(&mut self', 'fresh scan entry'),
    ('practical_live_checked', 'FR counter'),
    ('practical_live_lane_frames', 'P counter'),
    ('practical_empirical_cell_frames', 'X counter'),
    ('practical_live_exact_eval', 'exact EV counter'),
    ('practical_empirical_eval', 'empirical EV counter'),
    ('practical_live_index_wait', 'index SK counter'),
    ('practical_empirical_skip_exception', 'exception SK counter'),
]:
    need(t, marker, label)

# Centralized display/telemetry epoch reset. This intentionally does not touch
# the shiny search model, donor tables, branch guards or FASTTAIL capture.
helper = r'''    fn reset_scan_epoch_v716(&mut self) {
        self.practical_live_last_advance = u32::MAX;
        self.practical_live_checked = 0;
        self.practical_live_lane_frames = 0;
        self.practical_live_no_lane = 0;
        self.practical_live_found_advance = 0;
        self.practical_live_found_state = 0;
        self.practical_live_found_div = 0;
        self.practical_live_found_lane = 0;
        self.practical_live_start_tick = 0;
        self.practical_live_found_tick = 0;
        self.practical_live_index_wait = 0;
        self.practical_live_exact_eval = 0;
        self.practical_empirical = false;
        self.practical_empirical_eval = 0;
        self.practical_empirical_cell_frames = 0;
        self.practical_empirical_skip_exception = 0;
        self.practical_empirical_candidates = 0;
        self.practical_learn = 0;
    }

'''
anchor = '    fn clear_stale_practical_status(&mut self) {'
if helper.strip() not in t:
    if t.count(anchor) != 1:
        raise SystemExit(f'v716 helper insertion anchor count {t.count(anchor)}')
    t = t.replace(anchor, helper + anchor, 1)

# When an old terminal epoch expires after the VC has resumed/rebooted, clear
# every scan dashboard counter too. This prevents old P/X/EV/SK values from
# remaining visible in the new boot.
cs, ce = function_span(t, '    fn clear_stale_practical_status(&mut self)')
block = t[cs:ce]
if 'self.reset_scan_epoch_v716();' not in block:
    needle = '        self.practical_terminal_advance = 0;\n'
    if block.count(needle) != 1:
        raise SystemExit(f'v716 stale clear terminal anchor count {block.count(needle)}')
    block = block.replace(needle, needle + '        self.reset_scan_epoch_v716();\n', 1)
    t = t[:cs] + block + t[ce:]

# Fresh Y+DOWN must always begin from zero even if the user starts a new scan
# before the stale-status age threshold has elapsed. This is the user-visible
# guarantee: FR/ADV/P/X/EV/SK belong only to the current scan epoch.
ss, se = function_span(t, '    pub fn search_practical_targets(&mut self')
block = t[ss:se]
if 'self.reset_scan_epoch_v716();' not in block:
    brace = block.find('{')
    if brace < 0:
        raise SystemExit('v716 fresh scan brace missing')
    block = block[:brace+1] + '\n        self.reset_scan_epoch_v716();' + block[brace+1:]
    t = t[:ss] + block + t[se:]

# UI epoch only. CSV compatibility markers remain V710/V715.
t = t.replace('"S715 ', '"S716 ')

# Safety: current-root architecture, CrossBranch, LearnAllPost and final guards
# must remain present. No search criterion or evaluator is changed here.
for marker in [
    'fn practical_wait_monitor',
    'fn rebind_known_post_v713',
    'fn enter_stage3_learn',
    'practical_expected40_state',
    'practical_expected716_state',
    'practical_expected717_state',
    'FASTTAIL715,V715',
    'S716 SCAN',
    'S716 READY UP+B',
]:
    need(t, marker, marker)

T.write_text(t)
print('Applied Suicune v7.1.6 ResetEpoch: fresh scan and stale VC-reset cleanup zero FR/ADV/P/X/EV/SK telemetry')
