#!/usr/bin/env python3
from pathlib import Path

p = Path("apply_suicune_early_control_lab_v55.py")
s = p.read_text()

old_src = '''    \'\'\'        self.len += 1;\\n\\n        if self.probe_active && window[2] == SUICUNE_SPECIES {\'\'\','''
new_src = '''    \'\'\'        self.len += 1;\'\'\','''

old_new_tail = '''        self.len += 1;\\n\\n        if self.probe_active && window[2] == SUICUNE_SPECIES {\'\'\','''
new_new_tail = '''        self.len += 1;\'\'\','''

for label, old, new in [
    ("detector source anchor", old_src, new_src),
    ("detector replacement tail", old_new_tail, new_new_tail),
]:
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 script match, got {n}")
    s = s.replace(old, new, 1)

p.write_text(s)
print("Fixed v5.5 detector insertion anchor")
