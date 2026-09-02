#!/usr/bin/env python3
from pathlib import Path

p = Path('apply_suicune_absolute_resume_control_v730.py')
s = p.read_text()
start = s.find('# Add an explicit row next to the existing RPH metrics.')
end = s.find('main_path.write_text(m)', start)
if start < 0 or end < 0:
    raise SystemExit(f'v730 normalizer markers missing: start={start} end={end}')
s = s[:start] + '''# Existing RPH,V49 plus V38 already record wanted slot, target/actual tick and\n# resume_command_tick.  Keep v7.3 causal control free of an extra fragile CSV\n# insertion; offline validation computes the actual absolute slot from V38.\n\n''' + s[end:]
p.write_text(s)

a = Path('audit_suicune_v730.py')
x = a.read_text()
needle = "need('CONTROL,V730,A,10' in t, 'control CSV row missing')\n"
if needle not in x:
    raise SystemExit('v730 audit CONTROL-row check not found')
x = x.replace(needle, '', 1)
a.write_text(x)
print('Normalized v7.3 apply/audit: rely on existing RPH+V38 telemetry')
