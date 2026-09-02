#!/usr/bin/env python3
from pathlib import Path

p = Path('reader_core/src/crystal/trace.rs')
s = p.read_text()
old = 'pnp::println!("ABS SLOT{} X=TOGGLE", fixed.phase_slot & 7);'
new = 'pnp::println!("ABS SLOT{} X=TOGGLE", pnp::fixed_a_frame().phase_slot & 7);'
if s.count(old) != 1:
    raise SystemExit(f'v730 fixed UI expected 1 match, got {s.count(old)}')
s = s.replace(old, new, 1)
p.write_text(s)
print('Fixed v7.3 slot UI: use pnp::fixed_a_frame().phase_slot')
