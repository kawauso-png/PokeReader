#!/usr/bin/env python3
from pathlib import Path

p = Path('reader_core/src/crystal/trace.rs')
s = p.read_text()
old = 'NEUTRALPROBE,V786,{},{},{},{:04X},{:04X},{:04X},{:04X},{},{},{},{},{},{},{},{},{:04X}\\n'
new = 'NEUTRALPROBE,V786,{},{},{},{:04X},{:04X},{:04X},{:04X},{},{},{},{},{},{},{},{},{},{:04X}\\n'
if s.count(old) != 1:
    raise SystemExit(f'v786 CSV format fix: expected 1 match, got {s.count(old)}')
p.write_text(s.replace(old, new, 1))
print('Fixed v7.8.6 NEUTRALPROBE CSV: 17 values / 17 format fields')
