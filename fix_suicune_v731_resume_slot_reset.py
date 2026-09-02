#!/usr/bin/env python3
from pathlib import Path

P = Path('3gx/sources/main.c')
s = P.read_text()

old = '''            // Current Stage3 uses the calibrated zero resume/start phase slots.\n            // D-pad input does not alter those timing slots.\n            suicune_phase_slot = 0;\n            suicune_start_phase_slot = 0;'''
new = '''            // v7.3.1: keep the absolute resume-control slot selected by the\n            // control lab.  Only the legacy start-phase slot stays calibrated\n            // at zero.  Resetting suicune_phase_slot here caused Y+DOWN to\n            // overwrite the intended default SLOT1 on the next pause-loop poll.\n            suicune_start_phase_slot = 0;'''

n = s.count(old)
if n != 1:
    raise SystemExit(f'v731 resume-slot reset block: expected 1 match, got {n}')

s = s.replace(old, new, 1)
P.write_text(s)
print('Applied v7.3.1 ResumeSlotReset fix: Y-held poll no longer forces absolute resume slot to 0')
